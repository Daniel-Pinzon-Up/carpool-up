"""WebSocket /ws (seccion 9).

1. El cliente abre la conexion y en el primer mensaje envia {"type": "auth", "token": ...}
   (el token no viaja en la URL, que queda en los logs).
2. El servidor responde {"type": "ready"} y escucha user:{id} y conv:{id} de cada chat.
3. Del cliente llegan ping, chat.send, chat.read y typing; del servidor, notification,
   notification.read, message, typing, conversation.joined, chat.ack y error.
4. Cuando el token vence el servidor cierra con 4001 y el cliente se reconecta con uno nuevo.
"""

import asyncio
import uuid
from datetime import datetime
from urllib.parse import urlsplit

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio.client import PubSub

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.enums import UserStatus
from app.core.realtime import conversation_channel, user_channel
from app.core.redis import redis_client
from app.core.security import decode_access_token
from app.modules.auth.models import UserSession
from app.modules.chat.service import ChatService
from app.modules.live.connection import LiveConnection
from app.modules.users.models import User

logger = structlog.get_logger("live")
router = APIRouter()

AUTH_TIMEOUT_S = 10
CLOSE_UNAUTHORIZED = 4401
CLOSE_TOKEN_EXPIRED = 4001
CLOSE_FORBIDDEN_ORIGIN = 4403


def origin_allowed(websocket: WebSocket) -> bool:
    """Mismo origen (detras de Nginx) o un origen de desarrollo permitido."""
    origin = websocket.headers.get("origin")
    if origin is None:
        return True
    if origin in get_settings().cors_origins:
        return True
    return urlsplit(origin).netloc == websocket.headers.get("host")


async def authenticate(token: object) -> tuple[uuid.UUID, str, datetime | None] | None:
    if not isinstance(token, str):
        return None
    claims = decode_access_token(token)
    if claims is None:
        return None
    async with SessionLocal() as session:
        if claims.session_id is not None:
            user_session = await session.get(UserSession, claims.session_id)
            if (
                user_session is None
                or user_session.user_id != claims.user_id
                or user_session.revoked_at is not None
                or user_session.expires_at <= utcnow()
            ):
                return None
        user = await session.get(User, claims.user_id)
        if user is None or user.deleted_at is not None or user.status == UserStatus.BLOCKED:
            return None
        return user.id, user.full_name, claims.expires_at


async def conversation_ids(user_id: uuid.UUID) -> set[uuid.UUID]:
    async with SessionLocal() as session:
        return set(await ChatService(session).active_ids(user_id))


@router.websocket("/ws")
async def live(websocket: WebSocket) -> None:
    if not origin_allowed(websocket):
        await websocket.close(code=CLOSE_FORBIDDEN_ORIGIN)
        return
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_S)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        await _close(websocket, CLOSE_UNAUTHORIZED)
        return
    identity = await authenticate(first.get("token") if isinstance(first, dict) else None)
    if identity is None:
        await _close(websocket, CLOSE_UNAUTHORIZED)
        return
    user_id, name, expires_at = identity

    pubsub: PubSub = redis_client.pubsub()
    conversations = await conversation_ids(user_id)
    await pubsub.subscribe(user_channel(user_id), *(conversation_channel(c) for c in conversations))
    connection = LiveConnection(
        user_id=user_id,
        user_name=name,
        conversations=conversations,
        send=websocket.send_json,
        subscribe=pubsub.subscribe,
        sessions=SessionLocal,
    )
    await websocket.send_json({"type": "ready", "conversations": [str(c) for c in conversations]})
    logger.info("ws_connected", conversations=len(conversations))

    async def from_redis() -> None:
        async for item in pubsub.listen():
            if item.get("type") == "message":
                await connection.on_event(item["data"])

    async def from_client() -> None:
        while True:
            await connection.handle_raw(await websocket.receive_text())

    async def until_expiry() -> None:
        if expires_at is None:
            await asyncio.Event().wait()
            return
        await asyncio.sleep(max(0.0, (expires_at - utcnow()).total_seconds()))
        await _close(websocket, CLOSE_TOKEN_EXPIRED)

    tasks = [asyncio.create_task(job()) for job in (from_redis, from_client, until_expiry)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            error = task.exception()
            if error is not None and not isinstance(error, WebSocketDisconnect):
                logger.warning("ws_error", error=type(error).__name__)
    finally:
        for task in tasks:
            task.cancel()
        await pubsub.aclose()  # type: ignore[no-untyped-call]
        logger.info("ws_closed")


async def _close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        pass  # Ya estaba cerrado.
