"""Eliminacion de la propia cuenta (Ley 1581): anonimiza, borra lo personal y conserva lo
operativo; retira a la persona de sus viajes futuros y cierra sus sesiones."""

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, DocKind, ReviewStatus, TripStatus, UserRole
from app.core.storage import storage_root
from app.modules.audit.models import AuditLog
from app.modules.auth.models import UserSession
from app.modules.bookings.models import Booking
from app.modules.documents.models import Document
from app.modules.notifications.models import Notification
from app.modules.places.models import Place
from app.modules.safety.models import TrustedContact
from app.modules.trips.models import Trip
from app.modules.users.deletion import DELETED_NAME, anonymous_email
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth
from tests.test_bookings import book, decide, kinds, published

PASSWORD = "clave-de-prueba-123"  # la de make_user en conftest


async def delete_account(api: AsyncClient, user: User, password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return await api.post(f"{API}/users/me/delete", json={"password": password}, headers=auth(user))


async def count(db: AsyncSession, model: type, user: User) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(model).where(model.user_id == user.id))  # type: ignore[attr-defined]
        or 0
    )


async def test_passenger_deletes_account_and_personal_data_goes_away(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    user = await make_user(UserRole.PASSENGER)
    email = user.email
    file = storage_root() / "identity" / "carnet.png"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"\x89PNG\r\n\x1a\n")
    db.add_all(
        [
            Document(
                user_id=user.id,
                kind=DocKind.STUDENT_CARD,
                file_path="identity/carnet.png",
                content_type="image/png",
                status=ReviewStatus.APPROVED,
            ),
            TrustedContact(user_id=user.id, name="Mamá", phone="+573001112233"),
            Notification(user_id=user.id, kind="role_changed", payload={}),
            UserSession(
                user_id=user.id,
                refresh_token_hash="x" * 64,
                device_label="Prueba",
                expires_at=utcnow() + timedelta(days=1),
                last_seen_at=utcnow(),
            ),
        ]
    )
    await db.flush()

    wrong = await delete_account(api, user, "otra-clave")
    assert wrong.status_code == 422
    assert wrong.json()["code"] == "PASSWORD_INCORRECT"
    assert await count(db, TrustedContact, user) == 1

    response = await delete_account(api, user)
    assert response.status_code == 204, response.text

    await db.refresh(user)
    assert user.email == anonymous_email(user.id)
    assert user.full_name == DELETED_NAME
    assert user.deleted_at is not None
    assert user.program is None
    for model in (Document, TrustedContact, Notification):
        assert await count(db, model, user) == 0
    assert not file.exists()
    sessions = (await db.scalars(select(UserSession).where(UserSession.user_id == user.id))).all()
    assert sessions and all(s.revoked_at is not None for s in sessions)
    action = await db.scalar(
        select(AuditLog.action).where(AuditLog.entity_id == str(user.id), AuditLog.entity == "user")
    )
    assert action == "user.delete_self"

    # Ya no puede entrar ni usar un token emitido antes.
    login = await api.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 401
    assert (await api.get(f"{API}/users/me", headers=auth(user))).status_code == 401


async def test_driver_deletion_cancels_future_trips_and_keeps_history(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")

    response = await delete_account(routing_api, driver[0])
    assert response.status_code == 204, response.text

    trip_row = await db.get(Trip, trip["id"])
    assert trip_row is not None
    await db.refresh(trip_row)
    # El viaje se conserva como registro, cancelado y con aviso al pasajero.
    assert trip_row.status == TripStatus.CANCELLED_BY_DRIVER
    assert (await kinds(db, passenger))[-1] == "booking_cancelled_by_driver"
    vehicle = await db.get(Vehicle, driver[1].id)
    assert vehicle is not None
    await db.refresh(vehicle)
    assert vehicle.deleted_at is not None and not vehicle.is_active


async def test_cannot_delete_during_a_trip_or_as_superadmin(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")
    trip_row = await db.get(Trip, trip["id"])
    assert trip_row is not None
    trip_row.status = TripStatus.IN_PROGRESS
    await db.flush()

    for who in (driver[0], passenger):
        response = await delete_account(routing_api, who)
        assert response.status_code == 409
        assert response.json()["code"] == "ACCOUNT_DELETE_TRIP_IN_PROGRESS"
    row = await db.get(Booking, booking["id"])
    assert row is not None and row.status == BookingStatus.ACCEPTED

    superadmin = await make_user(UserRole.SUPERADMIN)
    response = await delete_account(routing_api, superadmin)
    assert response.status_code == 409
    assert response.json()["code"] == "ACCOUNT_DELETE_NOT_ALLOWED"
