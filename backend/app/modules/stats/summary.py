"""Resumen de cada usuario (viajes, cancelaciones, ausencias y calificacion).

Se calcula al consultar con unas pocas consultas agrupadas por lote de usuarios, en vez de
guardarlo en una tabla aparte: siempre esta al dia y no hay que mantenerlo.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import Integer, cast, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BookingStatus, TripStatus
from app.modules.bookings.models import Booking
from app.modules.ratings.models import Rating
from app.modules.trips.models import Trip


@dataclass
class UserSummary:
    rating_avg: float | None = None
    rating_count: int = 0
    trips_as_driver: int = 0
    trips_as_passenger: int = 0
    driver_cancellations: int = 0
    passenger_no_shows: int = 0
    # Promedio por criterio: {"punctuality": 4.5, ...}
    criteria: dict[str, float] = field(default_factory=dict)


async def stats_for(
    session: AsyncSession, user_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, UserSummary]:
    """Resumen de cada usuario pedido (los que no tienen actividad quedan en cero)."""
    ids = list(set(user_ids))
    summaries = {user_id: UserSummary() for user_id in ids}
    if not ids:
        return summaries

    trips = await session.execute(
        select(Trip.driver_id, Trip.status, func.count())
        .where(
            Trip.driver_id.in_(ids),
            Trip.deleted_at.is_(None),
            Trip.status.in_((TripStatus.COMPLETED, TripStatus.CANCELLED_BY_DRIVER)),
        )
        .group_by(Trip.driver_id, Trip.status)
    )
    for user_id, trip_status, count in trips:
        if trip_status == TripStatus.COMPLETED:
            summaries[user_id].trips_as_driver = count
        else:
            summaries[user_id].driver_cancellations = count

    bookings = await session.execute(
        select(Booking.passenger_id, Booking.status, func.count())
        .where(
            Booking.passenger_id.in_(ids),
            Booking.status.in_((BookingStatus.COMPLETED, BookingStatus.NO_SHOW)),
        )
        .group_by(Booking.passenger_id, Booking.status)
    )
    for user_id, booking_status, count in bookings:
        if booking_status == BookingStatus.COMPLETED:
            summaries[user_id].trips_as_passenger = count
        else:
            summaries[user_id].passenger_no_shows = count

    # Promedio por criterio desde el JSON de estrellas; el general es el promedio de los
    # criterios (todos pesan igual).
    scores = func.jsonb_each_text(Rating.scores).table_valued("key", "value")
    criteria = await session.execute(
        select(Rating.target_id, scores.c.key, func.avg(cast(scores.c.value, Integer)))
        .select_from(Rating)
        .join(scores, true())
        .where(Rating.target_id.in_(ids))
        .group_by(Rating.target_id, scores.c.key)
    )
    for user_id, criterion, avg in criteria:
        summaries[user_id].criteria[criterion] = round(float(avg), 2)
    counts = await session.execute(
        select(Rating.target_id, func.count())
        .where(Rating.target_id.in_(ids))
        .group_by(Rating.target_id)
    )
    for user_id, count in counts:
        summary = summaries[user_id]
        summary.rating_count = count
        values = summary.criteria.values()
        summary.rating_avg = round(sum(values) / len(values), 2) if values else None
    return summaries
