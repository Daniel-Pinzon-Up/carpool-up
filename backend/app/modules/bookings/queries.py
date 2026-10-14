"""Consultas de cupo y reservas que usan otros modulos (viajes, busqueda)."""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import ScalarSelect, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BookingStatus
from app.core.errors import NotFoundError
from app.modules.bookings.models import ACTIVE_STATUSES, HOLDING_STATUSES, Booking
from app.modules.trips.models import Trip


def booked_seats_subquery() -> ScalarSelect[Any]:
    """Puestos ocupados por viaje (accepted y cancel_requested), para usar en consultas."""
    return (
        select(func.coalesce(func.sum(Booking.seats), 0))
        .where(Booking.trip_id == Trip.id, Booking.status.in_(HOLDING_STATUSES))
        .correlate(Trip)
        .scalar_subquery()
    )


async def booked_seats(
    session: AsyncSession, trip_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, int]:
    ids = list(trip_ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(Booking.trip_id, func.sum(Booking.seats))
        .where(Booking.trip_id.in_(ids), Booking.status.in_(HOLDING_STATUSES))
        .group_by(Booking.trip_id)
    )
    return {trip_id: int(total) for trip_id, total in rows}


async def pending_requests(
    session: AsyncSession, trip_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Solicitudes y cancelaciones tardias que esperan al conductor."""
    ids = list(trip_ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(Booking.trip_id, func.count())
        .where(
            Booking.trip_id.in_(ids),
            Booking.status.in_((BookingStatus.REQUESTED, BookingStatus.CANCEL_REQUESTED)),
        )
        .group_by(Booking.trip_id)
    )
    return {trip_id: int(count) for trip_id, count in rows}


async def active_bookings(session: AsyncSession, trip_id: uuid.UUID) -> list[Booking]:
    query = (
        select(Booking)
        .where(Booking.trip_id == trip_id, Booking.status.in_(ACTIVE_STATUSES))
        .order_by(Booking.created_at)
    )
    return list((await session.scalars(query)).all())


async def lock_trip(session: AsyncSession, trip_id: uuid.UUID) -> Trip:
    """Bloquea la fila del viaje hasta el commit (SELECT ... FOR UPDATE).

    Serializa aceptaciones y ofertas de cupo del mismo viaje para que nunca se sobrevenda.
    """
    trip = await session.scalar(
        select(Trip)
        .where(Trip.id == trip_id)
        .with_for_update(of=Trip)
        .execution_options(populate_existing=True)
    )
    if trip is None:
        raise NotFoundError("trip")
    return trip


async def seats_left(session: AsyncSession, trip: Trip) -> int:
    taken = (await booked_seats(session, [trip.id])).get(trip.id, 0)
    return max(0, trip.seats_total - taken)
