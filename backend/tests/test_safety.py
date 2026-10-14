"""Seguridad: enlace compartido, ubicacion en vivo, emergencias y contactos de confianza."""

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import UserRole
from app.modules.audit.models import AuditLog
from app.modules.live.connection import LiveConnection
from app.modules.places.models import Place
from app.modules.safety.location import location_channel, location_key
from app.modules.safety.service import ADMIN_CHANNEL
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, EventLog, MemoryLocations, UserFactory, auth
from tests.test_bookings import kinds
from tests.test_chat import FakeSocket
from tests.test_trip_lifecycle import act, full_trip, move

pytestmark = pytest.mark.integration


async def started_trip(
    api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> dict[str, str]:
    trip, _ = await full_trip(api, driver, places, [passenger])
    await move(db, trip["id"], 5)
    response = await act(api, driver[0], f"/trips/{trip['id']}/start")
    assert response.status_code == 200, response.text
    return trip


async def test_share_link_shows_vehicle_route_and_location_without_names(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
    locations: MemoryLocations,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    trip, _ = await full_trip(routing_api, driver, places, [passenger])
    stranger = await make_user(UserRole.PASSENGER)
    response = await act(routing_api, stranger, f"/trips/{trip['id']}/share-links")
    assert response.status_code == 404

    response = await act(routing_api, passenger, f"/trips/{trip['id']}/share-links")
    assert response.status_code == 201, response.text
    link = response.json()
    assert link["path"] == f"/compartido/{link['token']}"
    stored = await db.get(Trip, trip["id"])
    assert stored is not None
    assert stored.share_token_hash is not None and stored.share_token_hash != link["token"]

    public = await routing_api.get(f"{API}/public/share/{link['token']}")
    assert public.status_code == 200, public.text
    body = public.json()
    assert body["vehicle"]["plate"] == "ABC123"
    assert body["status"] == "scheduled"
    assert body["location"] is None
    assert body["stops"][0]["name"] == "Ciudad Universitaria"
    text = public.text
    for private in (driver[0].full_name, passenger.full_name, driver[0].email, passenger.email):
        assert private not in text

    # En curso aparece la ultima ubicacion del conductor.
    await move(db, trip["id"], 5)
    await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
    locations.values[location_key(trip["id"])] = json.dumps(
        {"lat": 7.38, "lon": -72.648, "at": utcnow().isoformat()}
    )
    body = (await routing_api.get(f"{API}/public/share/{link['token']}")).json()
    assert body["location"]["lat"] == 7.38

    stored.share_expires_at = utcnow() - timedelta(seconds=1)
    await db.flush()
    assert (await routing_api.get(f"{API}/public/share/{link['token']}")).status_code == 404
    assert (await routing_api.get(f"{API}/public/share/no-existe")).status_code == 404


async def test_driver_location_reaches_passengers_and_is_private(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
    events: EventLog,
    locations: MemoryLocations,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    trip = await started_trip(routing_api, db, driver, places, passenger)
    trip_id = uuid.UUID(trip["id"])

    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        yield db

    socket = FakeSocket()
    as_driver = LiveConnection(
        driver[0].id, driver[0].full_name, set(), socket.send, socket.subscribe, sessions
    )
    await as_driver.handle(
        {"type": "location.update", "trip_id": trip["id"], "lat": 7.381, "lon": -72.649, "speed": 8}
    )
    published = await events.on(location_channel(trip_id))
    assert published[0]["lat"] == 7.381
    assert published[0]["speed"] == 8.0
    assert location_key(trip_id) in locations.values
    # Las actualizaciones demasiado seguidas se descartan.
    await as_driver.handle(
        {"type": "location.update", "trip_id": trip["id"], "lat": 7.0, "lon": -72.0}
    )
    assert len(await events.on(location_channel(trip_id))) == 1

    seen = (
        await routing_api.get(f"{API}/trips/{trip['id']}/location", headers=auth(passenger))
    ).json()
    assert seen["lon"] == -72.649
    stranger = await make_user(UserRole.PASSENGER)
    response = await routing_api.get(f"{API}/trips/{trip['id']}/location", headers=auth(stranger))
    assert response.status_code == 404

    # Un pasajero no puede publicar la ubicacion del viaje.
    rider_socket = FakeSocket()
    as_rider = LiveConnection(
        passenger.id,
        passenger.full_name,
        set(),
        rider_socket.send,
        rider_socket.subscribe,
        sessions,
    )
    await as_rider.handle(
        {"type": "location.update", "trip_id": trip["id"], "lat": 7.0, "lon": -72.0}
    )
    assert rider_socket.sent[-1]["code"] == "NOT_FOUND"

    # Al iniciar y terminar el viaje la conexion empieza y deja de escuchar su ubicacion.
    unsubscribed: list[str] = []

    async def unsubscribe(channel: str) -> None:
        unsubscribed.append(channel)

    follower = LiveConnection(
        passenger.id,
        passenger.full_name,
        set(),
        rider_socket.send,
        rider_socket.subscribe,
        sessions,
        unsubscribe,
    )
    await follower.on_event(json.dumps({"type": "trip.started", "trip_id": trip["id"]}))
    assert location_channel(trip_id) in rider_socket.subscribed
    await follower.on_event(json.dumps({"type": "trip.finished", "trip_id": trip["id"]}))
    assert unsubscribed == [location_channel(trip_id)]


async def test_emergency_alerts_admins_and_is_handled_with_audit(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
    events: EventLog,
    locations: MemoryLocations,
) -> None:
    admin = await make_user(UserRole.ADMIN)
    passenger = await make_user(UserRole.PASSENGER)
    trip = await started_trip(routing_api, db, driver, places, passenger)
    locations.values[location_key(trip["id"])] = json.dumps(
        {"lat": 7.38, "lon": -72.648, "at": utcnow().isoformat()}
    )

    response = await routing_api.post(
        f"{API}/trips/{trip['id']}/emergency",
        json={"note": "El conductor se desvio"},
        headers=auth(passenger),
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["phone"] == "123"
    assert report["emergency"]["lat"] == 7.38  # ultima ubicacion del viaje
    assert (await kinds(db, admin))[-1] == "emergency_alert"
    alerts = await events.on(ADMIN_CHANNEL)
    assert alerts[0]["emergency"]["note"] == "El conductor se desvio"

    stranger = await make_user(UserRole.PASSENGER)
    response = await routing_api.post(
        f"{API}/trips/{trip['id']}/emergency", json={}, headers=auth(stranger)
    )
    assert response.status_code == 404
    assert (
        await routing_api.get(f"{API}/admin/emergencies", headers=auth(passenger))
    ).status_code == 403

    listed = (await routing_api.get(f"{API}/admin/emergencies", headers=auth(admin))).json()
    assert [e["id"] for e in listed] == [report["emergency"]["id"]]
    url = f"{API}/admin/emergencies/{report['emergency']['id']}/handle"
    response = await routing_api.post(
        url, json={"resolution": "Llamamos a la pasajera, esta bien"}, headers=auth(admin)
    )
    assert response.status_code == 200, response.text
    assert response.json()["handled_at"] is not None
    response = await routing_api.post(url, json={"resolution": "Otra vez"}, headers=auth(admin))
    assert response.json()["code"] == "EMERGENCY_HANDLED"
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "emergency.handle"))
    assert audit is not None and audit.actor_id == admin.id
    assert (await routing_api.get(f"{API}/admin/emergencies", headers=auth(admin))).json() == []


async def test_trusted_contacts_are_private_and_limited(
    api: AsyncClient, make_user: UserFactory
) -> None:
    owner, other = await make_user(UserRole.PASSENGER), await make_user(UserRole.PASSENGER)
    url = f"{API}/me/trusted-contacts"
    response = await api.post(
        url,
        json={"name": " Mama ", "phone": "+57 300 123-4567", "relationship": "Madre"},
        headers=auth(owner),
    )
    assert response.status_code == 201, response.text
    contact = response.json()
    assert contact == {
        "id": contact["id"],
        "name": "Mama",
        "phone": "+573001234567",
        "relationship": "Madre",
    }
    response = await api.post(url, json={"name": "Primo", "phone": "abc"}, headers=auth(owner))
    assert response.status_code == 422

    assert (await api.get(url, headers=auth(other))).json() == []
    response = await api.patch(
        f"{url}/{contact['id']}", json={"name": "Otro nombre"}, headers=auth(other)
    )
    assert response.status_code == 404
    response = await api.patch(
        f"{url}/{contact['id']}", json={"phone": "3109876543"}, headers=auth(owner)
    )
    assert response.json()["phone"] == "3109876543"

    for n in range(4):
        await api.post(
            url, json={"name": f"Contacto {n}", "phone": f"30000000{n}"}, headers=auth(owner)
        )
    response = await api.post(
        url, json={"name": "Sexto", "phone": "3000000099"}, headers=auth(owner)
    )
    assert response.json()["code"] == "TRUSTED_CONTACTS_LIMIT"
    response = await api.delete(f"{url}/{contact['id']}", headers=auth(owner))
    assert response.status_code == 204
    assert len((await api.get(url, headers=auth(owner))).json()) == 4
