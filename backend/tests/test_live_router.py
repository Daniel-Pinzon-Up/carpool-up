"""Entrada del WebSocket /ws: origen, autenticacion por el primer mensaje, canales y cierre.

El manejador se llama con un socket simulado dentro del mismo bucle de eventos; la base es la
sesion transaccional de las pruebas y Redis es el real (pub/sub)."""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole, UserStatus
from app.core.redis import redis_client
from app.core.security import create_access_token
from app.modules.live import router as live_router
from app.modules.safety.service import ADMIN_CHANNEL
from tests.conftest import UserFactory

DISCONNECT = object()


class FakeSocket:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {"host": "localhost"}
        self.incoming: asyncio.Queue[Any] = asyncio.Queue()
        self.sent: list[dict[str, Any]] = []
        self.accepted = False
        self.closed: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000) -> None:
        self.closed = code

    async def _next(self) -> Any:
        item = await self.incoming.get()
        if item is DISCONNECT:
            raise WebSocketDisconnect()
        return item

    async def receive_json(self) -> Any:
        return await self._next()

    async def receive_text(self) -> str:
        return json.dumps(await self._next())

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def wait_for(self, kind: str, seconds: float = 3) -> dict[str, Any]:
        async def look() -> dict[str, Any]:
            while True:
                for message in self.sent:
                    if message.get("type") == kind:
                        return message
                await asyncio.sleep(0.02)

        return await asyncio.wait_for(look(), seconds)


@pytest.fixture(autouse=True)
def same_session(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """El router abre sesiones propias; aqui usan la de la prueba para ver sus datos."""

    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(live_router, "SessionLocal", factory)
    yield


async def run(socket: FakeSocket) -> asyncio.Task[None]:
    return asyncio.create_task(live_router.live(socket))  # type: ignore[arg-type]


async def test_foreign_origin_is_rejected_before_accepting() -> None:
    socket = FakeSocket({"host": "localhost", "origin": "https://evil.example"})
    await live_router.live(socket)  # type: ignore[arg-type]
    assert not socket.accepted
    assert socket.closed == live_router.CLOSE_FORBIDDEN_ORIGIN


async def test_same_origin_is_allowed() -> None:
    socket = FakeSocket({"host": "localhost", "origin": "https://localhost"})
    assert live_router.origin_allowed(socket)  # type: ignore[arg-type]


@pytest.mark.parametrize("first", [{"type": "auth", "token": "no-es-un-token"}, ["auth"], None])
async def test_bad_first_message_closes_with_4401(first: Any) -> None:
    socket = FakeSocket()
    await socket.incoming.put(first)
    await live_router.live(socket)  # type: ignore[arg-type]
    assert socket.accepted
    assert socket.closed == live_router.CLOSE_UNAUTHORIZED


async def test_silence_after_connecting_closes_with_4401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_router, "AUTH_TIMEOUT_S", 0.05)
    socket = FakeSocket()
    await live_router.live(socket)  # type: ignore[arg-type]
    assert socket.closed == live_router.CLOSE_UNAUTHORIZED


async def test_blocked_account_cannot_connect(make_user: UserFactory) -> None:
    user = await make_user(UserRole.PASSENGER, status=UserStatus.BLOCKED)
    socket = FakeSocket()
    await socket.incoming.put({"type": "auth", "token": create_access_token(user.id, user.role)})
    await live_router.live(socket)  # type: ignore[arg-type]
    assert socket.closed == live_router.CLOSE_UNAUTHORIZED


async def test_valid_token_gets_ready_and_answers_ping(make_user: UserFactory) -> None:
    user = await make_user(UserRole.PASSENGER)
    socket = FakeSocket()
    await socket.incoming.put({"type": "auth", "token": create_access_token(user.id, user.role)})
    task = await run(socket)
    ready = await socket.wait_for("ready")
    assert ready["conversations"] == [] and ready["trips"] == []
    await socket.incoming.put({"type": "ping"})
    await socket.wait_for("pong")
    await socket.incoming.put(DISCONNECT)
    await asyncio.wait_for(task, 3)
    assert socket.closed is None


async def test_admins_hear_emergencies_live(make_user: UserFactory) -> None:
    admin = await make_user(UserRole.ADMIN)
    socket = FakeSocket()
    await socket.incoming.put({"type": "auth", "token": create_access_token(admin.id, admin.role)})
    task = await run(socket)
    await socket.wait_for("ready")
    # Da tiempo a que la suscripcion quede activa en Redis antes de publicar.
    event = {"type": "emergency", "emergency": {"id": "e-1"}}
    for _ in range(20):
        await redis_client.publish(ADMIN_CHANNEL, json.dumps(event))
        try:
            received = await socket.wait_for("emergency", seconds=0.2)
            break
        except TimeoutError:
            continue
    else:
        raise AssertionError("el administrador no recibio la emergencia")
    assert received["emergency"]["id"] == "e-1"
    await socket.incoming.put(DISCONNECT)
    await asyncio.wait_for(task, 3)
