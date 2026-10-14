"""Monitoreo de viajes y moderacion (seccion 13): viajes, chat del viaje y calificaciones.

Leer el chat de un viaje es excepcional (una queja o una emergencia) y queda en la
auditoria igual que ocultar mensajes o comentarios.
"""

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import LOCAL_TZ
from app.core.enums import BookingStatus, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.admin.schemas import (
    AdminBooking,
    AdminMessage,
    AdminRating,
    AdminTripDetail,
    AdminTripRow,
)
from app.modules.audit.service import AuditService
from app.modules.bookings.lifecycle import end_trip_bookings
from app.modules.bookings.models import HOLDING_STATUSES, Booking
from app.modules.chat.models import Message
from app.modules.notifications.service import Kind, NotificationService
from app.modules.ratings.models import Rating
from app.modules.safety.models import EmergencyEvent
from app.modules.safety.service import emergency_out
from app.modules.trips.models import Trip
from app.modules.trips.service import mark_cancelled
from app.modules.users.models import User


def local_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    return start, start + timedelta(days=1)


class AdminTripService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def get(self, trip_id: uuid.UUID) -> Trip:
        trip = await self.session.get(Trip, trip_id)
        if trip is None:
            raise NotFoundError("trip")
        return trip

    async def rows(self, trips: list[Trip]) -> list[AdminTripRow]:
        ids = [t.id for t in trips]
        booked = dict(
            (
                await self.session.execute(
                    select(Booking.trip_id, func.sum(Booking.seats))
                    .where(
                        Booking.trip_id.in_(ids),
                        Booking.status.in_((*HOLDING_STATUSES, BookingStatus.COMPLETED)),
                    )
                    .group_by(Booking.trip_id)
                )
            ).all()
        )
        alerts = dict(
            (
                await self.session.execute(
                    select(EmergencyEvent.trip_id, func.count())
                    .where(EmergencyEvent.trip_id.in_(ids), EmergencyEvent.handled_at.is_(None))
                    .group_by(EmergencyEvent.trip_id)
                )
            ).all()
        )
        return [
            AdminTripRow(
                id=t.id,
                status=t.status,
                departs_at=t.departs_at,
                origin=t.stops[0].place.name,
                destination=t.stops[-1].place.name,
                driver_id=t.driver_id,
                driver_name=t.driver.full_name,
                seats_total=t.seats_total,
                seats_booked=int(booked.get(t.id) or 0),
                open_emergencies=int(alerts.get(t.id) or 0),
                deleted=t.deleted_at is not None,
            )
            for t in trips
        ]

    async def search(
        self,
        status: TripStatus | None,
        day: date | None,
        q: str | None,
        limit: int,
        cursor: str | None,
    ) -> Page[AdminTripRow]:
        query = select(Trip).join(User, User.id == Trip.driver_id)
        if status is not None:
            query = query.where(Trip.status == status)
        if day is not None:
            start, end = local_bounds(day)
            query = query.where(Trip.departs_at >= start, Trip.departs_at < end)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
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
        return Page(
            items=await self.rows(trips),
            next_cursor=encode_cursor(trips[-1].departs_at, trips[-1].id) if has_more else None,
        )

    async def detail(self, trip_id: uuid.UUID) -> AdminTripDetail:
        trip = await self.get(trip_id)
        (summary,) = await self.rows([trip])
        bookings = (
            await self.session.scalars(
                select(Booking).where(Booking.trip_id == trip.id).order_by(Booking.created_at)
            )
        ).all()
        emergencies = (
            await self.session.scalars(
                select(EmergencyEvent)
                .where(EmergencyEvent.trip_id == trip.id)
                .order_by(EmergencyEvent.created_at.desc())
            )
        ).all()
        chat = await self.session.scalar(
            select(Message.id).where(Message.trip_id == trip.id).limit(1)
        )
        vehicle = trip.vehicle
        return AdminTripDetail(
            **summary.model_dump(),
            vehicle=f"{vehicle.brand} {vehicle.model}, {vehicle.color}",
            plate=vehicle.plate,
            price_per_seat=trip.price_per_seat,
            started_at=trip.started_at,
            finished_at=trip.finished_at,
            cancel_reason=trip.cancel_reason,
            bookings=[
                AdminBooking(
                    id=b.id,
                    passenger_id=b.passenger_id,
                    passenger_name=b.passenger.full_name,
                    status=b.status,
                    seats=b.seats,
                    boarded_at=b.boarded_at,
                    created_at=b.created_at,
                )
                for b in bookings
            ],
            emergencies=[emergency_out(e) for e in emergencies],
            has_chat=chat is not None,
        )

    async def cancel(self, actor: Actor, trip_id: uuid.UUID, reason: str) -> AdminTripDetail:
        """Un administrador puede cancelar un viaje programado (por ejemplo, tras una queja)."""
        trip = await self.get(trip_id)
        if trip.status != TripStatus.SCHEDULED or trip.deleted_at is not None:
            raise AppError(
                "TRIP_NOT_EDITABLE",
                "Only scheduled trips can be cancelled",
                409,
                {"status": trip.status},
            )
        mark_cancelled(trip, reason)
        await end_trip_bookings(self.session, trip, BookingStatus.CANCELLED_BY_DRIVER, reason)
        NotificationService(self.session).notify(
            trip.driver_id,
            Kind.TRIP_CANCELLED_BY_ADMIN,
            {"trip_id": str(trip.id), "reason": reason},
        )
        self.audit.record(
            actor,
            "trip.cancel",
            "trip",
            trip.id,
            {"status": "scheduled"},
            {"status": trip.status.value, "reason": reason},
        )
        await self.session.commit()
        return await self.detail(trip.id)

    # --- Chat del viaje ------------------------------------------------------------------

    async def messages(self, actor: Actor, trip_id: uuid.UUID) -> list[AdminMessage]:
        trip = await self.get(trip_id)
        rows = (
            await self.session.scalars(
                select(Message)
                .where(Message.trip_id == trip.id)
                .order_by(Message.sent_at, Message.id)
            )
        ).all()
        self.audit.record(actor, "chat.view", "trip", trip.id)
        await self.session.commit()
        return [
            AdminMessage(
                id=m.id,
                sender_id=m.sender_id,
                sender_name=m.sender.full_name,
                body=m.body,
                sent_at=m.sent_at,
                hidden=m.hidden,
            )
            for m in rows
        ]

    async def set_message_hidden(
        self, actor: Actor, message_id: uuid.UUID, hidden: bool
    ) -> AdminMessage:
        message = await self.session.get(Message, message_id)
        if message is None:
            raise NotFoundError("message")
        before = {"hidden": message.hidden}
        message.hidden = hidden
        self.audit.record(
            actor,
            "message.hide" if hidden else "message.unhide",
            "message",
            message.id,
            before,
            {"hidden": hidden},
        )
        await self.session.commit()
        return AdminMessage(
            id=message.id,
            sender_id=message.sender_id,
            sender_name=message.sender.full_name,
            body=message.body,
            sent_at=message.sent_at,
            hidden=message.hidden,
        )

    # --- Calificaciones ------------------------------------------------------------------

    async def ratings(
        self, hidden: bool | None, limit: int, cursor: str | None
    ) -> Page[AdminRating]:
        """Calificaciones con comentario, de la mas reciente."""
        query = select(Rating).where(Rating.comment.is_not(None))
        if hidden is not None:
            query = query.where(Rating.hidden.is_(hidden))
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
        names = dict(
            (
                await self.session.execute(
                    select(User.id, User.full_name).where(
                        User.id.in_({r.author_id for r in rows} | {r.target_id for r in rows})
                    )
                )
            ).all()
        )
        return Page(
            items=[self.rating_row(r, names) for r in rows],
            next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None,
        )

    @staticmethod
    def rating_row(rating: Rating, names: dict[uuid.UUID, str]) -> AdminRating:
        return AdminRating(
            id=rating.id,
            trip_id=rating.trip_id,
            author_name=names.get(rating.author_id, ""),
            target_name=names.get(rating.target_id, ""),
            target_role=rating.target_role,
            average=round(rating.average, 2),
            comment=rating.comment,
            hidden=rating.hidden,
            created_at=rating.created_at,
        )

    async def set_rating_hidden(
        self, actor: Actor, rating_id: uuid.UUID, hidden: bool
    ) -> AdminRating:
        """Oculta o muestra el comentario; las estrellas siguen contando."""
        rating = await self.session.get(Rating, rating_id)
        if rating is None:
            raise NotFoundError("rating")
        before = {"hidden": rating.hidden}
        rating.hidden = hidden
        self.audit.record(
            actor,
            "rating.hide" if hidden else "rating.unhide",
            "rating",
            rating.id,
            before,
            {"hidden": hidden},
        )
        await self.session.commit()
        names = dict(
            (
                await self.session.execute(
                    select(User.id, User.full_name).where(
                        User.id.in_((rating.author_id, rating.target_id))
                    )
                )
            ).all()
        )
        return self.rating_row(rating, names)
