"""Suscripciones a series: rango, fechas bloqueadas, aprobacion unica y cancelaciones."""

from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, UserRole
from app.modules.bookings.jobs import expire_pending
from app.modules.bookings.models import Booking, SeriesSubscription
from app.modules.notifications.models import Notification
from app.modules.places.models import Place
from app.modules.semesters.models import Semester
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth
from tests.test_trips import next_monday, pico_placa, publish_series, series_body

pytestmark = pytest.mark.integration


async def published_series(
    api: AsyncClient, driver: tuple[User, Vehicle], places: list[Place]
) -> dict[str, Any]:
    response = await publish_series(api, driver[0], series_body(places, driver[1]))
    assert response.status_code == 201, response.text
    return response.json()


async def subscribe(
    api: AsyncClient,
    passenger: User,
    series_id: str,
    places: list[Place],
    option: int | str = 8,
    start: date | None = None,
) -> httpx.Response:
    return await api.post(
        f"{API}/series/{series_id}/subscriptions",
        json={
            "option": option,
            "start_date": (start or next_monday()).isoformat(),
            "pickup_place_id": str(places[0].id),
            "dropoff_place_id": str(places[2].id),
        },
        headers=auth(passenger),
    )


async def availability(api: AsyncClient, user: User, series_id: str) -> dict[str, Any]:
    response = await api.get(f"{API}/series/{series_id}/availability", headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()


async def sub_action(
    api: AsyncClient, user: User, sub_id: str, action: str, reason: str | None = None
) -> httpx.Response:
    return await api.post(
        f"{API}/subscriptions/{sub_id}/{action}", json={"reason": reason}, headers=auth(user)
    )


async def statuses(db: AsyncSession, subscription_id: str) -> list[BookingStatus]:
    rows = await db.scalars(
        select(Booking.status)
        .where(Booking.subscription_id == subscription_id)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


async def test_subscription_books_free_dates_and_skips_blocked_ones(
    routing_api: AsyncClient,
    db: AsyncSession,
    semester: Semester,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    await pico_placa(db, weekday=2, digits=[3])  # miercoles, placa ABC123
    series = await published_series(routing_api, driver, places)
    passenger = await make_user(UserRole.PASSENGER)
    monday = next_monday()

    days = (await availability(routing_api, passenger, series["id"]))["days"]
    by_date = {day["date"]: day for day in days}
    wednesday = by_date[(monday + timedelta(days=2)).isoformat()]
    assert wednesday["status"] == "cancelled_pico_placa"
    assert wednesday["bookable"] is False
    friday = by_date[(monday + timedelta(days=4)).isoformat()]
    assert friday["bookable"] is True

    # Alguien ocupa los 4 puestos del viernes.
    other = await make_user(UserRole.PASSENGER)
    response = await routing_api.post(
        f"{API}/trips/{friday['trip_id']}/bookings",
        json={
            "seats": 4,
            "pickup_place_id": str(places[0].id),
            "dropoff_place_id": str(places[2].id),
        },
        headers=auth(other),
    )
    await routing_api.post(
        f"{API}/bookings/{response.json()['id']}/accept", headers=auth(driver[0])
    )
    friday = {
        d["date"]: d for d in (await availability(routing_api, passenger, series["id"]))["days"]
    }[friday["date"]]
    assert friday["seats_available"] == 0
    assert friday["bookable"] is False

    response = await subscribe(routing_api, passenger, series["id"], places, option=9)
    assert response.json()["code"] == "SUBSCRIPTION_OPTION_INVALID"
    response = await subscribe(routing_api, passenger, series["id"], places)
    assert response.status_code == 201, response.text
    sub = response.json()
    assert sub["status"] == "requested"
    assert sub["from_date"] == monday.isoformat()
    assert sub["to_date"] == (monday + timedelta(days=7)).isoformat()
    assert sub["pickup_place"] == "Ciudad Universitaria"
    assert (await subscribe(routing_api, passenger, series["id"], places)).json()["code"] == (
        "SUBSCRIPTION_EXISTS"
    )

    inbox = (await routing_api.get(f"{API}/bookings/inbox", headers=auth(driver[0]))).json()
    assert [s["id"] for s in inbox["subscriptions"]] == [sub["id"]]

    response = await sub_action(routing_api, driver[0], sub["id"], "accept")
    assert response.status_code == 200, response.text
    sub = response.json()
    assert sub["status"] == "active"
    assert sub["booked_dates"] == [monday.isoformat(), (monday + timedelta(days=7)).isoformat()]
    assert sub["skipped_dates"] == [
        (monday + timedelta(days=2)).isoformat(),
        (monday + timedelta(days=4)).isoformat(),
    ]
    assert await statuses(db, sub["id"]) == [BookingStatus.ACCEPTED] * 2
    notice = await db.scalar(
        select(Notification).where(
            Notification.user_id == passenger.id, Notification.kind == "subscription_accepted"
        )
    )
    assert notice is not None
    assert notice.payload["booked"] == 2
    assert (await sub_action(routing_api, driver[0], sub["id"], "accept")).json()["code"] == (
        "SUBSCRIPTION_NOT_PENDING"
    )

    detail = (await routing_api.get(f"{API}/series/{series['id']}", headers=auth(passenger))).json()
    assert detail["my_subscription"]["status"] == "active"

    # Cambiar la serie con reservas pide confirmacion; al confirmar, los lunes salen.
    url = f"{API}/series/{series['id']}"
    response = await routing_api.patch(url, json={"weekdays": [2, 4]}, headers=auth(driver[0]))
    assert response.status_code == 409
    assert response.json()["code"] == "SERIES_HAS_BOOKINGS"
    assert response.json()["details"]["passengers"] == 2
    response = await routing_api.patch(
        url, json={"weekdays": [2, 4], "confirm": True}, headers=auth(driver[0])
    )
    assert response.status_code == 200, response.text
    assert await statuses(db, sub["id"]) == [BookingStatus.CANCELLED_BY_DRIVER] * 2


async def test_subscription_cancel_reject_expire_and_series_cancel(
    routing_api: AsyncClient,
    db: AsyncSession,
    semester: Semester,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    series = await published_series(routing_api, driver, places)
    leaver, rejected, idle, rider = [await make_user(UserRole.PASSENGER) for _ in range(4)]

    sub = (await subscribe(routing_api, leaver, series["id"], places, option=15)).json()
    await sub_action(routing_api, driver[0], sub["id"], "accept")
    response = await sub_action(routing_api, leaver, sub["id"], "cancel")
    assert response.json()["status"] == "cancelled"
    assert set(await statuses(db, sub["id"])) == {BookingStatus.CANCELLED_BY_PASSENGER}
    assert (await sub_action(routing_api, leaver, sub["id"], "cancel")).json()["code"] == (
        "SUBSCRIPTION_NOT_ACTIVE"
    )

    sub = (await subscribe(routing_api, rejected, series["id"], places)).json()
    response = await sub_action(routing_api, driver[0], sub["id"], "reject", "Ya voy lleno")
    assert response.json()["status"] == "rejected"
    assert response.json()["reject_reason"] == "Ya voy lleno"

    sub = (await subscribe(routing_api, idle, series["id"], places)).json()
    row = await db.get(SeriesSubscription, sub["id"])
    assert row is not None
    row.expires_at = utcnow() - timedelta(minutes=1)
    await db.flush()
    assert (await expire_pending(db))["subscriptions"] == 1
    await db.refresh(row)
    assert row.status == "expired"

    sub = (await subscribe(routing_api, rider, series["id"], places, option="series")).json()
    accepted = (await sub_action(routing_api, driver[0], sub["id"], "accept")).json()
    assert len(accepted["booked_dates"]) == 12
    response = await routing_api.post(
        f"{API}/series/{series['id']}/cancel",
        json={"reason": "Cambio de horario de clases"},
        headers=auth(driver[0]),
    )
    assert response.status_code == 200
    mine = (await routing_api.get(f"{API}/subscriptions/{sub['id']}", headers=auth(rider))).json()
    assert mine["status"] == "finished"
    assert set(await statuses(db, sub["id"])) == {BookingStatus.CANCELLED_BY_DRIVER}
    listed = (await routing_api.get(f"{API}/subscriptions/mine", headers=auth(rider))).json()
    assert [s["id"] for s in listed] == [sub["id"]]
