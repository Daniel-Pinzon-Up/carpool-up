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

from app.core.clock import utcnow
from app.core.enums import TripStatus
from app.core.errors import AppError
from app.core.realtime import conversation_channel, publish_now
from app.modules.chat.service import ChatService
from app.modules.safety.location import location_channel, save_location
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.users.models import User

logger = structlog.get_logger("live")

# Como mucho SEND_LIMIT mensajes de chat por conexion cada SEND_WINDOW segundos.
SEND_LIMIT = 10
SEND_WINDOW = 10.0
MAX_FRAME_BYTES = 8_192
# Ubicacion del conductor: como mucho una cada LOCATION_INTERVAL segundos.
LOCATION_INTERVAL = 2.0

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
        unsubscribe: Subscribe | None = None,
        trips: set[uuid.UUID] | None = None,
    ) -> None:
        self.user_id = user_id
        self.user_name = user_name
        self.conversations = conversations
        self.send = send
        self.subscribe = subscribe
        self.unsubscribe = unsubscribe
        self.sessions = sessions
        self.sent: deque[float] = deque()
        # Viajes en curso cuya ubicacion escucha y los que conduce (verificados en la base).
        self.trips: set[uuid.UUID] = trips if trips is not None else set()
        self.driving: set[uuid.UUID] = set()
        self.last_location = 0.0
        self.location_ttl: int | None = None

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
        if payload.get("type") in ("trip.started", "trip.finished") and payload.get("trip_id"):
            await self.follow_trip(uuid.UUID(payload["trip_id"]), payload["type"] == "trip.started")
        if payload.get("type") == "typing" and payload.get("user_id") == str(self.user_id):
            return  # No se muestra el propio "escribiendo".
        await self.send(payload)

    async def follow_trip(self, trip_id: uuid.UUID, start: bool) -> None:
        """Empieza o deja de escuchar la ubicacion del viaje."""
        if start and trip_id not in self.trips:
            self.trips.add(trip_id)
            await self.subscribe(location_channel(trip_id))
        elif not start and trip_id in self.trips:
            self.trips.discard(trip_id)
            self.driving.discard(trip_id)
            if self.unsubscribe is not None:
                await self.unsubscribe(location_channel(trip_id))

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
        if kind == "location.update":
            await self.location_update(message)
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

    async def location_update(self, message: dict[str, Any]) -> None:
        """Solo el conductor de un viaje en curso. Se guarda en Redis con vencimiento y se
        difunde a los participantes; las que llegan muy seguidas se descartan en silencio."""
        now = time.monotonic()
        if now - self.last_location < LOCATION_INTERVAL:
            return
        try:
            trip_id = uuid.UUID(str(message.get("trip_id")))
            lat, lon = float(message["lat"]), float(message["lon"])
        except (KeyError, TypeError, ValueError):
            await self.error("BAD_REQUEST")
            return
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            await self.error("BAD_REQUEST")
            return
        if trip_id not in self.driving and not await self.can_drive(trip_id):
            await self.error("NOT_FOUND")
            return
        self.last_location = now
        point: dict[str, Any] = {"lat": lat, "lon": lon, "at": utcnow().isoformat()}
        for field in ("accuracy", "heading", "speed"):
            value = message.get(field)
            if isinstance(value, int | float):
                point[field] = float(value)
        await save_location(trip_id, point, self.location_ttl or 120)
        await publish_now(
            location_channel(trip_id), {"type": "location", "trip_id": str(trip_id), **point}
        )

    async def can_drive(self, trip_id: uuid.UUID) -> bool:
        async with self.sessions() as session:
            trip = await session.get(Trip, trip_id)
            if (
                trip is None
                or trip.driver_id != self.user_id
                or trip.status != TripStatus.IN_PROGRESS
            ):
                return False
            if self.location_ttl is None:
                settings = SettingsService(session)
                self.location_ttl = int(await settings.get("live_location_ttl_seconds"))
        self.driving.add(trip_id)
        await self.follow_trip(trip_id, True)
        return True

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
