"""Lista de espera de viajes llenos (seccion 7.5)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.db import add_unique
from app.core.enums import WaitlistStatus
from app.core.errors import AppError, NotFoundError
from app.modules.bookings.queries import seats_left
from app.modules.bookings.schemas import Preferences, WaitlistJoin, WaitlistOut
from app.modules.bookings.service import (
    BookingService,
    check_compatibility,
    require_can_book,
    resolve_places,
    trip_brief,
    trip_rules,
)
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.waitlist.models import OPEN_STATUSES, WaitlistEntry
from app.modules.waitlist.offers import offer_next


def waitlist_exists() -> AppError:
    return AppError("WAITLIST_EXISTS", "You are already on the waiting list", 409)


async def people_ahead(session: AsyncSession, entry: WaitlistEntry) -> int:
    if entry.status not in OPEN_STATUSES:
        return 0
    count = await session.scalar(
        select(func.count()).where(
            WaitlistEntry.trip_id == entry.trip_id,
            WaitlistEntry.status.in_(OPEN_STATUSES),
            WaitlistEntry.position < entry.position,
        )
    )
    return int(count or 0)


async def waitlist_outs(
    session: AsyncSession, entries: Sequence[WaitlistEntry], viewer: User
) -> list[WaitlistOut]:
    return [
        WaitlistOut(
            id=entry.id,
            trip=trip_brief(entry.trip, viewer),
            seats=entry.seats,
            status=entry.status,
            ahead=await people_ahead(session, entry),
            offered_at=entry.offered_at,
            offer_expires_at=entry.offer_expires_at,
            booking_id=entry.booking_id,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


class WaitlistService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bookings = BookingService(session)

    async def reload(self, entry_id: uuid.UUID) -> WaitlistEntry:
        entry = await self.session.scalar(
            select(WaitlistEntry)
            .where(WaitlistEntry.id == entry_id)
            .execution_options(populate_existing=True)
        )
        if entry is None:
            raise NotFoundError("waitlist_entry")
        return entry

    async def join(self, passenger: User, trip_id: uuid.UUID, data: WaitlistJoin) -> WaitlistEntry:
        """Solo cuando el viaje no tiene cupo para los puestos pedidos."""
        trip = self.bookings.require_bookable(await self.session.get(Trip, trip_id), passenger)
        check_compatibility(passenger, trip_rules(trip), data.preferences)
        await require_can_book(self.session, passenger)
        if await self.bookings.has_active(passenger.id, trip.id):
            raise AppError("BOOKING_EXISTS", "You already have a booking on this trip", 409)
        existing = await self.session.scalar(
            select(WaitlistEntry.id).where(
                WaitlistEntry.trip_id == trip.id,
                WaitlistEntry.passenger_id == passenger.id,
                WaitlistEntry.status.in_(OPEN_STATUSES),
            )
        )
        if existing is not None:
            raise waitlist_exists()
        free = await seats_left(self.session, trip)
        if free >= data.seats:
            raise AppError(
                "WAITLIST_NOT_NEEDED",
                "There are seats left: book instead",
                409,
                {"seats_available": free},
            )
        places = await resolve_places(self.session, passenger, data)
        await self.bookings.meeting(trip, *places)
        last = await self.session.scalar(
            select(func.max(WaitlistEntry.position)).where(WaitlistEntry.trip_id == trip.id)
        )
        entry = WaitlistEntry(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=data.seats,
            pickup_place_id=places[0].id,
            dropoff_place_id=places[1].id,
            preferences=data.preferences.model_dump(),
            position=(last or 0) + 1,
            status=WaitlistStatus.WAITING,
        )
        await add_unique(self.session, entry, waitlist_exists())
        await self.session.commit()
        return await self.reload(entry.id)

    async def leave(self, passenger: User, trip_id: uuid.UUID) -> None:
        entry = await self.session.scalar(
            select(WaitlistEntry).where(
                WaitlistEntry.trip_id == trip_id,
                WaitlistEntry.passenger_id == passenger.id,
                WaitlistEntry.status.in_(OPEN_STATUSES),
            )
        )
        if entry is None:
            raise NotFoundError("waitlist_entry")
        was_offered = entry.status == WaitlistStatus.OFFERED
        entry.status = WaitlistStatus.LEFT
        if was_offered:
            await offer_next(self.session, entry.trip)
        await self.session.commit()

    async def get_own(self, passenger: User, entry_id: uuid.UUID) -> WaitlistEntry:
        entry = await self.session.get(WaitlistEntry, entry_id)
        if entry is None or entry.passenger_id != passenger.id:
            raise NotFoundError("waitlist_entry")
        return entry

    def require_offer(self, entry: WaitlistEntry) -> None:
        if (
            entry.status != WaitlistStatus.OFFERED
            or entry.offer_expires_at is None
            or entry.offer_expires_at <= utcnow()
        ):
            raise AppError(
                "WAITLIST_OFFER_EXPIRED", "There is no open offer", 409, {"status": entry.status}
            )

    async def confirm(self, passenger: User, entry_id: uuid.UUID) -> WaitlistEntry:
        """Convierte la oferta en una solicitud que el conductor aprueba como siempre."""
        entry = await self.get_own(passenger, entry_id)
        self.require_offer(entry)
        trip = self.bookings.require_bookable(entry.trip, passenger)
        free = await seats_left(self.session, trip)
        if free < entry.seats:
            raise AppError("TRIP_FULL", "Not enough seats left", 409, {"seats_available": free})
        data = WaitlistJoin(
            seats=entry.seats,
            pickup_place_id=entry.pickup_place_id,
            dropoff_place_id=entry.dropoff_place_id,
            preferences=Preferences(**entry.preferences),
        )
        booking = await self.bookings.request(passenger, trip.id, data)
        entry = await self.reload(entry.id)
        entry.status = WaitlistStatus.CONVERTED
        entry.booking_id = booking.id
        await self.session.commit()
        return await self.reload(entry.id)

    async def decline(self, passenger: User, entry_id: uuid.UUID) -> WaitlistEntry:
        entry = await self.get_own(passenger, entry_id)
        self.require_offer(entry)
        entry.status = WaitlistStatus.LEFT
        await offer_next(self.session, entry.trip)
        await self.session.commit()
        return await self.reload(entry.id)

    async def list_mine(self, passenger: User) -> list[WaitlistOut]:
        rows = (
            await self.session.scalars(
                select(WaitlistEntry)
                .join(Trip, Trip.id == WaitlistEntry.trip_id)
                .where(
                    WaitlistEntry.passenger_id == passenger.id,
                    WaitlistEntry.status.in_(OPEN_STATUSES),
                )
                .order_by(Trip.departs_at)
            )
        ).all()
        return await waitlist_outs(self.session, rows, passenger)
