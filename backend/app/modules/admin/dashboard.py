"""Indicadores del panel de administracion (seccion 13)."""

from datetime import timedelta
from typing import Any

from sqlalchemy import Numeric, Select, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import ColumnClause

from app.core.clock import local_today, utcnow
from app.core.enums import BookingStatus, ReviewStatus, TripStatus
from app.modules.admin.schemas import AdminOverview, CountItem, DayCount, RouteCount
from app.modules.bookings.models import Booking
from app.modules.documents.models import Document
from app.modules.places.models import Place
from app.modules.ratings.models import Rating
from app.modules.safety.models import EmergencyEvent
from app.modules.trips.models import Trip, TripStop
from app.modules.users.models import User

TOP_ROUTES = 8
ZONE: ColumnClause[Any] = literal_column("'America/Bogota'")


def local(column: Any) -> Any:
    return func.timezone(ZONE, column)


async def _scalar(session: AsyncSession, query: Select[Any]) -> int:
    return int(await session.scalar(query) or 0)


async def overview(session: AsyncSession, days: int) -> AdminOverview:
    """Usuarios por rol y estado; y, en la ventana de `days` dias, viajes por dia y por hora,
    ocupacion, cancelaciones, no-shows, rutas frecuentes y distribucion de calificaciones."""
    since = utcnow() - timedelta(days=days)
    users = (
        await session.execute(
            select(User.role, User.status, func.count())
            .where(User.deleted_at.is_(None))
            .group_by(User.role, User.status)
        )
    ).all()

    completed = (Trip.status == TripStatus.COMPLETED, Trip.departs_at >= since)
    day_col = func.to_char(local(Trip.departs_at), literal_column("'YYYY-MM-DD'"))
    per_day: dict[str, int] = {
        str(day): int(count)
        for day, count in (
            await session.execute(select(day_col, func.count()).where(*completed).group_by(day_col))
        ).all()
    }
    today = local_today()
    day_keys = [(today - timedelta(days=n)).isoformat() for n in reversed(range(days))]
    hour_col = func.extract("hour", local(Trip.departs_at))
    per_hour = {
        int(hour): int(count)
        for hour, count in (
            await session.execute(
                select(hour_col, func.count()).where(*completed).group_by(hour_col)
            )
        ).all()
    }

    seats_used = (
        select(func.coalesce(func.sum(Booking.seats), 0))
        .where(Booking.trip_id == Trip.id, Booking.status == BookingStatus.COMPLETED)
        .correlate(Trip)
        .scalar_subquery()
    )
    occupancy = await session.scalar(
        select(func.avg(seats_used * 1.0 / Trip.seats_total)).where(*completed)
    )

    origin_stop, destination_stop = aliased(TripStop), aliased(TripStop)
    origin_place, destination_place = aliased(Place), aliased(Place)
    last_position = (
        select(func.max(TripStop.position))
        .where(TripStop.trip_id == Trip.id)
        .correlate(Trip)
        .scalar_subquery()
    )
    routes = (
        await session.execute(
            select(origin_place.name, destination_place.name, func.count())
            .select_from(Trip)
            .join(origin_stop, (origin_stop.trip_id == Trip.id) & (origin_stop.position == 0))
            .join(origin_place, origin_place.id == origin_stop.place_id)
            .join(
                destination_stop,
                (destination_stop.trip_id == Trip.id)
                & (destination_stop.position == last_position),
            )
            .join(destination_place, destination_place.id == destination_stop.place_id)
            .where(Trip.departs_at >= since, Trip.deleted_at.is_(None))
            .group_by(origin_place.name, destination_place.name)
            .order_by(func.count().desc())
            .limit(TOP_ROUTES)
        )
    ).all()

    averages = (
        select(func.round(cast(Rating.average, Numeric)).label("stars"))
        .where(Rating.created_at >= since)
        .subquery()
    )
    distribution: dict[int, int] = {
        int(stars): int(count)
        for stars, count in (
            await session.execute(select(averages.c.stars, func.count()).group_by(averages.c.stars))
        ).all()
    }

    return AdminOverview(
        days=days,
        users=[
            CountItem(key=f"{role.value}:{status.value}", count=int(count))
            for role, status, count in users
        ],
        trips_completed=sum(per_day.values()),
        trips_per_day=[DayCount(day=key, count=per_day.get(key, 0)) for key in day_keys],
        trips_per_hour=[per_hour.get(hour, 0) for hour in range(24)],
        occupancy=round(float(occupancy), 3) if occupancy is not None else None,
        driver_cancellations=await _scalar(
            session,
            select(func.count()).where(
                Trip.status == TripStatus.CANCELLED_BY_DRIVER,
                Trip.cancelled_at >= since,
                Trip.deleted_at.is_(None),
            ),
        ),
        passenger_cancellations=await _scalar(
            session,
            select(func.count()).where(
                Booking.status == BookingStatus.CANCELLED_BY_PASSENGER,
                Booking.cancelled_at >= since,
            ),
        ),
        no_shows=await _scalar(
            session,
            select(func.count()).where(
                Booking.status == BookingStatus.NO_SHOW, Booking.no_show_at >= since
            ),
        ),
        top_routes=[
            RouteCount(origin=origin, destination=destination, count=int(count))
            for origin, destination, count in routes
        ],
        rating_distribution=[int(distribution.get(stars, 0)) for stars in range(1, 6)],
        pending_approvals=await _scalar(
            session, select(func.count()).where(Document.status == ReviewStatus.PENDING)
        ),
        open_emergencies=await _scalar(
            session, select(func.count()).where(EmergencyEvent.handled_at.is_(None))
        ),
    )
