"""Suscripcion a una serie: el conductor aprueba una sola vez (seccion 7.5).

Al aprobar se crean reservas aceptadas en cada ocurrencia del rango que este programada y
tenga cupo; las demas fechas se informan al pasajero, que puede anotarse en su lista de
espera.
"""

import uuid
from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today, utcnow
from app.core.db import add_unique
from app.core.enums import BookingStatus, SeriesStatus, SubscriptionStatus, TripStatus
from app.core.errors import AppError, NotFoundError
from app.modules.bookings.models import ACTIVE_STATUSES, Booking, SeriesSubscription
from app.modules.bookings.queries import booked_seats, lock_trip, seats_left
from app.modules.bookings.schemas import (
    AvailabilityDay,
    Preferences,
    SeriesAvailability,
    SeriesBrief,
    SubscriptionCreate,
    SubscriptionOut,
)
from app.modules.bookings.service import (
    BookingService,
    cancel_rules,
    check_compatibility,
    passenger_card,
    passenger_trip_counts,
    require_can_book,
    resolve_places,
)
from app.modules.chat.membership import join_trip_chats
from app.modules.notifications.service import Kind, NotificationService
from app.modules.series.models import TripSeries
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.trips.planning import local_date
from app.modules.trips.schemas import DriverOut
from app.modules.users.models import User

OPEN = (SubscriptionStatus.REQUESTED, SubscriptionStatus.ACTIVE)


def subscription_exists() -> AppError:
    return AppError("SUBSCRIPTION_EXISTS", "You already have a request for this series", 409)


def subscription_range(start: date, option: int | str, series: TripSeries) -> date:
    """Nunca pasa del final de la serie."""
    if option == "series":
        return series.window_end
    return min(start + timedelta(days=int(option) - 1), series.window_end)


async def series_trips(
    session: AsyncSession, series_id: uuid.UUID, start: date | None = None, end: date | None = None
) -> list[Trip]:
    """Ocurrencias futuras de la serie (opcionalmente dentro de un rango de fechas locales)."""
    query = (
        select(Trip)
        .where(
            Trip.series_id == series_id,
            Trip.deleted_at.is_(None),
            Trip.departs_at > utcnow(),
        )
        .order_by(Trip.departs_at)
    )
    trips = list((await session.scalars(query)).all())
    return [
        t
        for t in trips
        if (start is None or local_date(t.departs_at) >= start)
        and (end is None or local_date(t.departs_at) <= end)
    ]


def series_brief(series: TripSeries) -> SeriesBrief:
    return SeriesBrief(
        id=series.id,
        origin=series.stops[0].place.name,
        destination=series.stops[-1].place.name,
        weekdays=series.weekdays,
        departure_time=series.departure_time,
        window_end=series.window_end,
        price_per_seat=series.price_per_seat,
        driver=DriverOut(id=series.driver.id, full_name=series.driver.full_name),
    )


async def subscription_outs(
    session: AsyncSession, subscriptions: Sequence[SeriesSubscription]
) -> list[SubscriptionOut]:
    if not subscriptions:
        return []
    counts = await passenger_trip_counts(session, {s.passenger_id for s in subscriptions})
    booked_rows = (
        await session.execute(
            select(Booking.subscription_id, Trip.departs_at)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(
                Booking.subscription_id.in_([s.id for s in subscriptions]),
                Booking.status.in_((*ACTIVE_STATUSES, BookingStatus.COMPLETED)),
            )
        )
    ).all()
    booked: dict[uuid.UUID, set[date]] = {}
    for subscription_id, departs_at in booked_rows:
        if subscription_id is not None:
            booked.setdefault(subscription_id, set()).add(local_date(departs_at))
    outs = []
    for sub in subscriptions:
        dates = booked.get(sub.id, set())
        skipped: list[date] = []
        if sub.status == SubscriptionStatus.ACTIVE:
            occurrences = await series_trips(session, sub.series_id, sub.from_date, sub.to_date)
            skipped = sorted({local_date(t.departs_at) for t in occurrences} - dates)
        outs.append(
            SubscriptionOut(
                id=sub.id,
                series=series_brief(sub.series),
                passenger=passenger_card(sub.passenger, counts.get(sub.passenger_id, 0)),
                from_date=sub.from_date,
                to_date=sub.to_date,
                seats=sub.seats,
                pickup_place=sub.pickup_place.name,
                dropoff_place=sub.dropoff_place.name,
                preferences=Preferences(**sub.preferences),
                status=sub.status,
                expires_at=sub.expires_at,
                created_at=sub.created_at,
                decided_at=sub.decided_at,
                reject_reason=sub.reject_reason,
                booked_dates=sorted(dates),
                skipped_dates=skipped,
            )
        )
    return outs


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)
        self.bookings = BookingService(session)
        self.notifications = NotificationService(session)

    async def reload(self, subscription_id: uuid.UUID) -> SeriesSubscription:
        sub = await self.session.scalar(
            select(SeriesSubscription)
            .where(SeriesSubscription.id == subscription_id)
            .execution_options(populate_existing=True)
        )
        if sub is None:
            raise NotFoundError("subscription")
        return sub

    async def active_series(self, viewer: User, series_id: uuid.UUID) -> TripSeries:
        series = await self.session.get(TripSeries, series_id)
        if series is None or series.status != SeriesStatus.ACTIVE:
            raise NotFoundError("series")
        return series

    async def availability(
        self, viewer: User, series_id: uuid.UUID, seats: int
    ) -> SeriesAvailability:
        """Ocurrencias futuras con su cupo; las de pico y placa aparecen bloqueadas."""
        series = await self.active_series(viewer, series_id)
        trips = [
            t
            for t in await series_trips(self.session, series.id)
            if t.status in (TripStatus.SCHEDULED, TripStatus.CANCELLED_PICO_PLACA)
        ]
        taken = await booked_seats(self.session, [t.id for t in trips])
        days = []
        for trip in trips:
            free = max(0, trip.seats_total - taken.get(trip.id, 0))
            days.append(
                AvailabilityDay(
                    trip_id=trip.id,
                    date=local_date(trip.departs_at),
                    departs_at=trip.departs_at,
                    status=trip.status,
                    seats_available=free if trip.status == TripStatus.SCHEDULED else 0,
                    bookable=trip.status == TripStatus.SCHEDULED and free >= seats,
                )
            )
        return SeriesAvailability(
            series_id=series.id,
            options=await self.settings.get("subscription_options_days"),
            days=days,
        )

    # --- Solicitar --------------------------------------------------------------------

    async def request(
        self, passenger: User, series_id: uuid.UUID, data: SubscriptionCreate
    ) -> SeriesSubscription:
        series = await self.active_series(passenger, series_id)
        if series.driver_id == passenger.id:
            raise AppError("BOOKING_OWN_TRIP", "You cannot join your own series", 409)
        check_compatibility(
            passenger, [(r["kind"], r["value"]) for r in series.rules], data.preferences
        )
        await require_can_book(self.session, passenger)
        existing = await self.session.scalar(
            select(SeriesSubscription.id).where(
                SeriesSubscription.series_id == series.id,
                SeriesSubscription.passenger_id == passenger.id,
                SeriesSubscription.status.in_(OPEN),
            )
        )
        if existing is not None:
            raise subscription_exists()
        options = await self.settings.get("subscription_options_days")
        if data.option not in options:
            raise AppError(
                "SUBSCRIPTION_OPTION_INVALID", "Range not allowed", 422, {"options": options}
            )
        start = max(data.start_date, local_today())
        if data.start_date < local_today() or start > series.window_end:
            raise AppError(
                "SUBSCRIPTION_OUT_OF_RANGE",
                "The start date is outside the series",
                422,
                {"window_end": series.window_end.isoformat()},
            )
        end = subscription_range(start, data.option, series)
        trips = [
            t
            for t in await series_trips(self.session, series.id, start, end)
            if t.status == TripStatus.SCHEDULED
        ]
        if not trips:
            raise AppError("SUBSCRIPTION_EMPTY", "There are no trips in that range", 422)
        places = await resolve_places(self.session, passenger, data)
        await self.bookings.meeting(trips[0], *places)

        hours = int(await self.settings.get("pending_request_hours"))
        sub = SeriesSubscription(
            series_id=series.id,
            passenger_id=passenger.id,
            from_date=start,
            to_date=end,
            seats=data.seats,
            pickup_place_id=places[0].id,
            dropoff_place_id=places[1].id,
            preferences=data.preferences.model_dump(),
            status=SubscriptionStatus.REQUESTED,
            expires_at=min(utcnow() + timedelta(hours=hours), trips[0].departs_at),
        )
        await add_unique(self.session, sub, subscription_exists())
        self.notifications.notify(
            series.driver_id,
            Kind.SUBSCRIPTION_REQUESTED,
            {"series_id": str(series.id), "subscription_id": str(sub.id)},
        )
        await self.session.commit()
        return await self.reload(sub.id)

    # --- Decision del conductor --------------------------------------------------------

    async def get_for_driver(self, driver: User, subscription_id: uuid.UUID) -> SeriesSubscription:
        sub = await self.session.get(SeriesSubscription, subscription_id)
        if sub is None or sub.series.driver_id != driver.id:
            raise NotFoundError("subscription")
        return sub

    @staticmethod
    def require_pending(sub: SeriesSubscription) -> None:
        if sub.status != SubscriptionStatus.REQUESTED or sub.expires_at <= utcnow():
            raise AppError(
                "SUBSCRIPTION_NOT_PENDING",
                "The request was already decided or expired",
                409,
                {"status": sub.status},
            )

    async def accept(self, driver: User, subscription_id: uuid.UUID) -> SeriesSubscription:
        """Crea las reservas aceptadas de cada ocurrencia del rango con cupo.

        Bloquea las ocurrencias en orden de id (evita interbloqueos con otras aceptaciones)
        y omite las llenas, en pico y placa, ya reservadas o que se cruzan con otro viaje.
        """
        sub = await self.get_for_driver(driver, subscription_id)
        self.require_pending(sub)
        passenger = sub.passenger
        data = SubscriptionCreate(
            option="series",
            start_date=sub.from_date,
            seats=sub.seats,
            pickup_place_id=sub.pickup_place_id,
            dropoff_place_id=sub.dropoff_place_id,
            preferences=Preferences(**sub.preferences),
        )
        places = (sub.pickup_place, sub.dropoff_place)
        candidates = await series_trips(self.session, sub.series_id, sub.from_date, sub.to_date)
        booked: list[date] = []
        for trip_id in sorted(t.id for t in candidates):
            await lock_trip(self.session, trip_id)
        for trip in candidates:
            day = local_date(trip.departs_at)
            if trip.status != TripStatus.SCHEDULED:
                continue
            if await self.bookings.has_active(passenger.id, trip.id):
                continue
            if await seats_left(self.session, trip) < sub.seats:
                continue
            try:
                meeting = await self.bookings.meeting(trip, *places)
                booking = await self.bookings.build(
                    passenger,
                    trip,
                    data,
                    places,
                    meeting,
                    status=BookingStatus.ACCEPTED,
                    subscription_id=sub.id,
                )
            except AppError:
                continue  # Fuera de la ruta o cruzada con otra reserva del pasajero.
            self.session.add(booking)
            await self.session.flush()
            booking.trip = trip
            await join_trip_chats(self.session, booking)
            booked.append(day)
        sub.status = SubscriptionStatus.ACTIVE
        sub.decided_at = utcnow()
        skipped = sorted({local_date(t.departs_at) for t in candidates} - set(booked))
        self.notifications.notify(
            sub.passenger_id,
            Kind.SUBSCRIPTION_ACCEPTED,
            {
                "series_id": str(sub.series_id),
                "subscription_id": str(sub.id),
                "booked": len(booked),
                "skipped_dates": [d.isoformat() for d in skipped],
            },
        )
        await self.session.commit()
        return await self.reload(sub.id)

    async def reject(
        self, driver: User, subscription_id: uuid.UUID, reason: str | None
    ) -> SeriesSubscription:
        sub = await self.get_for_driver(driver, subscription_id)
        self.require_pending(sub)
        sub.status = SubscriptionStatus.REJECTED
        sub.decided_at = utcnow()
        sub.reject_reason = reason.strip() if reason else None
        self.notifications.notify(
            sub.passenger_id,
            Kind.SUBSCRIPTION_REJECTED,
            {"series_id": str(sub.series_id), "subscription_id": str(sub.id), "reason": reason},
        )
        await self.session.commit()
        return await self.reload(sub.id)

    # --- Cancelacion del pasajero ------------------------------------------------------

    async def cancel(
        self, passenger: User, subscription_id: uuid.UUID, reason: str | None
    ) -> SeriesSubscription:
        """Termina la suscripcion y cancela sus reservas futuras una por una con las reglas de
        cancelacion: las tardias quedan como solicitud al conductor."""
        sub = await self.session.get(SeriesSubscription, subscription_id)
        if sub is None or sub.passenger_id != passenger.id:
            raise NotFoundError("subscription")
        if sub.status not in OPEN:
            raise AppError(
                "SUBSCRIPTION_NOT_ACTIVE",
                "The subscription is not active",
                409,
                {"status": sub.status},
            )
        rules = await cancel_rules(self.session)
        bookings = (
            await self.session.scalars(
                select(Booking)
                .join(Trip, Trip.id == Booking.trip_id)
                .where(
                    Booking.subscription_id == sub.id,
                    Booking.status.in_((BookingStatus.REQUESTED, BookingStatus.ACCEPTED)),
                    Trip.status == TripStatus.SCHEDULED,
                    Trip.departs_at > utcnow(),
                )
                .order_by(Trip.departs_at)
            )
        ).all()
        late = [b for b in bookings if not rules.free(b, utcnow())]
        if late and not reason:
            raise AppError(
                "CANCEL_REASON_REQUIRED",
                "Some trips are too close: the driver needs a reason",
                422,
                {"late_trips": len(late), "cancel_free_hours": rules.free_hours},
            )
        for booking in bookings:
            await self.bookings.cancel_one(booking, reason, rules, notify=False)
        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_at = utcnow()
        self.notifications.notify(
            sub.series.driver_id,
            Kind.SUBSCRIPTION_CANCELLED,
            {
                "series_id": str(sub.series_id),
                "subscription_id": str(sub.id),
                "late_requests": len(late),
            },
        )
        await self.session.commit()
        return await self.reload(sub.id)

    # --- Listas -----------------------------------------------------------------------

    async def list_mine(self, passenger: User) -> list[SubscriptionOut]:
        rows = (
            await self.session.scalars(
                select(SeriesSubscription)
                .where(SeriesSubscription.passenger_id == passenger.id)
                .order_by(SeriesSubscription.created_at.desc())
            )
        ).all()
        return await subscription_outs(self.session, rows)

    async def pending_for_driver(self, driver: User) -> list[SubscriptionOut]:
        rows = (
            await self.session.scalars(
                select(SeriesSubscription)
                .join(TripSeries, TripSeries.id == SeriesSubscription.series_id)
                .where(
                    TripSeries.driver_id == driver.id,
                    SeriesSubscription.status == SubscriptionStatus.REQUESTED,
                    SeriesSubscription.expires_at > utcnow(),
                )
                .order_by(SeriesSubscription.created_at)
            )
        ).all()
        return await subscription_outs(self.session, rows)

    async def get_visible(self, viewer: User, subscription_id: uuid.UUID) -> SeriesSubscription:
        sub = await self.session.get(SeriesSubscription, subscription_id)
        if sub is None or viewer.id not in (sub.passenger_id, sub.series.driver_id):
            raise NotFoundError("subscription")
        return sub
