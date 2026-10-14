"""Calificaciones (seccion 7.7): bidireccionales, por criterio, una por par y viaje, dentro de
rating_window_days despues de finalizar y solo entre quienes viajaron."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.bookings.models import Booking
from app.modules.notifications.service import Kind, NotificationService
from app.modules.ratings.models import DRIVER_CRITERIA, PASSENGER_CRITERIA, Rating
from app.modules.ratings.schemas import PendingRating, RatingIn, RatingOut
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.users.models import User


@dataclass(frozen=True)
class Target:
    user: User
    role: str  # rol de quien recibe: driver o passenger


def criteria_for(role: str) -> tuple[str, ...]:
    return DRIVER_CRITERIA if role == "driver" else PASSENGER_CRITERIA


async def riders_of(session: AsyncSession, trip_id: uuid.UUID) -> list[Booking]:
    """Pasajeros que viajaron (reserva completada: abordaron)."""
    rows = await session.scalars(
        select(Booking).where(Booking.trip_id == trip_id, Booking.status == BookingStatus.COMPLETED)
    )
    return list(rows.all())


async def targets_for(session: AsyncSession, trip: Trip, user: User) -> list[Target]:
    """El conductor califica a cada pasajero que abordo; cada uno de ellos, al conductor."""
    riders = await riders_of(session, trip.id)
    if trip.driver_id == user.id:
        return [Target(b.passenger, "passenger") for b in riders]
    if any(b.passenger_id == user.id for b in riders):
        return [Target(trip.driver, "driver")]
    return []


def rating_out(rating: Rating) -> RatingOut:
    return RatingOut(
        id=rating.id,
        trip_id=rating.trip_id,
        target_role=rating.target_role,
        scores=rating.scores,
        average=round(rating.average, 2),
        comment=None if rating.hidden else rating.comment,
        hidden=rating.hidden,
        created_at=rating.created_at,
    )


class RatingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)

    async def window(self) -> timedelta:
        return timedelta(days=int(await self.settings.get("rating_window_days")))

    async def rate(self, author: User, trip_id: uuid.UUID, data: RatingIn) -> RatingOut:
        trip = await self.session.get(Trip, trip_id)
        if trip is None or trip.deleted_at is not None:
            raise NotFoundError("trip")
        targets = await targets_for(self.session, trip, author)
        if not targets:
            raise NotFoundError("trip")
        if trip.status != TripStatus.COMPLETED or trip.finished_at is None:
            raise AppError("RATING_NOT_OPEN", "Ratings open when the trip is finished", 409)
        window = await self.window()
        if utcnow() > trip.finished_at + window:
            raise AppError(
                "RATING_WINDOW_CLOSED",
                "The time to rate this trip has passed",
                409,
                {"days": window.days},
            )
        target = next((t for t in targets if t.user.id == data.target_id), None)
        if target is None:
            raise AppError("RATING_TARGET_INVALID", "You cannot rate this person", 422)
        expected = set(criteria_for(target.role))
        if set(data.scores) != expected:
            raise AppError(
                "RATING_CRITERIA_INVALID",
                "Rate every criterion for this role",
                422,
                {"criteria": sorted(expected)},
            )
        existing = await self.session.scalar(
            select(Rating.id).where(
                Rating.trip_id == trip.id,
                Rating.author_id == author.id,
                Rating.target_id == target.user.id,
            )
        )
        if existing is not None:
            raise AppError("RATING_EXISTS", "You already rated this person on this trip", 409)
        rating = Rating(
            trip_id=trip.id,
            author_id=author.id,
            target_id=target.user.id,
            target_role=target.role,
            comment=data.comment,
            created_at=utcnow(),
            scores=dict(sorted(data.scores.items())),
            average=sum(data.scores.values()) / len(data.scores),
        )
        self.session.add(rating)
        NotificationService(self.session).notify(
            target.user.id, Kind.RATING_RECEIVED, {"trip_id": str(trip.id)}
        )
        await self.session.commit()
        return rating_out(rating)

    async def pending(self, user: User) -> list[PendingRating]:
        """A quien le falta calificar al usuario, en viajes con el plazo abierto."""
        window = await self.window()
        since = utcnow() - window
        trips = (
            await self.session.scalars(
                select(Trip)
                .outerjoin(Booking, Booking.trip_id == Trip.id)
                .where(
                    Trip.status == TripStatus.COMPLETED,
                    Trip.finished_at > since,
                    or_(
                        Trip.driver_id == user.id,
                        and_(
                            Booking.passenger_id == user.id,
                            Booking.status == BookingStatus.COMPLETED,
                        ),
                    ),
                )
                .distinct()
                .order_by(Trip.finished_at.desc())
            )
        ).all()
        done = set(
            (
                await self.session.execute(
                    select(Rating.trip_id, Rating.target_id).where(
                        Rating.author_id == user.id, Rating.trip_id.in_([t.id for t in trips])
                    )
                )
            ).all()
        )
        pending = []
        for trip in trips:
            assert trip.finished_at is not None  # noqa: S101 - filtrado arriba
            for target in await targets_for(self.session, trip, user):
                if (trip.id, target.user.id) in done:
                    continue
                pending.append(
                    PendingRating(
                        trip_id=trip.id,
                        departs_at=trip.departs_at,
                        origin=trip.stops[0].place.name,
                        destination=trip.stops[-1].place.name,
                        target_id=target.user.id,
                        target_name=target.user.full_name,
                        target_role=target.role,
                        criteria=list(criteria_for(target.role)),
                        closes_at=trip.finished_at + window,
                    )
                )
        return pending

    async def received(self, user_id: uuid.UUID, limit: int, cursor: str | None) -> Page[RatingOut]:
        """Calificaciones que recibio alguien, sin quien las escribio ni comentarios ocultos."""
        if await self.session.get(User, user_id) is None:
            raise NotFoundError("user")
        query = select(Rating).where(Rating.target_id == user_id)
        if cursor:
            at, row_id = decode_cursor(cursor)
            query = query.where(
                or_(Rating.created_at < at, and_(Rating.created_at == at, Rating.id < row_id))
            )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(Rating.created_at.desc(), Rating.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return Page(
            items=[rating_out(r) for r in rows],
            next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None,
        )

    async def given_on(self, user: User, trip_id: uuid.UUID) -> set[uuid.UUID]:
        rows = await self.session.scalars(
            select(Rating.target_id).where(Rating.trip_id == trip_id, Rating.author_id == user.id)
        )
        return set(rows.all())
