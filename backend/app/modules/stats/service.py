"""Historial y estadisticas del pasajero y del conductor (secciones 8 y 13)."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnClause
from sqlalchemy.sql.functions import Function

from app.core.clock import local_today, utcnow
from app.core.enums import BookingStatus, TripStatus
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.bookings.models import ACTIVE_STATUSES, Booking
from app.modules.places.models import Place
from app.modules.ratings.models import Rating
from app.modules.ratings.service import riders_of
from app.modules.settings.service import SettingsService
from app.modules.stats.schemas import (
    DriverHistoryEntry,
    DriverMonth,
    DriverStats,
    PassengerHistoryEntry,
    PassengerMonth,
    PassengerStats,
    PlaceCount,
    RatingBlock,
)
from app.modules.stats.summary import stats_for
from app.modules.tickets.models import Ticket
from app.modules.trips.models import Trip
from app.modules.users.models import User

MONTHS = 12
TOP_PLACES = 5
LOCAL_ZONE = "America/Bogota"


def month_keys(today: date, count: int = MONTHS) -> list[str]:
    """Los ultimos `count` meses, del mas antiguo al actual (YYYY-MM)."""
    year, month = today.year, today.month
    keys = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def local_month(column: Any) -> Function[Any]:
    # Constantes en el SQL (no como parametros): asi la misma expresion sirve en SELECT y
    # GROUP BY, que Postgres compara texto a texto.
    zone: ColumnClause[Any] = literal_column(f"'{LOCAL_ZONE}'")
    return func.to_char(func.timezone(zone, column), literal_column("'YYYY-MM'"))


def rating_state(closes_at: datetime | None, pending: int, rated: int) -> str:
    """none: no hay a quien calificar; pending: falta alguien y el plazo sigue abierto;
    done: califico a todos; closed: vencio el plazo sin calificar a todos."""
    if pending == 0 and rated == 0:
        return "none"
    if pending == 0:
        return "done"
    return "pending" if closes_at and utcnow() < closes_at else "closed"


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def window(self) -> timedelta:
        return timedelta(days=int(await SettingsService(self.session).get("rating_window_days")))

    async def rating_block(self, user: User) -> RatingBlock:
        stats = (await stats_for(self.session, [user.id])).get(user.id)
        return RatingBlock(
            average=stats.rating_avg if stats else None,
            count=stats.rating_count if stats else 0,
            criteria=stats.criteria if stats else {},
        )

    # --- Pasajero -----------------------------------------------------------------------

    async def passenger(self, user: User) -> PassengerStats:
        completed = and_(Booking.passenger_id == user.id, Booking.status == BookingStatus.COMPLETED)
        trips = int(await self.session.scalar(select(func.count()).where(completed)) or 0)
        spent = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(Ticket.amount), 0))
                .join(Booking, Booking.id == Ticket.booking_id)
                .where(Booking.passenger_id == user.id)
            )
            or 0
        )
        by_status = dict(
            (
                await self.session.execute(
                    select(Booking.status, func.count())
                    .where(Booking.passenger_id == user.id)
                    .group_by(Booking.status)
                )
            ).all()
        )
        top = (
            await self.session.execute(
                select(Place.name, func.count())
                .join(Booking, Booking.pickup_place_id == Place.id)
                .where(completed)
                .group_by(Place.name)
                .order_by(func.count().desc(), Place.name)
                .limit(TOP_PLACES)
            )
        ).all()
        keys = month_keys(local_today())
        monthly = {
            month: (int(count), int(amount or 0))
            for month, count, amount in (
                await self.session.execute(
                    select(
                        local_month(Trip.departs_at),
                        func.count(Booking.id),
                        func.sum(Ticket.amount),
                    )
                    .join(Trip, Trip.id == Booking.trip_id)
                    .outerjoin(Ticket, Ticket.booking_id == Booking.id)
                    .where(completed, local_month(Trip.departs_at).in_(keys))
                    .group_by(local_month(Trip.departs_at))
                )
            ).all()
        }
        return PassengerStats(
            trips=trips,
            spent=spent,
            no_shows=int(by_status.get(BookingStatus.NO_SHOW, 0)),
            cancellations=int(by_status.get(BookingStatus.CANCELLED_BY_PASSENGER, 0)),
            rating=await self.rating_block(user),
            top_origins=[PlaceCount(name=name, count=int(count)) for name, count in top],
            by_month=[
                PassengerMonth(
                    month=key, trips=monthly.get(key, (0, 0))[0], spent=monthly.get(key, (0, 0))[1]
                )
                for key in keys
            ],
        )

    # --- Conductor ----------------------------------------------------------------------

    async def driver(self, user: User) -> DriverStats:
        done = and_(Trip.driver_id == user.id, Trip.status == TripStatus.COMPLETED)
        trips = int(await self.session.scalar(select(func.count()).where(done)) or 0)
        seats_used = (
            select(func.coalesce(func.sum(Booking.seats), 0))
            .where(Booking.trip_id == Trip.id, Booking.status == BookingStatus.COMPLETED)
            .correlate(Trip)
            .scalar_subquery()
        )
        occupancy = await self.session.scalar(
            select(func.avg(seats_used * 1.0 / Trip.seats_total)).where(done)
        )
        passengers = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Booking)
                .join(Trip, Trip.id == Booking.trip_id)
                .where(done, Booking.status == BookingStatus.COMPLETED)
            )
            or 0
        )
        contributions = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(Ticket.amount), 0),
                    func.coalesce(
                        func.sum(Ticket.amount).filter(Ticket.paid_confirmed.is_(True)), 0
                    ),
                )
                .join(Booking, Booking.id == Ticket.booking_id)
                .join(Trip, Trip.id == Booking.trip_id)
                .where(Trip.driver_id == user.id)
            )
        ).one()
        cancellations = int(
            await self.session.scalar(
                select(func.count()).where(
                    Trip.driver_id == user.id,
                    Trip.status == TripStatus.CANCELLED_BY_DRIVER,
                    Trip.deleted_at.is_(None),
                )
            )
            or 0
        )
        keys = month_keys(local_today())
        monthly = {
            month: (int(count), int(riders or 0))
            for month, count, riders in (
                await self.session.execute(
                    select(local_month(Trip.departs_at), func.count(), func.sum(seats_used))
                    .where(done, local_month(Trip.departs_at).in_(keys))
                    .group_by(local_month(Trip.departs_at))
                )
            ).all()
        }
        return DriverStats(
            trips=trips,
            passengers=passengers,
            occupancy=round(float(occupancy), 3) if occupancy is not None else None,
            contributions=int(contributions[0]),
            confirmed_contributions=int(contributions[1]),
            cancellations=cancellations,
            rating=await self.rating_block(user),
            by_month=[
                DriverMonth(
                    month=key,
                    trips=monthly.get(key, (0, 0))[0],
                    passengers=monthly.get(key, (0, 0))[1],
                )
                for key in keys
            ],
        )

    # --- Historial ----------------------------------------------------------------------

    async def passenger_history(
        self, user: User, limit: int, cursor: str | None
    ) -> Page[PassengerHistoryEntry]:
        """Reservas que ya no estan vigentes o cuyo viaje termino, de la mas reciente."""
        active = and_(
            Booking.status.in_(ACTIVE_STATUSES),
            Trip.status.in_((TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)),
        )
        query = (
            select(Booking, Trip)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(Booking.passenger_id == user.id, ~active)
        )
        if cursor:
            at, row_id = decode_cursor(cursor)
            query = query.where(
                or_(Trip.departs_at < at, and_(Trip.departs_at == at, Booking.id < row_id))
            )
        rows = (
            await self.session.execute(
                query.order_by(Trip.departs_at.desc(), Booking.id.desc()).limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        tickets = {
            t.booking_id: t
            for t in (
                await self.session.scalars(
                    select(Ticket).where(Ticket.booking_id.in_([b.id for b, _ in rows]))
                )
            ).all()
        }
        rated = set(
            (
                await self.session.scalars(
                    select(Rating.trip_id).where(
                        Rating.author_id == user.id, Rating.trip_id.in_([t.id for _, t in rows])
                    )
                )
            ).all()
        )
        window = await self.window()
        items = []
        for booking, trip in rows:
            ticket = tickets.get(booking.id)
            can_rate = booking.status == BookingStatus.COMPLETED
            closes = trip.finished_at + window if trip.finished_at and can_rate else None
            items.append(
                PassengerHistoryEntry(
                    booking_id=booking.id,
                    trip_id=trip.id,
                    departs_at=trip.departs_at,
                    origin=trip.stops[0].place.name,
                    destination=trip.stops[-1].place.name,
                    driver_name=trip.driver.full_name,
                    trip_status=trip.status,
                    booking_status=booking.status,
                    seats=booking.seats,
                    amount=ticket.amount if ticket else None,
                    ticket_code=ticket.code if ticket else None,
                    paid_confirmed=ticket.paid_confirmed if ticket else None,
                    rating=rating_state(
                        closes,
                        int(can_rate and trip.id not in rated),
                        int(trip.id in rated),
                    ),
                    rating_closes_at=closes,
                )
            )
        last = rows[-1] if rows else None
        return Page(
            items=items,
            next_cursor=encode_cursor(last[1].departs_at, last[0].id)
            if has_more and last
            else None,
        )

    async def driver_history(
        self, user: User, limit: int, cursor: str | None
    ) -> Page[DriverHistoryEntry]:
        """Viajes propios que ya pasaron, se cancelaron o terminaron."""
        active = or_(
            Trip.status == TripStatus.IN_PROGRESS,
            and_(
                Trip.status == TripStatus.SCHEDULED,
                Trip.departs_at >= utcnow() - timedelta(hours=3),
            ),
        )
        query = select(Trip).where(Trip.driver_id == user.id, Trip.deleted_at.is_(None), ~active)
        if cursor:
            at, row_id = decode_cursor(cursor)
            query = query.where(
                or_(Trip.departs_at < at, and_(Trip.departs_at == at, Trip.id < row_id))
            )
        trips = list(
            (
                await self.session.scalars(
                    query.order_by(Trip.departs_at.desc(), Trip.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(trips) > limit
        trips = trips[:limit]
        window = await self.window()
        items = []
        for trip in trips:
            riders = await riders_of(self.session, trip.id)
            rated = set(
                (
                    await self.session.scalars(
                        select(Rating.target_id).where(
                            Rating.trip_id == trip.id, Rating.author_id == user.id
                        )
                    )
                ).all()
            )
            contributions = int(
                await self.session.scalar(
                    select(func.coalesce(func.sum(Ticket.amount), 0))
                    .join(Booking, Booking.id == Ticket.booking_id)
                    .where(Booking.trip_id == trip.id)
                )
                or 0
            )
            closes = trip.finished_at + window if trip.finished_at else None
            pending = sum(1 for b in riders if b.passenger_id not in rated)
            items.append(
                DriverHistoryEntry(
                    trip_id=trip.id,
                    series_id=trip.series_id,
                    departs_at=trip.departs_at,
                    origin=trip.stops[0].place.name,
                    destination=trip.stops[-1].place.name,
                    trip_status=trip.status,
                    seats_total=trip.seats_total,
                    passengers=sum(b.seats for b in riders),
                    contributions=contributions,
                    to_rate=pending if closes and utcnow() < closes else 0,
                    rating=rating_state(closes, pending, len(rated)),
                    rating_closes_at=closes if riders else None,
                )
            )
        return Page(
            items=items,
            next_cursor=encode_cursor(trips[-1].departs_at, trips[-1].id) if has_more else None,
        )
