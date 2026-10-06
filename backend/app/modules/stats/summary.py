"""Recalculo de user_stats desde las tablas de origen (viajes, reservas y calificaciones).

Se recalcula todo el resumen del usuario en vez de sumar y restar: es una consulta por
usuario afectado y nunca se desajusta. Ninguna funcion hace commit.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BookingStatus, TripStatus
from app.modules.bookings.models import Booking
from app.modules.ratings.models import Rating, RatingScore
from app.modules.stats.models import UserStats
from app.modules.trips.models import Trip


async def _count(session: AsyncSession, query: Select[Any]) -> int:
    return int(await session.scalar(query) or 0)


async def refresh_user_stats(session: AsyncSession, user_ids: Iterable[uuid.UUID]) -> None:
    for user_id in set(user_ids):
        stats = await session.get(UserStats, user_id)
        if stats is None:
            stats = UserStats(user_id=user_id)
            session.add(stats)
        stats.trips_as_driver = await _count(
            session,
            select(func.count()).where(
                Trip.driver_id == user_id, Trip.status == TripStatus.COMPLETED
            ),
        )
        stats.driver_cancellations = await _count(
            session,
            select(func.count()).where(
                Trip.driver_id == user_id,
                Trip.status == TripStatus.CANCELLED_BY_DRIVER,
                Trip.deleted_at.is_(None),
            ),
        )
        stats.trips_as_passenger = await _count(
            session,
            select(func.count()).where(
                Booking.passenger_id == user_id, Booking.status == BookingStatus.COMPLETED
            ),
        )
        stats.passenger_no_shows = await _count(
            session,
            select(func.count()).where(
                Booking.passenger_id == user_id, Booking.status == BookingStatus.NO_SHOW
            ),
        )
        rows = (
            await session.execute(
                select(RatingScore.criterion, func.avg(RatingScore.stars))
                .join(Rating, Rating.id == RatingScore.rating_id)
                .where(Rating.target_id == user_id)
                .group_by(RatingScore.criterion)
            )
        ).all()
        stats.criteria = {criterion: round(float(avg), 2) for criterion, avg in rows}
        stats.rating_count = await _count(
            session, select(func.count()).where(Rating.target_id == user_id)
        )
        # Promedio general = promedio de los criterios (todos pesan igual).
        stats.rating_avg = (
            round(sum(stats.criteria.values()) / len(stats.criteria), 2) if stats.criteria else None
        )


async def stats_for(
    session: AsyncSession, user_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, UserStats]:
    ids = list(set(user_ids))
    if not ids:
        return {}
    rows = await session.scalars(select(UserStats).where(UserStats.user_id.in_(ids)))
    return {row.user_id: row for row in rows.all()}
