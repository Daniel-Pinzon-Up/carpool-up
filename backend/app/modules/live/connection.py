"""Una conexion WebSocket ya autenticada: mensajes del cliente y eventos de Redis.

Separada del endpoint para probarla sin socket: recibe como enviar al cliente, como
suscribirse a un canal y de donde sacar sesiones de base de datos.
"""

import json
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.realtime import conversation_channel, publish_now
from app.modules.chat.service import ChatService
from app.modules.users.models import User

logger = structlog.get_logger("live")

# Como mucho SEND_LIMIT mensajes de chat por conexion cada SEND_WINDOW segundos.
SEND_LIMIT = 10
SEND_WINDOW = 10.0
MAX_FRAME_BYTES = 8_192

Send = Callable[[dict[str, Any]], Awaitable[None]]
Subscribe = Callable[[str], Awaitable[None]]
Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class LiveConnection:
    def __init__(
        self,
        user_id: uuid.UUID,
        user_name: str,
        conversations: set[uuid.UUID],
        send: Send,
        subscribe: Subscribe,
        sessions: Sessions,
    ) -> None:
        self.user_id = user_id
        self.user_name = user_name
        self.conversations = conversations
        self.send = send
        self.subscribe = subscribe
        self.sessions = sessions
        self.sent: deque[float] = deque()

    async def error(self, code: str, client_id: Any = None) -> None:
        await self.send({"type": "error", "code": code, "client_id": client_id})

    # --- Del servidor al cliente -----------------------------------------------------------

    async def on_event(self, data: str) -> None:
        """Reenvia el evento; si el usuario entro a un chat nuevo, empieza a escucharlo."""
        try:
            payload = json.loads(data)
        except ValueError:
            return
        if payload.get("type") == "conversation.joined":
            conversation_id = uuid.UUID(payload["conversation_id"])
            if conversation_id not in self.conversations:
                self.conversations.add(conversation_id)
                await self.subscribe(conversation_channel(conversation_id))
        if payload.get("type") == "typing" and payload.get("user_id") == str(self.user_id):
            return  # No se muestra el propio "escribiendo".
        await self.send(payload)

    # --- Del cliente al servidor -----------------------------------------------------------

    async def handle_raw(self, raw: str) -> None:
        if len(raw.encode()) > MAX_FRAME_BYTES:
            await self.error("PAYLOAD_TOO_LARGE")
            return
        try:
            message = json.loads(raw)
        except ValueError:
            await self.error("BAD_REQUEST")
            return
        if not isinstance(message, dict):
            await self.error("BAD_REQUEST")
            return
        await self.handle(message)

    async def handle(self, message: dict[str, Any]) -> None:
        kind = message.get("type")
        client_id = message.get("client_id")
        if kind == "ping":
            await self.send({"type": "pong"})
            return
        if kind not in ("chat.send", "chat.read", "typing"):
            await self.error("UNKNOWN_TYPE", client_id)
            return
        try:
            conversation_id = uuid.UUID(str(message.get("conversation_id")))
        except ValueError:
            await self.error("BAD_REQUEST", client_id)
            return
        if conversation_id not in self.conversations:
            await self.error("NOT_FOUND", client_id)
            return
        if kind == "typing":
            await publish_now(
                conversation_channel(conversation_id),
                {
                    "type": "typing",
                    "conversation_id": str(conversation_id),
                    "user_id": str(self.user_id),
                    "name": self.user_name,
                },
            )
        elif kind == "chat.read":
            await self.with_chat(lambda chat, user: chat.mark_read(user, conversation_id))
        else:
            await self.chat_send(conversation_id, message.get("body"), client_id)

    async def chat_send(self, conversation_id: uuid.UUID, body: Any, client_id: Any) -> None:
        now = time.monotonic()
        while self.sent and now - self.sent[0] > SEND_WINDOW:
            self.sent.popleft()
        if len(self.sent) >= SEND_LIMIT:
            await self.error("RATE_LIMITED", client_id)
            return
        if not isinstance(body, str) or not body.strip() or len(body.strip()) > 1000:
            await self.error("MESSAGE_INVALID", client_id)
            return
        self.sent.append(now)

        async def send(chat: ChatService, user: User) -> None:
            out = await chat.send(user, conversation_id, body)
            await self.send(
                {"type": "chat.ack", "client_id": client_id, "message": out.model_dump(mode="json")}
            )

        await self.with_chat(send, client_id)

    async def with_chat(
        self,
        action: Callable[[ChatService, User], Awaitable[Any]],
        client_id: Any = None,
    ) -> None:
        async with self.sessions() as session:
            user = await session.get(User, self.user_id)
            if user is None:
                await self.error("UNAUTHORIZED", client_id)
                return
            try:
                await action(ChatService(session), user)
            except AppError as exc:
                await session.rollback()
                await self.error(exc.code, client_id)
