"""Chat y tiempo real: chats por reserva, mensajes, avisos, lectura, retencion y WebSocket."""

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.clock import utcnow
from app.core.enums import UserRole
from app.core.realtime import conversation_channel, emit, user_channel
from app.modules.chat.models import Conversation, Message
from app.modules.chat.service import close_finished_conversations, purge_chat
from app.modules.live.connection import SEND_LIMIT, LiveConnection
from app.modules.notifications.models import Notification
from app.modules.places.models import Place
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, EventLog, UserFactory, auth
from tests.test_bookings import book, decide, published

pytestmark = pytest.mark.integration


async def ride(
    api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    **trip: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Viaje publicado con la reserva del pasajero aceptada."""
    published_trip = await published(api, driver, places, **trip)
    booking = (await book(api, passenger, published_trip["id"], places)).json()
    response = await decide(api, driver[0], booking["id"], "accept")
    assert response.status_code == 200, response.text
    return published_trip, booking


async def chats(api: AsyncClient, user: User) -> list[dict[str, Any]]:
    response = await api.get(f"{API}/conversations", headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()


async def say(api: AsyncClient, user: User, conversation_id: str, body: str) -> dict[str, Any]:
    response = await api.post(
        f"{API}/conversations/{conversation_id}/messages", json={"body": body}, headers=auth(user)
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def passenger(make_user: UserFactory) -> User:
    return await make_user(UserRole.PASSENGER)


async def test_accepting_a_booking_opens_group_and_direct_chats(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
    events: EventLog,
) -> None:
    trip, _ = await ride(routing_api, driver, places, passenger)
    mine = await chats(routing_api, passenger)
    assert sorted(c["kind"] for c in mine) == ["direct", "trip_group"]
    group = next(c for c in mine if c["kind"] == "trip_group")
    direct = next(c for c in mine if c["kind"] == "direct")
    assert group["title"] == "Ciudad Universitaria - Terminal"
    assert [m["is_driver"] for m in group["members"]] == [True, False]
    assert direct["counterpart"] == driver[0].full_name
    assert "email" not in str(mine)
    driver_direct = next(c for c in await chats(routing_api, driver[0]) if c["kind"] == "direct")
    assert driver_direct["counterpart"] == passenger.full_name

    joined = await events.on(user_channel(passenger.id))
    assert {e["conversation_id"] for e in joined if e["type"] == "conversation.joined"} == {
        group["id"],
        direct["id"],
    }
    view = (await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(passenger))).json()
    assert view["chat_id"] == group["id"]
    stranger = await make_user(UserRole.PASSENGER)
    view = (await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(stranger))).json()
    assert view["chat_id"] is None
    response = await routing_api.get(f"{API}/conversations/{group['id']}", headers=auth(stranger))
    assert response.status_code == 404

    # Un segundo pasajero entra al mismo grupal, con su propio directo.
    other = await make_user(UserRole.PASSENGER)
    booking = (await book(routing_api, other, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")
    group = next(c for c in await chats(routing_api, other) if c["kind"] == "trip_group")
    assert len(group["members"]) == 3
    assert len([c for c in await chats(routing_api, driver[0]) if c["kind"] == "direct"]) == 2


async def test_messages_are_broadcast_counted_and_read(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    events: EventLog,
) -> None:
    await ride(routing_api, driver, places, passenger)
    group = next(c for c in await chats(routing_api, passenger) if c["kind"] == "trip_group")
    first = await say(routing_api, passenger, group["id"], "  Llego en 5 minutos  ")
    assert first["body"] == "Llego en 5 minutos"
    assert first["sender_name"] == passenger.full_name
    await say(routing_api, passenger, group["id"], "Estoy en la entrada")

    broadcast = await events.on(conversation_channel(group["id"]))
    assert [e["message"]["body"] for e in broadcast] == [
        "Llego en 5 minutos",
        "Estoy en la entrada",
    ]

    # El conductor ve 2 sin leer y un solo aviso (no uno por mensaje).
    listed = next(c for c in await chats(routing_api, driver[0]) if c["id"] == group["id"])
    assert listed["unread"] == 2
    assert listed["last_message"]["body"] == "Estoy en la entrada"
    own = next(c for c in await chats(routing_api, passenger) if c["id"] == group["id"])
    assert own["unread"] == 0
    notices = await db.scalar(
        select(func.count()).where(
            Notification.user_id == driver[0].id, Notification.kind == "message_new"
        )
    )
    assert notices == 1
    live = await events.on(user_channel(driver[0].id))
    assert any(
        e["type"] == "notification" and e["notification"]["kind"] == "message_new" for e in live
    )
    unread = (await routing_api.get(f"{API}/conversations/unread", headers=auth(driver[0]))).json()
    assert unread == {"unread": 2, "conversations": 1}

    response = await routing_api.post(
        f"{API}/conversations/{group['id']}/read", headers=auth(driver[0])
    )
    assert response.status_code == 204
    unread = (await routing_api.get(f"{API}/conversations/unread", headers=auth(driver[0]))).json()
    assert unread == {"unread": 0, "conversations": 0}
    pending = await db.scalar(
        select(func.count()).where(
            Notification.user_id == driver[0].id,
            Notification.kind == "message_new",
            Notification.read_at.is_(None),
        )
    )
    assert pending == 0

    response = await routing_api.post(
        f"{API}/conversations/{group['id']}/messages", json={"body": "   "}, headers=auth(driver[0])
    )
    assert response.status_code == 422
    response = await routing_api.post(
        f"{API}/conversations/{group['id']}/messages",
        json={"body": "x" * 1001},
        headers=auth(driver[0]),
    )
    assert response.status_code == 422


async def test_history_pages_backwards_and_catches_up(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    await ride(routing_api, driver, places, passenger)
    group = next(c for c in await chats(routing_api, passenger) if c["kind"] == "trip_group")
    sent = [await say(routing_api, passenger, group["id"], f"Mensaje {n}") for n in range(5)]
    url = f"{API}/conversations/{group['id']}/messages"

    latest = (await routing_api.get(url, params={"limit": 2}, headers=auth(driver[0]))).json()
    assert [m["body"] for m in latest] == ["Mensaje 3", "Mensaje 4"]
    older = (
        await routing_api.get(
            url, params={"limit": 2, "before": latest[0]["id"]}, headers=auth(driver[0])
        )
    ).json()
    assert [m["body"] for m in older] == ["Mensaje 1", "Mensaje 2"]
    # Al reconectar se pide lo que llego despues del ultimo mensaje visto.
    newer = (
        await routing_api.get(url, params={"after": sent[2]["id"]}, headers=auth(driver[0]))
    ).json()
    assert [m["body"] for m in newer] == ["Mensaje 3", "Mensaje 4"]


async def test_leaving_and_cancelling_close_the_right_chats(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    trip, booking = await ride(routing_api, driver, places, passenger)
    other = await make_user(UserRole.PASSENGER)
    second = (await book(routing_api, other, trip["id"], places)).json()
    await decide(routing_api, driver[0], second["id"], "accept")

    # Quien cancela sale del grupal; el directo con el conductor sigue.
    await routing_api.post(
        f"{API}/bookings/{booking['id']}/cancel", json={}, headers=auth(passenger)
    )
    assert [c["kind"] for c in await chats(routing_api, passenger)] == ["direct"]

    group = next(c for c in await chats(routing_api, other) if c["kind"] == "trip_group")
    assert len(group["members"]) == 2
    await routing_api.post(
        f"{API}/trips/{trip['id']}/cancel",
        json={"reason": "Se dano el carro"},
        headers=auth(driver[0]),
    )
    group = next(c for c in await chats(routing_api, other) if c["id"] == group["id"])
    assert group["closed"] is True
    response = await routing_api.post(
        f"{API}/conversations/{group['id']}/messages", json={"body": "Hola"}, headers=auth(other)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONVERSATION_CLOSED"


async def test_retention_closes_finished_trips_and_purges_old_chats(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip, _ = await ride(routing_api, driver, places, passenger)
    group = next(c for c in await chats(routing_api, passenger) if c["kind"] == "trip_group")
    await say(routing_api, passenger, group["id"], "Gracias por el viaje")
    row = await db.get(Trip, trip["id"])
    assert row is not None
    row.departs_at = utcnow() - timedelta(hours=5)
    await db.flush()

    assert await close_finished_conversations(db) == 2
    conversation = await db.get(Conversation, uuid.UUID(group["id"]))
    assert conversation is not None
    await db.refresh(conversation)
    assert conversation.closed_at is not None
    assert await purge_chat(db) == 0

    conversation.closed_at = utcnow() - timedelta(days=31)
    await db.flush()
    assert await purge_chat(db) == 1
    left = await db.scalar(
        select(func.count()).where(Message.conversation_id == uuid.UUID(group["id"]))
    )
    assert left == 0


# --- WebSocket ---------------------------------------------------------------------------


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.subscribed: list[str] = []

    async def send(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)

    async def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)


async def test_live_connection_handles_client_messages(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    events: EventLog,
) -> None:
    await ride(routing_api, driver, places, passenger)
    group = next(c for c in await chats(routing_api, passenger) if c["kind"] == "trip_group")
    group_id = uuid.UUID(group["id"])

    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        yield db

    socket = FakeSocket()
    connection = LiveConnection(
        passenger.id, passenger.full_name, {group_id}, socket.send, socket.subscribe, sessions
    )
    await connection.handle_raw('{"type": "ping"}')
    assert socket.sent[-1] == {"type": "pong"}
    await connection.handle_raw("no es json")
    assert socket.sent[-1]["code"] == "BAD_REQUEST"

    await connection.handle(
        {"type": "chat.send", "conversation_id": str(group_id), "body": "Hola", "client_id": "c1"}
    )
    ack = socket.sent[-1]
    assert ack["type"] == "chat.ack"
    assert ack["client_id"] == "c1"
    assert ack["message"]["body"] == "Hola"
    assert [e["message"]["body"] for e in await events.on(conversation_channel(group_id))] == [
        "Hola"
    ]

    # Un chat del que no es miembro no existe para esta conexion.
    await connection.handle(
        {"type": "chat.send", "conversation_id": str(uuid.uuid4()), "body": "x", "client_id": "c2"}
    )
    assert socket.sent[-1] == {"type": "error", "code": "NOT_FOUND", "client_id": "c2"}

    await connection.handle({"type": "typing", "conversation_id": str(group_id)})
    typing = [e for e in await events.on(conversation_channel(group_id)) if e["type"] == "typing"]
    assert typing[0]["name"] == passenger.full_name
    # El propio "escribiendo" no vuelve al que escribe; el de otros si.
    sent_before = len(socket.sent)
    await connection.on_event(
        json.dumps(
            {"type": "typing", "user_id": str(passenger.id), "conversation_id": str(group_id)}
        )
    )
    assert len(socket.sent) == sent_before
    await connection.on_event('{"type": "typing", "user_id": "otro", "conversation_id": "x"}')
    assert len(socket.sent) == sent_before + 1

    # Entrar a un chat nuevo suscribe la conexion a su canal.
    new_id = uuid.uuid4()
    await connection.on_event(
        json.dumps({"type": "conversation.joined", "conversation_id": str(new_id)})
    )
    assert socket.subscribed == [conversation_channel(new_id)]
    assert new_id in connection.conversations

    for n in range(SEND_LIMIT):
        await connection.handle(
            {"type": "chat.send", "conversation_id": str(group_id), "body": f"m{n}"}
        )
    assert socket.sent[-1]["code"] == "RATE_LIMITED"


async def test_notifications_are_published_after_commit(
    routing_api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    events: EventLog,
) -> None:
    trip = await published(routing_api, driver, places)
    await book(routing_api, passenger, trip["id"], places)
    live = await events.on(user_channel(driver[0].id))
    assert [e["notification"]["kind"] for e in live if e["type"] == "notification"] == [
        "booking_requested"
    ]


async def test_events_wait_for_commit_and_vanish_on_rollback(
    engine: AsyncEngine, events: EventLog
) -> None:
    async with AsyncSession(engine) as session:
        emit(session, "user:prueba", {"type": "x"})
        await session.rollback()
        emit(session, "user:prueba", {"type": "y"})
        assert await events.on("user:prueba") == []
        await session.commit()
    assert await events.on("user:prueba") == [{"type": "y"}]
