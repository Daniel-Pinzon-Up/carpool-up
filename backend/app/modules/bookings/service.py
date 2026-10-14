"""Reservas: solicitar, aceptar con bloqueo, rechazar, cancelar y bandeja (seccion 7.5)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.db import add_unique
from app.core.enums import BookingStatus, RuleKind, Sex, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.bookings.matching import Meeting, apply_meeting, meeting_points
from app.modules.bookings.models import ACTIVE_STATUSES, HOLDING_STATUSES, Booking
from app.modules.bookings.queries import lock_trip, seats_left
from app.modules.bookings.schemas import (
    BookingOut,
    CancellationOut,
    MeetingPoint,
    PassengerCard,
    PointsIn,
    Preferences,
    TripBrief,
)
from app.modules.chat.membership import announce_joined
from app.modules.notifications.service import Kind, NotificationService
from app.modules.places.models import Place
from app.modules.routing.schemas import RoutePoint
from app.modules.routing.service import resolve_points
from app.modules.search.service import Point
from app.modules.settings.service import SettingsService
from app.modules.stats.summary import UserSummary, stats_for
from app.modules.trips.models import Trip
from app.modules.trips.schemas import ALLOWED, NOT_ALLOWED, DriverOut, VehicleSummary
from app.modules.users.models import User

# Preferencia del pasajero -> (regla del viaje, valor que la contradice).
PREFERENCE_CONFLICTS = {
    "pets": (RuleKind.PETS, NOT_ALLOWED),
    "luggage": (RuleKind.LUGGAGE, NOT_ALLOWED),
    "no_smoking": (RuleKind.SMOKING, ALLOWED),
    "music": (RuleKind.MUSIC, NOT_ALLOWED),
}


def check_compatibility(
    passenger: User, rules: Sequence[tuple[str, str]], preferences: Preferences
) -> None:
    """Solo mujeres para viajes de solo mujeres y preferencias que las reglas no prohiben."""
    kinds = dict(rules)
    if RuleKind.WOMEN_ONLY in kinds and passenger.sex != Sex.FEMALE:
        raise AppError("WOMEN_ONLY_TRIP", "Only women can book this trip", 403)
    wanted = preferences.model_dump()
    conflicts = [
        name
        for name, (kind, value) in PREFERENCE_CONFLICTS.items()
        if wanted[name] and kinds.get(kind) == value
    ]
    if conflicts:
        raise AppError(
            "PREFERENCES_CONFLICT",
            "The trip rules do not allow these preferences",
            422,
            {"preferences": conflicts},
        )


def trip_rules(trip: Trip) -> list[tuple[str, str]]:
    return [(rule["kind"], rule["value"]) for rule in trip.rules]


def require_can_book(passenger: User) -> None:
    """Las ausencias repetidas suspenden las reservas unos dias (booking_ban_until)."""
    ban = passenger.booking_ban_until
    if ban is not None and ban > utcnow():
        raise AppError(
            "BOOKING_SUSPENDED",
            "Bookings are suspended for this account",
            403,
            {"ends_at": ban.isoformat()},
        )


async def resolve_places(
    session: AsyncSession, passenger: User, data: PointsIn
) -> tuple[Place, Place]:
    """Lugares del catalogo o pines propios dentro del area de servicio."""
    await resolve_points(
        session,
        [RoutePoint(place_id=data.pickup_place_id), RoutePoint(place_id=data.dropoff_place_id)],
        passenger,
    )
    pickup = await session.get(Place, data.pickup_place_id)
    dropoff = await session.get(Place, data.dropoff_place_id)
    assert pickup is not None and dropoff is not None  # noqa: S101 - validados arriba
    return pickup, dropoff


async def overlapping_booking(
    session: AsyncSession,
    passenger_id: uuid.UUID,
    start: datetime,
    end: datetime,
    exclude_trip: uuid.UUID,
) -> Booking | None:
    """Otra reserva activa del pasajero cuyo tramo (recogida a bajada) se cruza con este."""
    return await session.scalar(
        select(Booking)
        .where(
            Booking.passenger_id == passenger_id,
            Booking.status.in_(ACTIVE_STATUSES),
            Booking.trip_id != exclude_trip,
            Booking.pickup_eta < end,
            Booking.dropoff_eta > start,
        )
        .limit(1)
    )


def is_late(trip: Trip, now: datetime, late_minutes: int) -> bool:
    """El conductor no inicio el viaje driver_late_minutes despues de la hora."""
    return trip.status == TripStatus.SCHEDULED and now >= trip.departs_at + timedelta(
        minutes=late_minutes
    )


@dataclass(frozen=True)
class CancelRules:
    free_hours: int
    late_minutes: int

    def free(self, booking: Booking, now: datetime) -> bool:
        """Cancelar ahora es directo (sin pedir permiso al conductor)."""
        if booking.status == BookingStatus.REQUESTED:
            return True
        if booking.status != BookingStatus.ACCEPTED:
            return False
        trip = booking.trip
        return (
            booking.penalty_free
            or trip.departs_at - now >= timedelta(hours=self.free_hours)
            or is_late(trip, now, self.late_minutes)
        )


async def cancel_rules(session: AsyncSession) -> CancelRules:
    settings = SettingsService(session)
    return CancelRules(
        int(await settings.get("cancel_free_hours")),
        int(await settings.get("driver_late_minutes")),
    )


# --- Respuestas -----------------------------------------------------------------------


def vehicle_for(trip: Trip, viewer: User, booking: Booking | None) -> VehicleSummary:
    """La placa la ven el conductor y el pasajero con reserva aceptada (o ya completada)."""
    vehicle = trip.vehicle
    sees_plate = vehicle.owner_id == viewer.id or (
        booking is not None
        and booking.passenger_id == viewer.id
        and booking.status in (*HOLDING_STATUSES, BookingStatus.COMPLETED)
    )
    return VehicleSummary(
        id=vehicle.id,
        type=vehicle.type,
        brand=vehicle.brand,
        model=vehicle.model,
        color=vehicle.color,
        has_photo=vehicle.photo_path is not None,
        plate=vehicle.plate if sees_plate else None,
    )


def trip_brief(trip: Trip, viewer: User, booking: Booking | None = None) -> TripBrief:
    return TripBrief(
        id=trip.id,
        status=trip.status,
        departs_at=trip.departs_at,
        arrives_at=trip.departs_at + timedelta(seconds=trip.est_duration_s),
        origin=trip.stops[0].place.name,
        destination=trip.stops[-1].place.name,
        price_per_seat=trip.price_per_seat,
        driver=DriverOut(id=trip.driver.id, full_name=trip.driver.full_name),
        vehicle=vehicle_for(trip, viewer, booking),
    )


def passenger_card(user: User, stats: UserSummary) -> PassengerCard:
    return PassengerCard(
        id=user.id,
        full_name=user.full_name,
        program=user.program,
        rating=stats.rating_avg,
        trips_as_passenger=stats.trips_as_passenger,
    )


def meeting_out(booking: Booking, pickup: bool) -> MeetingPoint:
    prefix = "pickup" if pickup else "dropoff"
    place: Place = getattr(booking, f"{prefix}_place")
    name = getattr(booking, f"{prefix}_name")
    return MeetingPoint(
        place_id=place.id,
        place_name=place.name,
        kind="stop" if name is not None else "route",
        name=name,
        lat=getattr(booking, f"{prefix}_lat"),
        lon=getattr(booking, f"{prefix}_lon"),
        eta=getattr(booking, f"{prefix}_eta"),
        walk_m=getattr(booking, f"{prefix}_walk_m"),
    )


async def booking_outs(
    session: AsyncSession, bookings: Sequence[Booking], viewer: User
) -> list[BookingOut]:
    if not bookings:
        return []
    counts = await stats_for(session, {b.passenger_id for b in bookings})
    rules = await cancel_rules(session)
    now = utcnow()
    outs = []
    for booking in bookings:
        trip = booking.trip
        accepted = booking.status in HOLDING_STATUSES
        outs.append(
            BookingOut(
                id=booking.id,
                trip=trip_brief(trip, viewer, booking),
                passenger=passenger_card(booking.passenger, counts[booking.passenger_id]),
                seats=booking.seats,
                amount=booking.seats * trip.price_per_seat,
                status=booking.status,
                pickup=meeting_out(booking, pickup=True),
                dropoff=meeting_out(booking, pickup=False),
                preferences=Preferences(**booking.preferences),
                expires_at=booking.expires_at,
                penalty_free=booking.penalty_free,
                free_cancel=rules.free(booking, now),
                created_at=booking.created_at,
                decided_at=booking.decided_at,
                boarded_at=booking.boarded_at,
                no_show_at=booking.no_show_at,
                cancelled_at=booking.cancelled_at,
                cancel_reason=booking.cancel_reason,
                cancellation=(
                    CancellationOut(reason=booking.cancel_reason)
                    if booking.status == BookingStatus.CANCEL_REQUESTED
                    else None
                ),
                payment_note=trip.driver.payment_note
                if accepted and booking.passenger_id == viewer.id
                else None,
            )
        )
    return outs


# --- Servicio -------------------------------------------------------------------------


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)
        self.notifications = NotificationService(session)

    async def out(self, booking: Booking, viewer: User) -> BookingOut:
        return (await booking_outs(self.session, [booking], viewer))[0]

    async def reload(self, booking_id: uuid.UUID) -> Booking:
        booking = await self.session.scalar(
            select(Booking)
            .where(Booking.id == booking_id)
            .execution_options(populate_existing=True)
        )
        if booking is None:
            raise NotFoundError("booking")
        return booking

    # --- Solicitar --------------------------------------------------------------------

    @staticmethod
    def require_bookable(trip: Trip | None, passenger: User) -> Trip:
        if trip is None or trip.deleted_at is not None:
            raise NotFoundError("trip")
        if trip.driver_id == passenger.id:
            raise AppError("BOOKING_OWN_TRIP", "You cannot book your own trip", 409)
        if trip.status != TripStatus.SCHEDULED or trip.departs_at <= utcnow():
            raise AppError(
                "TRIP_NOT_BOOKABLE",
                "The trip is not open for bookings",
                409,
                {"status": trip.status},
            )
        return trip

    async def meeting(self, trip: Trip, pickup: Place, dropoff: Place) -> Meeting:
        radius = int(await self.settings.get("search_radius_meters"))
        meeting = await meeting_points(
            self.session,
            trip,
            Point(pickup.lat, pickup.lon),
            Point(dropoff.lat, dropoff.lon),
            radius,
        )
        if not meeting.on_route:
            raise AppError(
                "POINTS_OFF_ROUTE",
                "The pick-up and drop-off are not along this trip",
                422,
                {"radius_m": radius},
            )
        return meeting

    async def build(
        self,
        passenger: User,
        trip: Trip,
        data: PointsIn,
        places: tuple[Place, Place],
        meeting: Meeting,
        *,
        status: BookingStatus = BookingStatus.REQUESTED,
    ) -> Booking:
        """Reserva lista para agregar; comprueba que no se cruce con otra del pasajero."""
        clash = await overlapping_booking(
            self.session, passenger.id, meeting.pickup.eta, meeting.dropoff.eta, trip.id
        )
        if clash is not None:
            raise AppError(
                "BOOKING_OVERLAP",
                "You already have a booking at that time",
                409,
                {"booking_id": str(clash.id), "trip_id": str(clash.trip_id)},
            )
        now = utcnow()
        hours = int(await self.settings.get("pending_request_hours"))
        booking = Booking(
            trip_id=trip.id,
            passenger_id=passenger.id,
            seats=data.seats,
            pickup_place_id=places[0].id,
            dropoff_place_id=places[1].id,
            preferences=data.preferences.model_dump(),
            status=status,
            expires_at=min(now + timedelta(hours=hours), trip.departs_at),
            decided_at=now if status == BookingStatus.ACCEPTED else None,
        )
        apply_meeting(booking, meeting)
        return booking

    async def has_active(self, passenger_id: uuid.UUID, trip_id: uuid.UUID) -> bool:
        found = await self.session.scalar(
            select(Booking.id).where(
                Booking.trip_id == trip_id,
                Booking.passenger_id == passenger_id,
                Booking.status.in_(ACTIVE_STATUSES),
            )
        )
        return found is not None

    async def request(self, passenger: User, trip_id: uuid.UUID, data: PointsIn) -> Booking:
        """Queda en requested y no aparta cupo hasta que el conductor acepte."""
        trip = self.require_bookable(await self.session.get(Trip, trip_id), passenger)
        check_compatibility(passenger, trip_rules(trip), data.preferences)
        require_can_book(passenger)
        if await self.has_active(passenger.id, trip.id):
            raise AppError("BOOKING_EXISTS", "You already have a booking on this trip", 409)
        free = await seats_left(self.session, trip)
        if free < data.seats:
            raise AppError("TRIP_FULL", "Not enough seats left", 409, {"seats_available": free})
        places = await resolve_places(self.session, passenger, data)
        meeting = await self.meeting(trip, *places)
        booking = await self.build(passenger, trip, data, places, meeting)
        await add_unique(
            self.session,
            booking,
            AppError("BOOKING_EXISTS", "You already have a booking on this trip", 409),
        )
        self.notifications.notify(
            trip.driver_id,
            Kind.BOOKING_REQUESTED,
            {"trip_id": str(trip.id), "booking_id": str(booking.id), "seats": booking.seats},
        )
        await self.session.commit()
        return await self.reload(booking.id)

    # --- Decision del conductor --------------------------------------------------------

    async def get_for_driver(self, driver: User, booking_id: uuid.UUID) -> Booking:
        booking = await self.session.get(Booking, booking_id)
        if booking is None or booking.trip.driver_id != driver.id:
            raise NotFoundError("booking")
        return booking

    async def accept(self, driver: User, booking_id: uuid.UUID) -> Booking:
        """Bloquea el viaje (SELECT ... FOR UPDATE) y verifica el cupo antes de aceptar."""
        booking = await self.get_for_driver(driver, booking_id)
        trip = await lock_trip(self.session, booking.trip_id)
        booking = await self.reload(booking.id)
        if booking.status != BookingStatus.REQUESTED:
            raise AppError(
                "BOOKING_NOT_PENDING",
                "The request was already decided",
                409,
                {"status": booking.status},
            )
        if trip.status != TripStatus.SCHEDULED or trip.departs_at <= utcnow():
            raise AppError("TRIP_NOT_BOOKABLE", "The trip is not open for bookings", 409)
        free = await seats_left(self.session, trip)
        if free < booking.seats:
            raise AppError("TRIP_FULL", "Not enough seats left", 409, {"seats_available": free})
        booking.status = BookingStatus.ACCEPTED
        booking.decided_at = utcnow()
        announce_joined(self.session, booking)
        self.notifications.notify(
            booking.passenger_id,
            Kind.BOOKING_ACCEPTED,
            {"trip_id": str(trip.id), "booking_id": str(booking.id)},
        )
        await self.session.commit()
        return await self.reload(booking.id)

    async def reject(self, driver: User, booking_id: uuid.UUID, reason: str | None) -> Booking:
        booking = await self.get_for_driver(driver, booking_id)
        if booking.status != BookingStatus.REQUESTED:
            raise AppError(
                "BOOKING_NOT_PENDING",
                "The request was already decided",
                409,
                {"status": booking.status},
            )
        booking.status = BookingStatus.REJECTED
        booking.decided_at = utcnow()
        booking.cancel_reason = reason.strip() if reason else None
        self.notifications.notify(
            booking.passenger_id,
            Kind.BOOKING_REJECTED,
            {"trip_id": str(booking.trip_id), "booking_id": str(booking.id), "reason": reason},
        )
        await self.session.commit()
        return await self.reload(booking.id)

    # --- Cancelacion del pasajero ------------------------------------------------------

    async def get_own(self, passenger: User, booking_id: uuid.UUID) -> Booking:
        booking = await self.session.get(Booking, booking_id)
        if booking is None or booking.passenger_id != passenger.id:
            raise NotFoundError("booking")
        return booking

    async def cancel(self, passenger: User, booking_id: uuid.UUID, reason: str | None) -> Booking:
        booking = await self.get_own(passenger, booking_id)
        await self.cancel_one(booking, reason, await cancel_rules(self.session))
        await self.session.commit()
        return await self.reload(booking.id)

    async def cancel_one(
        self, booking: Booking, reason: str | None, rules: CancelRules, *, notify: bool = True
    ) -> BookingStatus:
        """Cancelacion libre (solicitud sin aceptar, con antelacion, viaje cambiado o
        conductor retrasado) o solicitud de cancelacion tardia al conductor. Sin commit."""
        if booking.status == BookingStatus.CANCEL_REQUESTED:
            raise AppError("CANCELLATION_PENDING", "A cancellation is already pending", 409)
        if booking.status not in (BookingStatus.REQUESTED, BookingStatus.ACCEPTED):
            raise AppError(
                "BOOKING_NOT_CANCELLABLE",
                "This booking can no longer be cancelled",
                409,
                {"status": booking.status},
            )
        if booking.trip.status not in (TripStatus.SCHEDULED,):
            raise AppError(
                "BOOKING_NOT_CANCELLABLE",
                "The trip already started",
                409,
                {"trip_status": booking.trip.status},
            )
        now = utcnow()
        payload: dict[str, Any] = {"trip_id": str(booking.trip_id), "booking_id": str(booking.id)}
        if rules.free(booking, now):
            was_holding = booking.status == BookingStatus.ACCEPTED
            booking.status = BookingStatus.CANCELLED_BY_PASSENGER
            booking.cancelled_at = now
            booking.cancel_reason = reason.strip() if reason else None
            if notify:
                kind = (
                    Kind.BOOKING_CANCELLED_BY_PASSENGER if was_holding else Kind.BOOKING_WITHDRAWN
                )
                self.notifications.notify(booking.trip.driver_id, kind, payload)
            return booking.status
        if not reason:
            raise AppError(
                "CANCEL_REASON_REQUIRED",
                "A late cancellation needs a reason for the driver",
                422,
                {"cancel_free_hours": rules.free_hours},
            )
        booking.status = BookingStatus.CANCEL_REQUESTED
        booking.cancel_reason = reason.strip()
        self.notifications.notify(booking.trip.driver_id, Kind.CANCELLATION_REQUESTED, payload)
        return booking.status

    async def resolve_cancellation(
        self, driver: User, booking_id: uuid.UUID, accept: bool
    ) -> Booking:
        """El conductor decide la cancelacion tardia que pidio el pasajero."""
        booking = await self.get_for_driver(driver, booking_id)
        if booking.status != BookingStatus.CANCEL_REQUESTED:
            raise AppError("CANCELLATION_NOT_PENDING", "The cancellation was already decided", 409)
        payload = {"trip_id": str(booking.trip_id), "booking_id": str(booking.id)}
        if accept:
            booking.status = BookingStatus.CANCELLED_BY_PASSENGER
            booking.cancelled_at = utcnow()
            self.notifications.notify(booking.passenger_id, Kind.CANCELLATION_ACCEPTED, payload)
        else:
            booking.status = BookingStatus.ACCEPTED
            booking.cancel_reason = None
            self.notifications.notify(booking.passenger_id, Kind.CANCELLATION_REJECTED, payload)
        await self.session.commit()
        return await self.reload(booking.id)

    # --- Listas -----------------------------------------------------------------------

    async def get_visible(self, viewer: User, booking_id: uuid.UUID) -> Booking:
        booking = await self.session.get(Booking, booking_id)
        if booking is None or viewer.id not in (booking.passenger_id, booking.trip.driver_id):
            raise NotFoundError("booking")
        return booking

    async def list_mine(
        self, passenger: User, scope: str, limit: int, cursor: str | None
    ) -> Page[BookingOut]:
        """upcoming: reservas activas de viajes que no han terminado, por hora de recogida.
        history: el resto, de la mas reciente a la mas antigua."""
        now = utcnow()
        query = (
            select(Booking)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(Booking.passenger_id == passenger.id)
        )
        upcoming = scope == "upcoming"
        active = and_(
            Booking.status.in_(ACTIVE_STATUSES),
            Trip.status.in_((TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)),
            Trip.departs_at >= now - timedelta(hours=3),
        )
        query = query.where(active if upcoming else ~active)
        if cursor:
            at, row_id = decode_cursor(cursor)
            if upcoming:
                query = query.where(
                    or_(
                        Booking.pickup_eta > at, and_(Booking.pickup_eta == at, Booking.id > row_id)
                    )
                )
            else:
                query = query.where(
                    or_(
                        Booking.pickup_eta < at, and_(Booking.pickup_eta == at, Booking.id < row_id)
                    )
                )
        order = (
            (Booking.pickup_eta.asc(), Booking.id.asc())
            if upcoming
            else (Booking.pickup_eta.desc(), Booking.id.desc())
        )
        rows = list((await self.session.scalars(query.order_by(*order).limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return Page(
            items=await booking_outs(self.session, rows, passenger),
            next_cursor=encode_cursor(rows[-1].pickup_eta, rows[-1].id) if has_more else None,
        )

    async def list_for_trip(self, driver: User, trip_id: uuid.UUID) -> list[BookingOut]:
        trip = await self.session.get(Trip, trip_id)
        if trip is None or trip.driver_id != driver.id:
            raise NotFoundError("trip")
        rows = (
            await self.session.scalars(
                select(Booking)
                .where(Booking.trip_id == trip_id)
                .order_by(Booking.pickup_eta, Booking.created_at)
            )
        ).all()
        return await booking_outs(self.session, rows, driver)

    async def pending_for_driver(self, driver: User) -> tuple[list[BookingOut], list[BookingOut]]:
        """Solicitudes y cancelaciones tardias por decidir, de la salida mas proxima."""
        rows = (
            await self.session.scalars(
                select(Booking)
                .join(Trip, Trip.id == Booking.trip_id)
                .where(
                    Trip.driver_id == driver.id,
                    Trip.departs_at > utcnow(),
                    Booking.status.in_((BookingStatus.REQUESTED, BookingStatus.CANCEL_REQUESTED)),
                )
                .order_by(Trip.departs_at, Booking.created_at)
            )
        ).all()
        outs = await booking_outs(self.session, rows, driver)
        requests = [o for o in outs if o.status == BookingStatus.REQUESTED]
        cancellations = [o for o in outs if o.status == BookingStatus.CANCEL_REQUESTED]
        return requests, cancellations
