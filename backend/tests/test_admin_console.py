"""Panel de administracion: permisos por rol, gestion de cuentas, viajes, moderacion,
indicadores y auditoria de cada accion."""

import re
import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today, utcnow
from app.core.enums import BookingStatus, TripStatus, UserRole, UserStatus
from app.main import create_app
from app.modules.admin.users import end_expired_account_suspensions
from app.modules.audit.models import AuditLog
from app.modules.auth.models import UserSession
from app.modules.bookings.models import Booking
from app.modules.chat.models import Message
from app.modules.places.models import Place
from app.modules.ratings.models import Rating
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth
from tests.test_bookings import book, decide, kinds, published
from tests.test_ratings import DRIVER_SCORES, finished_trip, rate

pytestmark = pytest.mark.integration

# Rutas solo del superadmin (configuracion global, administradores y auditoria).
SUPERADMIN_ONLY = re.compile(
    r"^/api/v1/admin/(settings|semesters|places|pico-placa|legal|audit|admins|users/\{user_id\}/role)"
)


def admin_routes() -> list[tuple[str, str]]:
    """Todas las rutas /admin documentadas en OpenAPI (incluye los routers anidados)."""
    paths = create_app().openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith(f"{API}/admin")
        for method in operations
    )


def concrete(path: str) -> str:
    """Rellena los parametros de ruta con valores validos."""
    path = path.replace("{key}", "search_radius_meters")
    return re.sub(r"\{[a-z_]+\}", str(uuid.uuid4()), path)


async def call(api: AsyncClient, method: str, path: str, user: User):  # type: ignore[no-untyped-def]
    return await api.request(method, concrete(path), json={}, headers=auth(user))


async def audit_actions(db: AsyncSession) -> list[str]:
    return list((await db.scalars(select(AuditLog.action).order_by(AuditLog.created_at))).all())


async def test_no_role_reaches_what_is_not_theirs(api: AsyncClient, make_user: UserFactory) -> None:
    routes = admin_routes()
    assert len(routes) > 30
    passenger = await make_user(UserRole.PASSENGER)
    driver = await make_user(UserRole.DRIVER)
    admin = await make_user(UserRole.ADMIN)
    superadmin = await make_user(UserRole.SUPERADMIN)
    for method, path in routes:
        for user in (passenger, driver):
            response = await call(api, method, path, user)
            assert response.status_code == 403, (method, path, user.role)
        response = await api.request(method, concrete(path), json={})
        assert response.status_code == 401, (method, path)
        response = await call(api, method, path, admin)
        if SUPERADMIN_ONLY.match(path):
            assert response.status_code == 403, (method, path, "admin")
        else:
            assert response.status_code != 403, (method, path, "admin")
        response = await call(api, method, path, superadmin)
        assert response.status_code not in (401, 403), (method, path, "superadmin")


async def test_suspend_reinstate_and_block_accounts(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    admin = await make_user(UserRole.ADMIN)
    passenger = await make_user(UserRole.PASSENGER)
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")

    url = f"{API}/admin/users/{passenger.id}"
    response = await routing_api.post(
        f"{url}/suspend",
        json={"reason": "Reportes de mal comportamiento", "days": 3},
        headers=auth(admin),
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "suspended"
    assert detail["suspension_reason"] == "Reportes de mal comportamiento"
    assert detail["suspended_until"] is not None
    assert detail["active_bookings"] == 0
    row = await db.get(Booking, booking["id"])
    assert row is not None
    await db.refresh(row)
    assert row.status == BookingStatus.CANCELLED_BY_PASSENGER
    assert (await kinds(db, passenger))[-1] == "account_suspended"
    assert "booking_cancelled_by_passenger" in await kinds(db, driver[0])
    # Suspendida no usa la app, pero ve su estado.
    response = await routing_api.get(f"{API}/bookings/mine", headers=auth(passenger))
    assert response.json()["code"] == "ACCOUNT_NOT_ACTIVE"
    assert (await routing_api.get(f"{API}/users/me", headers=auth(passenger))).status_code == 200
    response = await routing_api.post(
        f"{url}/suspend", json={"reason": "Otra vez"}, headers=auth(admin)
    )
    assert response.json()["code"] == "USER_STATUS_INVALID"

    response = await routing_api.post(f"{url}/reinstate", json={}, headers=auth(admin))
    assert response.json()["status"] == "active"
    assert (await kinds(db, passenger))[-1] == "account_reinstated"

    # Bloquear: cierra sesiones y cancela los viajes del conductor con aviso a pasajeros.
    db.add(
        UserSession(
            user_id=driver[0].id,
            refresh_token_hash="x" * 64,
            device_label="Prueba",
            expires_at=utcnow() + timedelta(days=1),
            last_seen_at=utcnow(),
        )
    )
    other = await make_user(UserRole.PASSENGER)
    second_trip = await published(
        routing_api, driver, places, departs_at=(utcnow() + timedelta(days=2)).isoformat()
    )
    second = (await book(routing_api, other, second_trip["id"], places)).json()
    await decide(routing_api, driver[0], second["id"], "accept")
    response = await routing_api.post(
        f"{API}/admin/users/{driver[0].id}/block",
        json={"reason": "Conduccion peligrosa reportada"},
        headers=auth(admin),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "blocked"
    trip_row = await db.get(Trip, second_trip["id"])
    assert trip_row is not None
    await db.refresh(trip_row)
    assert trip_row.status == TripStatus.CANCELLED_BY_DRIVER
    assert (await kinds(db, other))[-1] == "booking_cancelled_by_driver"
    sessions = (
        await db.scalars(select(UserSession).where(UserSession.user_id == driver[0].id))
    ).all()
    assert all(s.revoked_at is not None for s in sessions)
    assert (await routing_api.get(f"{API}/users/me", headers=auth(driver[0]))).status_code == 401

    actions = await audit_actions(db)
    assert {"user.suspend", "user.reinstate", "user.block"} <= set(actions)


async def test_who_can_manage_whom(api: AsyncClient, make_user: UserFactory) -> None:
    admin, other_admin = await make_user(UserRole.ADMIN), await make_user(UserRole.ADMIN)
    superadmin = await make_user(UserRole.SUPERADMIN)
    body = {"reason": "Prueba de permisos"}
    for actor, target, expected in (
        (admin, admin, 403),  # a si mismo
        (admin, other_admin, 403),  # otro administrador
        (admin, superadmin, 403),
        (superadmin, superadmin, 403),
        (superadmin, other_admin, 200),
    ):
        response = await api.post(
            f"{API}/admin/users/{target.id}/suspend", json=body, headers=auth(actor)
        )
        assert response.status_code == expected, (actor.role, target.role)


async def test_temporary_suspension_ends_alone_and_bans_can_be_lifted(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    admin = await make_user(UserRole.ADMIN)
    passenger = await make_user(UserRole.PASSENGER)
    await api.post(
        f"{API}/admin/users/{passenger.id}/suspend",
        json={"reason": "Suspension corta", "days": 1},
        headers=auth(admin),
    )
    await db.refresh(passenger)
    assert passenger.suspended_until is not None
    assert await end_expired_account_suspensions(db) == 0
    passenger.suspended_until = utcnow() - timedelta(minutes=1)
    await db.flush()
    assert await end_expired_account_suspensions(db) == 1
    await db.refresh(passenger)
    assert passenger.status == UserStatus.ACTIVE
    assert "user.reinstate_auto" in await audit_actions(db)

    passenger.booking_ban_until = utcnow() + timedelta(days=6)
    await db.flush()
    detail = (await api.get(f"{API}/admin/users/{passenger.id}", headers=auth(admin))).json()
    assert detail["booking_ban_until"] is not None
    response = await api.post(
        f"{API}/admin/users/{passenger.id}/lift-ban",
        json={"reason": "No-show mal marcado"},
        headers=auth(admin),
    )
    assert response.json()["booking_ban_until"] is None
    assert (await kinds(db, passenger))[-1] == "booking_ban_lifted"
    assert "suspension.end" in await audit_actions(db)


async def test_trip_monitoring_chat_and_moderation(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    admin = await make_user(UserRole.ADMIN)
    passenger = await make_user(UserRole.PASSENGER)
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")
    chat = (await routing_api.get(f"{API}/trips/{trip['id']}", headers=auth(passenger))).json()[
        "chat_id"
    ]
    await routing_api.post(
        f"{API}/conversations/{chat}/messages",
        json={"body": "Mensaje ofensivo"},
        headers=auth(passenger),
    )

    listed = (
        await routing_api.get(
            f"{API}/admin/trips",
            params={
                "q": driver[0].full_name.split()[0],
                "day": (local_today() + timedelta(days=1)).isoformat(),
            },
            headers=auth(admin),
        )
    ).json()
    assert [t["id"] for t in listed["items"]] == [trip["id"]]
    assert listed["items"][0]["seats_booked"] == 1
    detail = (await routing_api.get(f"{API}/admin/trips/{trip['id']}", headers=auth(admin))).json()
    assert detail["plate"] == "ABC123"
    assert detail["bookings"][0]["passenger_name"] == passenger.full_name
    assert detail["has_chat"] is True

    messages = (
        await routing_api.get(f"{API}/admin/trips/{trip['id']}/messages", headers=auth(admin))
    ).json()
    assert [m["body"] for m in messages] == ["Mensaje ofensivo"]
    response = await routing_api.post(
        f"{API}/admin/messages/{messages[0]['id']}/hide", json={"hidden": True}, headers=auth(admin)
    )
    assert response.json()["hidden"] is True
    seen = (
        await routing_api.get(f"{API}/conversations/{chat}/messages", headers=auth(driver[0]))
    ).json()
    assert seen == []
    hidden = await db.get(Message, uuid.UUID(messages[0]["id"]))
    assert hidden is not None and hidden.hidden

    response = await routing_api.post(
        f"{API}/admin/trips/{trip['id']}/cancel",
        json={"reason": "Queja de seguridad"},
        headers=auth(admin),
    )
    assert response.json()["status"] == "cancelled_by_driver"
    assert (await kinds(db, driver[0]))[-1] == "trip_cancelled_by_admin"
    assert (await kinds(db, passenger))[-1] == "booking_cancelled_by_driver"
    assert {"chat.view", "message.hide", "trip.cancel"} <= set(await audit_actions(db))


async def test_rating_comments_moderation_and_overview(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    admin = await make_user(UserRole.ADMIN)
    rider = await make_user(UserRole.PASSENGER)
    trip = await finished_trip(routing_api, db, driver, places, [rider])
    await rate(
        routing_api, rider, trip["id"], driver[0], DRIVER_SCORES, comment="Comentario grosero"
    )

    listed = (await routing_api.get(f"{API}/admin/ratings", headers=auth(admin))).json()["items"]
    assert listed[0]["comment"] == "Comentario grosero"
    assert listed[0]["author_name"] == rider.full_name
    response = await routing_api.post(
        f"{API}/admin/ratings/{listed[0]['id']}/hide", json={"hidden": True}, headers=auth(admin)
    )
    assert response.json()["hidden"] is True
    public = (
        await routing_api.get(f"{API}/users/{driver[0].id}/ratings", headers=auth(rider))
    ).json()
    assert public["items"][0]["comment"] is None
    assert public["items"][0]["average"] == 4.5
    rating = await db.scalar(select(Rating).where(Rating.trip_id == trip["id"]))
    assert rating is not None and rating.hidden
    assert "rating.hide" in await audit_actions(db)

    overview: dict[str, Any] = (
        await routing_api.get(f"{API}/admin/stats", headers=auth(admin))
    ).json()
    assert overview["trips_completed"] == 1
    assert len(overview["trips_per_day"]) == 30
    assert sum(overview["trips_per_hour"]) == 1
    assert overview["top_routes"][0] == {
        "origin": "Ciudad Universitaria",
        "destination": "Terminal",
        "count": 1,
    }
    assert overview["rating_distribution"] == [0, 0, 0, 0, 1]
    assert overview["occupancy"] == pytest.approx(1 / 3, abs=0.001)
    roles = {item["key"]: item["count"] for item in overview["users"]}
    assert roles["passenger:active"] >= 1


async def test_audit_log_names_who_acted(
    api: AsyncClient, make_user: UserFactory, su_headers: dict[str, str], superadmin: User
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    await api.post(
        f"{API}/admin/users/{passenger.id}/suspend",
        json={"reason": "Prueba de auditoria"},
        headers=su_headers,
    )
    entries = (await api.get(f"{API}/admin/audit", headers=su_headers)).json()["items"]
    entry = next(e for e in entries if e["action"] == "user.suspend")
    assert entry["actor_name"] == superadmin.full_name
    assert entry["entity_id"] == str(passenger.id)
