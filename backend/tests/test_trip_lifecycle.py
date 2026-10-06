"""Ciclo del viaje: iniciar, abordaje, no-show y sancion, finalizar con tickets y jobs."""

import re
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import LOCAL_TZ, utcnow
from app.core.enums import BookingStatus, SuspensionKind, TripStatus, UserRole
from app.core.realtime import user_channel
from app.modules.bookings.models import Booking
from app.modules.chat.models import Conversation
from app.modules.places.models import Place
from app.modules.routing.models import TrafficFactor
from app.modules.routing.service import weekday_group
from app.modules.suspensions.models import Suspension
from app.modules.trips.jobs import mark_not_held, recompute_traffic_factors, send_trip_reminders
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, EventLog, UserFactory, auth
from tests.test_bookings import book, decide, kinds, published

pytestmark = pytest.mark.integration


async def move(db: AsyncSession, trip_id: str, minutes: float) -> Trip:
    """Pone la salida del viaje a `minutes` de ahora (negativo: ya paso)."""
    trip = await db.get(Trip, trip_id)
    assert trip is not None
    trip.departs_at = utcnow() + timedelta(minutes=minutes)
    await db.flush()
    return trip


async def act(api: AsyncClient, user: User, path: str) -> httpx.Response:
    return await api.post(f"{API}{path}", json={}, headers=auth(user))


async def full_trip(
    api: AsyncClient,
    driver: tuple[User, Vehicle],
    places: list[Place],
    passengers: list[User],
    **trip: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Viaje con una reserva aceptada por pasajero."""
    published_trip = await published(api, driver, places, **trip)
    bookings = []
    for passenger in passengers:
        booking = (await book(api, passenger, published_trip["id"], places)).json()
        await decide(api, driver[0], booking["id"], "accept")
        bookings.append(booking)
    return published_trip, bookings


async def test_complete_trip_from_start_to_tickets(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
    events: EventLog,
) -> None:
    rider, absent, late = [await make_user(UserRole.PASSENGER) for _ in range(3)]
    trip, (boarded, missing) = await full_trip(routing_api, driver, places, [rider, absent])
    pending = (await book(routing_api, late, trip["id"], places)).json()

    # Demasiado pronto para iniciar (sale manana).
    response = await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
    assert response.json()["code"] == "TRIP_START_TOO_EARLY"
    assert (await act(routing_api, rider, f"/trips/{trip['id']}/start")).status_code == 403

    await move(db, trip["id"], 10)
    response = await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"
    assert (await kinds(db, rider))[-1] == "trip_started"
    assert (await kinds(db, late))[-1] == "booking_expired"
    started = await events.on(user_channel(rider.id))
    assert {"type": "trip.started", "trip_id": trip["id"]} in started
    late_booking = await db.get(Booking, pending["id"])
    assert late_booking is not None
    await db.refresh(late_booking)
    assert late_booking.status == BookingStatus.EXPIRED

    # Abordaje: uno sube; el otro no aparece (solo despues de la espera).
    response = await act(routing_api, driver[0], f"/bookings/{boarded['id']}/boarded")
    assert response.status_code == 200, response.text
    response = await act(routing_api, driver[0], f"/bookings/{boarded['id']}/boarded")
    assert response.json()["code"] == "BOOKING_NOT_BOARDABLE"
    response = await act(routing_api, driver[0], f"/bookings/{missing['id']}/no-show")
    assert response.json()["code"] == "NO_SHOW_TOO_EARLY"
    response = await act(routing_api, driver[0], f"/trips/{trip['id']}/finish")
    assert response.json()["code"] == "PASSENGERS_UNMARKED"
    assert response.json()["details"]["passengers"] == [absent.full_name]

    await move(db, trip["id"], -11)
    response = await act(routing_api, driver[0], f"/bookings/{missing['id']}/no-show")
    assert response.json()["status"] == "no_show"
    assert (await kinds(db, absent))[-1] == "passenger_no_show"

    response = await act(routing_api, driver[0], f"/trips/{trip['id']}/finish")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    booking = await db.get(Booking, boarded["id"])
    assert booking is not None
    await db.refresh(booking)
    assert booking.status == BookingStatus.COMPLETED

    tickets = (await routing_api.get(f"{API}/tickets/mine", headers=auth(rider))).json()
    assert len(tickets) == 1
    ticket = tickets[0]
    assert re.fullmatch(r"CP-[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}", ticket["code"])
    assert ticket["amount"] == 2000
    assert ticket["paid_confirmed"] is False
    assert (await kinds(db, rider))[-2:] == ["trip_finished", "rating_pending"]
    assert (await routing_api.get(f"{API}/tickets/mine", headers=auth(absent))).json() == []
    driver_tickets = (
        await routing_api.get(
            f"{API}/tickets/mine",
            params={"role": "driver", "trip_id": trip["id"]},
            headers=auth(driver[0]),
        )
    ).json()
    assert [t["passenger_name"] for t in driver_tickets] == [rider.full_name]

    url = f"{API}/tickets/{ticket['id']}/paid"
    assert (
        await routing_api.post(url, json={"paid": True}, headers=auth(rider))
    ).status_code == 403
    paid = (await routing_api.post(url, json={"paid": True}, headers=auth(driver[0]))).json()
    assert paid["paid_confirmed"] is True

    # Se cierran el grupal y los directos de este viaje puntual (uno por pasajero).
    open_chats = await db.scalar(
        select(func.count()).where(
            Conversation.trip_id == trip["id"], Conversation.closed_at.is_(None)
        )
    )
    assert open_chats == 0


async def test_start_rules(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
) -> None:
    trip = await published(routing_api, driver, places)
    await move(db, trip["id"], -(3 * 60 + 1))
    response = await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
    assert response.json()["code"] == "TRIP_START_TOO_LATE"
    await move(db, trip["id"], 5)
    await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
    response = await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
    assert response.json()["code"] == "TRIP_NOT_STARTABLE"


async def test_repeated_no_shows_suspend_bookings(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    for hour in (7, 11, 15):
        departs = datetime.combine(
            (utcnow() + timedelta(days=2)).astimezone(LOCAL_TZ).date(),
            datetime.min.time(),
            tzinfo=LOCAL_TZ,
        ) + timedelta(hours=hour)
        trip, (booking,) = await full_trip(
            routing_api, driver, places, [passenger], departs_at=departs.isoformat()
        )
        await move(db, trip["id"], 5)
        await act(routing_api, driver[0], f"/trips/{trip['id']}/start")
        await move(db, trip["id"], -11)
        response = await act(routing_api, driver[0], f"/bookings/{booking['id']}/no-show")
        assert response.status_code == 200, response.text
        await act(routing_api, driver[0], f"/trips/{trip['id']}/finish")

    ban = await db.scalar(select(Suspension).where(Suspension.user_id == passenger.id))
    assert ban is not None
    assert ban.kind == SuspensionKind.BOOKING_BAN
    assert ban.created_by is None
    assert ban.ends_at is not None
    assert abs((ban.ends_at - utcnow()) - timedelta(days=7)) < timedelta(minutes=1)
    assert "booking_suspended" in await kinds(db, passenger)
    other = await published(routing_api, driver, places)
    response = await book(routing_api, passenger, other["id"], places)
    assert response.json()["code"] == "BOOKING_SUSPENDED"


async def test_not_held_reminders_and_traffic_factors(
    routing_api: AsyncClient,
    db: AsyncSession,
    driver: tuple[User, Vehicle],
    places: list[Place],
    make_user: UserFactory,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    soon, (booking,) = await full_trip(routing_api, driver, places, [passenger])
    await move(db, soon["id"], 20)
    assert await send_trip_reminders(db) == 1
    assert await send_trip_reminders(db) == 0  # una sola vez
    assert (await kinds(db, passenger))[-1] == "trip_reminder"
    assert (await kinds(db, driver[0]))[-1] == "trip_reminder_driver"

    trip = await move(db, soon["id"], -(3 * 60 + 5))
    assert await mark_not_held(db) == 1
    await db.refresh(trip)
    assert trip.status == TripStatus.NOT_HELD
    row = await db.get(Booking, booking["id"])
    assert row is not None
    await db.refresh(row)
    assert row.status == BookingStatus.EXPIRED

    # Cinco viajes completados que tardaron 1,5 veces lo que dijo OSRM.
    base = await db.get(Trip, soon["id"])
    assert base is not None
    departs = utcnow() - timedelta(days=1)
    for n in range(5):
        db.add(
            Trip(
                driver_id=base.driver_id,
                vehicle_id=base.vehicle_id,
                departs_at=departs,
                seats_total=3,
                price_per_seat=1000,
                route=base.route,
                distance_m=4000,
                est_duration_s=600,
                osrm_duration_s=600,
                status=TripStatus.COMPLETED,
                started_at=departs,
                finished_at=departs + timedelta(seconds=900 + n),
            )
        )
    await db.flush()
    result = await recompute_traffic_factors(db)
    assert result["slots"] == 1
    factor = await db.scalar(
        select(TrafficFactor).where(
            TrafficFactor.weekday_group == weekday_group(departs),
            TrafficFactor.hour == departs.astimezone(LOCAL_TZ).hour,
        )
    )
    assert factor is not None
    assert factor.factor == 1.5
    assert factor.samples == 5
