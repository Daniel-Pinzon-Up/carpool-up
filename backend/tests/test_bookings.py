"""Reservas: solicitud, decision del conductor, cancelaciones, cambios del viaje y jobs."""

from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import LOCAL_TZ, utcnow
from app.core.enums import BookingStatus, Sex, SuspensionKind, UserRole
from app.modules.bookings.jobs import auto_cancel_late_driver, expire_pending
from app.modules.bookings.models import Booking
from app.modules.notifications.models import Notification
from app.modules.places.models import Place
from app.modules.suspensions.models import Suspension
from app.modules.trips.models import Trip
from app.modules.trips.service import recheck_pico_placa
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.waitlist.models import WaitlistEntry
from app.modules.waitlist.offers import run_waitlist
from tests.conftest import API, UserFactory, auth, make_driver
from tests.test_trips import pico_placa, publish, trip_body

pytestmark = pytest.mark.integration


async def published(
    api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place], **overrides: Any
) -> dict[str, Any]:
    user, vehicle = driver
    response = await publish(api, user, trip_body(places, vehicle, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def book(
    api: AsyncClient,
    passenger: User,
    trip_id: str,
    places: list[Place],
    *,
    seats: int = 1,
    pickup: int = 0,
    dropoff: int = 2,
    preferences: dict[str, bool] | None = None,
) -> httpx.Response:
    return await api.post(
        f"{API}/trips/{trip_id}/bookings",
        json={
            "seats": seats,
            "pickup_place_id": str(places[pickup].id),
            "dropoff_place_id": str(places[dropoff].id),
            "preferences": preferences or {},
        },
        headers=auth(passenger),
    )


async def decide(api: AsyncClient, driver: User, booking_id: str, action: str) -> httpx.Response:
    return await api.post(f"{API}/bookings/{booking_id}/{action}", json={}, headers=auth(driver))


async def cancel(
    api: AsyncClient, passenger: User, booking_id: str, reason: str | None = None
) -> httpx.Response:
    return await api.post(
        f"{API}/bookings/{booking_id}/cancel", json={"reason": reason}, headers=auth(passenger)
    )


async def kinds(db: AsyncSession, user: User) -> list[str]:
    rows = await db.scalars(
        select(Notification.kind)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at)
    )
    return list(rows.all())


async def trip_view(api: AsyncClient, user: User, trip_id: str) -> dict[str, Any]:
    response = await api.get(f"{API}/trips/{trip_id}", headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def passenger(make_user: UserFactory) -> User:
    return await make_user(UserRole.PASSENGER, sex=Sex.FEMALE)


# --- Solicitud ------------------------------------------------------------------------


async def test_request_stays_pending_without_holding_seats(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip = await published(routing_api, driver, places)
    response = await book(routing_api, passenger, trip["id"], places, seats=2)
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "requested"
    assert booking["amount"] == 4000
    assert booking["pickup"]["kind"] == "stop"
    assert booking["pickup"]["name"] == "Ciudad Universitaria"
    assert booking["dropoff"]["name"] == "Terminal"
    assert booking["trip"]["vehicle"]["plate"] is None
    assert booking["payment_note"] is None
    assert booking["free_cancel"] is True

    view = await trip_view(routing_api, passenger, trip["id"])
    assert view["seats_available"] == 3
    assert view["my_booking"]["status"] == "requested"
    assert view["passengers"] == []
    assert await kinds(db, driver[0]) == ["booking_requested"]
    driver_view = await trip_view(routing_api, driver[0], trip["id"])
    assert driver_view["pending_requests"] == 1


async def test_request_validations(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    trip = await published(
        routing_api,
        driver,
        places,
        rules=[
            {"kind": "women_only", "value": "allowed"},
            {"kind": "pets", "value": "not_allowed"},
        ],
    )
    man = await make_user(UserRole.PASSENGER, sex=Sex.MALE)
    other_driver, _ = await make_driver(db, make_user, plate="XYZ789")

    assert (await book(routing_api, other_driver, trip["id"], places)).status_code == 403
    response = await book(routing_api, man, trip["id"], places)
    assert response.json()["code"] == "WOMEN_ONLY_TRIP"
    response = await book(routing_api, passenger, trip["id"], places, preferences={"pets": True})
    assert response.status_code == 422
    assert response.json()["details"]["preferences"] == ["pets"]
    response = await book(routing_api, passenger, trip["id"], places, pickup=2, dropoff=0)
    assert response.json()["code"] == "POINTS_OFF_ROUTE"
    response = await book(routing_api, passenger, trip["id"], places, seats=4)
    assert response.json()["code"] == "TRIP_FULL"
    assert response.json()["details"]["seats_available"] == 3

    assert (await book(routing_api, passenger, trip["id"], places)).status_code == 201
    response = await book(routing_api, passenger, trip["id"], places)
    assert response.json()["code"] == "BOOKING_EXISTS"


async def test_suspended_passenger_cannot_book(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip = await published(routing_api, driver, places)
    db.add(
        Suspension(
            user_id=passenger.id,
            kind=SuspensionKind.BOOKING_BAN,
            reason="3 no-shows",
            starts_at=utcnow() - timedelta(days=1),
            ends_at=utcnow() + timedelta(days=6),
        )
    )
    await db.flush()
    response = await book(routing_api, passenger, trip["id"], places)
    assert response.status_code == 403
    assert response.json()["code"] == "BOOKING_SUSPENDED"


async def test_bookings_cannot_overlap_in_time(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    first = await published(routing_api, driver, places)
    second = await published(routing_api, await make_driver(db, make_user, plate="XYZ789"), places)
    assert (await book(routing_api, passenger, first["id"], places)).status_code == 201
    response = await book(routing_api, passenger, second["id"], places)
    assert response.status_code == 409
    assert response.json()["code"] == "BOOKING_OVERLAP"


# --- Decision del conductor -------------------------------------------------------------


async def test_accept_holds_seats_and_reveals_plate_and_payment_note(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    driver[0].payment_note = "Nequi 300 000 0000"
    await db.flush()
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places, seats=2)).json()
    stranger = await make_user(UserRole.PASSENGER)

    # Solo el conductor del viaje decide.
    assert (await decide(routing_api, stranger, booking["id"], "accept")).status_code == 403
    response = await decide(routing_api, driver[0], booking["id"], "accept")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"
    assert (await decide(routing_api, driver[0], booking["id"], "accept")).json()["code"] == (
        "BOOKING_NOT_PENDING"
    )

    mine = (
        await routing_api.get(f"{API}/bookings/{booking['id']}", headers=auth(passenger))
    ).json()
    assert mine["trip"]["vehicle"]["plate"] == "ABC123"
    assert mine["payment_note"] == "Nequi 300 000 0000"
    view = await trip_view(routing_api, passenger, trip["id"])
    assert view["seats_available"] == 1
    assert view["vehicle"]["plate"] == "ABC123"
    assert view["passengers"] == [
        {
            "id": str(passenger.id),
            "full_name": passenger.full_name,
            "seats": 2,
            "pickup_name": None,
            "pickup_eta": None,
        }
    ]
    driver_view = await trip_view(routing_api, driver[0], trip["id"])
    assert driver_view["passengers"][0]["pickup_name"] == "Ciudad Universitaria"
    # Otro pasajero no ve placa, datos de pago ni companeros.
    outsider = await trip_view(routing_api, stranger, trip["id"])
    assert outsider["vehicle"]["plate"] is None
    assert outsider["payment_note"] is None
    assert outsider["passengers"] == []
    assert "email" not in str(mine["passenger"])
    assert "booking_accepted" in await kinds(db, passenger)

    # Con un puesto libre no se aceptan dos mas.
    late = await make_user(UserRole.PASSENGER)
    second = (await book(routing_api, late, trip["id"], places, seats=1)).json()
    third_user = await make_user(UserRole.PASSENGER)
    third = (await book(routing_api, third_user, trip["id"], places, seats=1)).json()
    assert (await decide(routing_api, driver[0], second["id"], "accept")).status_code == 200
    response = await decide(routing_api, driver[0], third["id"], "accept")
    assert response.json()["code"] == "TRIP_FULL"


async def test_reject_and_driver_inbox(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    inbox = (await routing_api.get(f"{API}/bookings/inbox", headers=auth(driver[0]))).json()
    assert [b["id"] for b in inbox["bookings"]] == [booking["id"]]
    assert inbox["bookings"][0]["passenger"]["full_name"] == passenger.full_name
    assert (
        await routing_api.get(f"{API}/bookings/inbox", headers=auth(passenger))
    ).status_code == 403

    response = await routing_api.post(
        f"{API}/bookings/{booking['id']}/reject",
        json={"reason": "Voy lleno de equipaje"},
        headers=auth(driver[0]),
    )
    assert response.json()["status"] == "rejected"
    assert response.json()["cancel_reason"] == "Voy lleno de equipaje"
    assert "booking_rejected" in await kinds(db, passenger)
    inbox = (await routing_api.get(f"{API}/bookings/inbox", headers=auth(driver[0]))).json()
    assert inbox["bookings"] == []
    # Rechazada, puede volver a pedir.
    assert (await book(routing_api, passenger, trip["id"], places)).status_code == 201


# --- Cancelaciones ----------------------------------------------------------------------


async def test_passenger_withdraws_request_and_cancels_early(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip = await published(routing_api, driver, places)
    first = (await book(routing_api, passenger, trip["id"], places)).json()
    response = await cancel(routing_api, passenger, first["id"])
    assert response.json()["status"] == "cancelled_by_passenger"
    assert (await kinds(db, driver[0]))[-1] == "booking_withdrawn"

    second = (await book(routing_api, passenger, trip["id"], places, seats=3)).json()
    await decide(routing_api, driver[0], second["id"], "accept")
    response = await cancel(routing_api, passenger, second["id"])
    assert response.json()["status"] == "cancelled_by_passenger"
    assert (await trip_view(routing_api, passenger, trip["id"]))["seats_available"] == 3
    assert (await kinds(db, driver[0]))[-1] == "booking_cancelled_by_passenger"
    response = await cancel(routing_api, passenger, second["id"])
    assert response.json()["code"] == "BOOKING_NOT_CANCELLABLE"


async def test_late_cancellation_needs_driver_decision(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    soon = (utcnow() + timedelta(minutes=60)).isoformat()
    trip = await published(routing_api, driver, places, departs_at=soon)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")
    mine = (
        await routing_api.get(f"{API}/bookings/{booking['id']}", headers=auth(passenger))
    ).json()
    assert mine["free_cancel"] is False

    response = await cancel(routing_api, passenger, booking["id"])
    assert response.status_code == 422
    assert response.json()["code"] == "CANCEL_REASON_REQUIRED"
    response = await cancel(routing_api, passenger, booking["id"], "Me enferme hoy")
    assert response.json()["status"] == "cancel_requested"
    request = response.json()["cancellation"]
    assert request["status"] == "pending"
    assert (await kinds(db, driver[0]))[-1] == "cancellation_requested"
    # Mientras tanto el cupo sigue ocupado.
    assert (await trip_view(routing_api, passenger, trip["id"]))["seats_available"] == 2
    response = await cancel(routing_api, passenger, booking["id"], "Me enferme hoy")
    assert response.json()["code"] == "CANCELLATION_PENDING"

    inbox = (await routing_api.get(f"{API}/bookings/inbox", headers=auth(driver[0]))).json()
    assert [b["id"] for b in inbox["cancellations"]] == [booking["id"]]

    response = await routing_api.post(
        f"{API}/cancellation-requests/{request['id']}/reject", headers=auth(driver[0])
    )
    assert response.json()["status"] == "accepted"
    assert response.json()["cancellation"]["status"] == "rejected"
    assert (await kinds(db, passenger))[-1] == "cancellation_rejected"

    request = (await cancel(routing_api, passenger, booking["id"], "Sigo enfermo")).json()
    response = await routing_api.post(
        f"{API}/cancellation-requests/{request['cancellation']['id']}/accept",
        headers=auth(driver[0]),
    )
    assert response.json()["status"] == "cancelled_by_passenger"
    assert (await kinds(db, passenger))[-1] == "cancellation_accepted"
    assert (await trip_view(routing_api, passenger, trip["id"]))["seats_available"] == 3
    response = await routing_api.post(
        f"{API}/cancellation-requests/{request['cancellation']['id']}/accept",
        headers=auth(driver[0]),
    )
    assert response.json()["code"] == "CANCELLATION_NOT_PENDING"


async def test_late_driver_lets_passengers_cancel_and_job_cancels(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    trip = await published(routing_api, driver, places)
    first = (await book(routing_api, passenger, trip["id"], places)).json()
    other = await make_user(UserRole.PASSENGER)
    second = (await book(routing_api, other, trip["id"], places)).json()
    for booking in (first, second):
        await decide(routing_api, driver[0], booking["id"], "accept")
    row = await db.get(Trip, trip["id"])
    assert row is not None
    row.departs_at = utcnow() - timedelta(minutes=16)
    await db.flush()

    # El pasajero cancela sin pedir permiso aunque falten menos de 2 horas.
    assert (await cancel(routing_api, passenger, first["id"])).json()["status"] == (
        "cancelled_by_passenger"
    )
    assert await auto_cancel_late_driver(db) == 1
    booking = await db.get(Booking, second["id"])
    assert booking is not None
    await db.refresh(booking)
    assert booking.status == BookingStatus.AUTO_CANCELLED_LATE
    assert (await kinds(db, other))[-1] == "booking_auto_cancelled_late"


async def test_driver_cancel_and_pico_placa_end_bookings(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")
    response = await routing_api.post(
        f"{API}/trips/{trip['id']}/cancel",
        json={"reason": "Se dano el carro"},
        headers=auth(driver[0]),
    )
    assert response.status_code == 200
    mine = (
        await routing_api.get(f"{API}/bookings/{booking['id']}", headers=auth(passenger))
    ).json()
    assert mine["status"] == "cancelled_by_driver"
    assert mine["cancel_reason"] == "Se dano el carro"
    assert (await kinds(db, passenger))[-1] == "booking_cancelled_by_driver"
    # El pasajero sigue viendo el viaje cancelado en su historial.
    assert (await trip_view(routing_api, passenger, trip["id"]))["status"] == "cancelled_by_driver"

    second_trip = await published(routing_api, driver, places)
    second = (await book(routing_api, passenger, second_trip["id"], places)).json()
    departs = (await db.get(Trip, second_trip["id"])).departs_at  # type: ignore[union-attr]
    await pico_placa(db, departs.astimezone(LOCAL_TZ).weekday(), [3])
    result = await recheck_pico_placa(db)
    assert result.cancelled == 1
    mine = (await routing_api.get(f"{API}/bookings/{second['id']}", headers=auth(passenger))).json()
    assert mine["status"] == "auto_cancelled_pico_placa"
    assert (await kinds(db, passenger))[-1] == "booking_pico_placa_cancelled"


async def test_expire_pending_requests_job(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
) -> None:
    trip = await published(routing_api, driver, places)
    booking = (await book(routing_api, passenger, trip["id"], places)).json()
    row = await db.get(Booking, booking["id"])
    assert row is not None
    row.expires_at = utcnow() - timedelta(minutes=1)
    await db.flush()
    result = await expire_pending(db)
    assert result["bookings"] == 1
    await db.refresh(row)
    assert row.status == BookingStatus.EXPIRED
    assert (await kinds(db, passenger))[-1] == "booking_expired"
    assert (await decide(routing_api, driver[0], booking["id"], "accept")).status_code == 409


# --- Cambios del viaje ----------------------------------------------------------------


async def test_trip_changes_respect_bookings(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    soon = utcnow() + timedelta(minutes=90)
    trip = await published(routing_api, driver, places, departs_at=soon.isoformat())
    booking = (await book(routing_api, passenger, trip["id"], places, seats=2)).json()
    await decide(routing_api, driver[0], booking["id"], "accept")
    man = await make_user(UserRole.PASSENGER, sex=Sex.MALE)
    await book(routing_api, man, trip["id"], places)

    url = f"{API}/trips/{trip['id']}"
    response = await routing_api.patch(url, json={"seats": 1}, headers=auth(driver[0]))
    assert response.json()["code"] == "SEATS_BELOW_BOOKED"
    response = await routing_api.patch(
        url, json={"rules": [{"kind": "women_only", "value": "allowed"}]}, headers=auth(driver[0])
    )
    assert response.json()["code"] == "WOMEN_ONLY_CONFLICT"

    later = soon + timedelta(minutes=10)
    response = await routing_api.patch(
        url, json={"departs_at": later.isoformat()}, headers=auth(driver[0])
    )
    assert response.status_code == 200, response.text
    mine = (
        await routing_api.get(f"{API}/bookings/{booking['id']}", headers=auth(passenger))
    ).json()
    assert mine["penalty_free"] is True
    assert mine["free_cancel"] is True
    # El punto de encuentro se recalcula con la nueva hora.
    assert abs((datetime.fromisoformat(mine["pickup"]["eta"]) - later).total_seconds()) < 1
    assert "trip_changed" in await kinds(db, passenger)
    assert (await cancel(routing_api, passenger, booking["id"])).json()["status"] == (
        "cancelled_by_passenger"
    )


# --- Lista de espera ------------------------------------------------------------------


async def test_waitlist_offers_freed_seats_in_order(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    trip = await published(routing_api, driver, places, seats=1)
    holder = (await book(routing_api, passenger, trip["id"], places)).json()
    second, third = await make_user(UserRole.PASSENGER), await make_user(UserRole.PASSENGER)
    body = {
        "seats": 1,
        "pickup_place_id": str(places[1].id),
        "dropoff_place_id": str(places[2].id),
    }
    url = f"{API}/trips/{trip['id']}/waitlist"

    # Con cupo libre no hace falta la fila.
    response = await routing_api.post(url, json=body, headers=auth(second))
    assert response.json()["code"] == "WAITLIST_NOT_NEEDED"
    await decide(routing_api, driver[0], holder["id"], "accept")
    response = await book(routing_api, second, trip["id"], places)
    assert response.json()["code"] == "TRIP_FULL"

    first_entry = (await routing_api.post(url, json=body, headers=auth(second))).json()
    assert first_entry["status"] == "waiting"
    assert first_entry["ahead"] == 0
    second_entry = (await routing_api.post(url, json=body, headers=auth(third))).json()
    assert second_entry["ahead"] == 1
    assert (await routing_api.post(url, json=body, headers=auth(third))).json()["code"] == (
        "WAITLIST_EXISTS"
    )
    view = await trip_view(routing_api, third, trip["id"])
    assert view["my_waitlist"]["status"] == "waiting"

    # Se libera el puesto: se ofrece al primero de la fila.
    await cancel(routing_api, passenger, holder["id"])
    mine = (await routing_api.get(f"{API}/waitlist/mine", headers=auth(second))).json()
    assert mine[0]["status"] == "offered"
    assert mine[0]["offer_expires_at"] is not None
    assert (await kinds(db, second))[-1] == "waitlist_offer"
    third_list = (await routing_api.get(f"{API}/waitlist/mine", headers=auth(third))).json()
    assert third_list[0]["status"] == "waiting"

    # Rechaza la oferta: pasa al siguiente, que confirma y queda como solicitud.
    response = await routing_api.post(
        f"{API}/waitlist/{first_entry['id']}/decline", headers=auth(second)
    )
    assert response.json()["status"] == "left"
    response = await routing_api.post(
        f"{API}/waitlist/{second_entry['id']}/confirm", headers=auth(third)
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "converted"
    booking = await db.get(Booking, response.json()["booking_id"])
    assert booking is not None
    assert booking.status == BookingStatus.REQUESTED
    assert booking.pickup_name == "Sede Casona"
    response = await routing_api.post(
        f"{API}/waitlist/{second_entry['id']}/confirm", headers=auth(third)
    )
    assert response.json()["code"] == "WAITLIST_OFFER_EXPIRED"


async def test_waitlist_offer_expires_and_moves_on(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passenger: User,
    make_user: UserFactory,
) -> None:
    trip = await published(routing_api, driver, places, seats=1)
    holder = (await book(routing_api, passenger, trip["id"], places)).json()
    await decide(routing_api, driver[0], holder["id"], "accept")
    second, third = await make_user(UserRole.PASSENGER), await make_user(UserRole.PASSENGER)
    body = {"pickup_place_id": str(places[0].id), "dropoff_place_id": str(places[2].id)}
    url = f"{API}/trips/{trip['id']}/waitlist"
    first_entry = (await routing_api.post(url, json=body, headers=auth(second))).json()
    second_entry = (await routing_api.post(url, json=body, headers=auth(third))).json()
    await cancel(routing_api, passenger, holder["id"])

    entry = await db.get(WaitlistEntry, first_entry["id"])
    assert entry is not None
    entry.offer_expires_at = utcnow() - timedelta(seconds=1)
    await db.flush()
    result = await run_waitlist(db)
    assert result == {"expired": 1, "offered": 1}
    assert (await kinds(db, second))[-1] == "waitlist_offer_expired"
    later = await db.get(WaitlistEntry, second_entry["id"])
    assert later is not None
    await db.refresh(later)
    assert later.status == "offered"

    # Salir de la fila con una oferta abierta tampoco deja el cupo sin ofrecer.
    response = await routing_api.delete(url, headers=auth(third))
    assert response.status_code == 204
    assert (await routing_api.delete(url, headers=auth(third))).status_code == 404
