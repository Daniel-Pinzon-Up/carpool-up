"""Viajes puntuales y ocurrencias: publicar, ver, editar, cancelar y duplicar (seccion 7.2)."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from geoalchemy2.shape import to_shape
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, RuleKind, Sex, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.bookings.lifecycle import end_trip_bookings, trip_changed
from app.modules.bookings.models import ACTIVE_STATUSES, HOLDING_STATUSES, Booking
from app.modules.bookings.queries import active_bookings, booked_seats, pending_requests
from app.modules.chat.service import ChatService
from app.modules.notifications.service import Kind, NotificationService
from app.modules.pico_placa.service import PicoPlacaService
from app.modules.routing.osrm import RouteProvider
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip, TripStop
from app.modules.trips.planning import TripPlanner, local_date
from app.modules.trips.schemas import (
    CoPassenger,
    DriverOut,
    MyBooking,
    MyWaitlist,
    RuleIn,
    RuleOut,
    StopOut,
    TripCreate,
    TripOut,
    TripSummary,
    TripUpdate,
    VehicleSummary,
)
from app.modules.users.models import User
from app.modules.vehicles.eligibility import require_can_publish
from app.modules.vehicles.models import Vehicle
from app.modules.waitlist.models import OPEN_STATUSES as WAITLIST_OPEN
from app.modules.waitlist.models import WaitlistEntry
from app.modules.waitlist.offers import offer_next

logger = structlog.get_logger("trips")

# Lo que un pasajero puede ver de un viaje ajeno.
PUBLIC_STATUSES = (TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)


# --- Respuestas -----------------------------------------------------------------------


def vehicle_summary(vehicle: Vehicle, viewer: User) -> VehicleSummary:
    return VehicleSummary(
        id=vehicle.id,
        type=vehicle.type,
        brand=vehicle.brand,
        model=vehicle.model,
        color=vehicle.color,
        has_photo=vehicle.photo_path is not None,
        plate=vehicle.plate if vehicle.owner_id == viewer.id else None,
    )


def stop_out(stop: TripStop) -> StopOut:
    return StopOut(
        position=stop.position,
        kind=stop.kind,
        place_id=stop.place_id,
        name=stop.place.name,
        lat=stop.place.lat,
        lon=stop.place.lon,
        eta=stop.eta,
    )


def is_editable(trip: Trip, cutoff_minutes: int, now: datetime | None = None) -> bool:
    moment = now or utcnow()
    return (
        trip.status == TripStatus.SCHEDULED
        and trip.deleted_at is None
        and trip.departs_at - timedelta(minutes=cutoff_minutes) > moment
    )


def trip_summary(
    trip: Trip, viewer: User, cutoff_minutes: int, booked: int = 0, pending: int = 0
) -> TripSummary:
    """booked y pending vienen de una consulta por lotes (ver TripService.counts)."""
    own = trip.driver_id == viewer.id
    return TripSummary(
        id=trip.id,
        series_id=trip.series_id,
        status=trip.status,
        departs_at=trip.departs_at,
        arrives_at=trip.departs_at + timedelta(seconds=trip.est_duration_s),
        seats_total=trip.seats_total,
        price_per_seat=trip.price_per_seat,
        origin=trip.stops[0].place.name,
        destination=trip.stops[-1].place.name,
        stop_count=max(0, len(trip.stops) - 2),
        vehicle=vehicle_summary(trip.vehicle, viewer),
        editable=own and is_editable(trip, cutoff_minutes),
        seats_available=max(0, trip.seats_total - booked),
        pending_requests=pending if own else 0,
    )


def trip_out(
    trip: Trip, viewer: User, cutoff_minutes: int, booked: int = 0, pending: int = 0
) -> TripOut:
    line = to_shape(trip.route)
    return TripOut(
        **trip_summary(trip, viewer, cutoff_minutes, booked, pending).model_dump(),
        geometry=[[x, y] for x, y in line.coords],
        distance_m=trip.distance_m,
        est_duration_s=trip.est_duration_s,
        stops=[stop_out(stop) for stop in trip.stops],
        rules=[RuleOut(kind=rule.kind, value=rule.value) for rule in trip.rules],
        driver=DriverOut(id=trip.driver.id, full_name=trip.driver.full_name),
        cancel_reason=trip.cancel_reason,
        cancelled_at=trip.cancelled_at,
    )


def rules_in(trip: Trip) -> list[RuleIn]:
    return [RuleIn(kind=rule.kind, value=rule.value) for rule in trip.rules]


# --- Servicio -------------------------------------------------------------------------


class TripService:
    def __init__(self, session: AsyncSession, provider: RouteProvider) -> None:
        self.session = session
        self.planner = TripPlanner(session, provider)
        self.settings = SettingsService(session)

    async def cutoff_minutes(self) -> int:
        return int(await self.settings.get("trip_edit_cutoff_minutes"))

    async def create(self, driver: User, data: TripCreate) -> Trip:
        await require_can_publish(self.session, driver)
        vehicle = await self.planner.vehicle(driver, data.vehicle_id)
        self.planner.check_seats(vehicle, data.seats)
        await self.planner.check_price(data.price_per_seat)
        rules = self.planner.check_rules(driver, data.rules)
        await self.planner.check_departure(data.departs_at, single=True)
        await self.planner.check_pico_placa(vehicle, data.departs_at)
        planned = await self.planner.plan_route(driver, data.place_ids)

        trip = Trip(
            driver_id=driver.id,
            vehicle_id=vehicle.id,
            seats_total=data.seats,
            price_per_seat=data.price_per_seat,
            status=TripStatus.SCHEDULED,
        )
        await self.planner.apply(trip, planned, data.departs_at, rules)
        await self.planner.check_overlaps(driver.id, [(trip.departs_at, trip.est_duration_s)])
        self.session.add(trip)
        await self.session.commit()
        return await self.reload(trip.id)

    async def reload(self, trip_id: uuid.UUID) -> Trip:
        """Vuelve a leer el viaje con paradas, reglas, vehiculo y conductor."""
        trip = await self.session.scalar(
            select(Trip).where(Trip.id == trip_id).execution_options(populate_existing=True)
        )
        if trip is None:
            raise NotFoundError("trip")
        return trip

    async def get_visible(self, viewer: User, trip_id: uuid.UUID) -> Trip:
        """El conductor ve sus viajes; quien tuvo una reserva, ese viaje; los demas, solo los
        programados o en curso."""
        trip = await self.session.get(Trip, trip_id)
        if trip is None or trip.deleted_at is not None:
            raise NotFoundError("trip")
        if (
            trip.driver_id != viewer.id
            and trip.status not in PUBLIC_STATUSES
            and not await self.took_part(viewer, trip.id)
        ):
            raise NotFoundError("trip")
        return trip

    async def took_part(self, viewer: User, trip_id: uuid.UUID) -> bool:
        booking = await self.session.scalar(
            select(Booking.id)
            .where(Booking.trip_id == trip_id, Booking.passenger_id == viewer.id)
            .limit(1)
        )
        return booking is not None

    async def counts(self, trips: list[Trip]) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        ids = [trip.id for trip in trips]
        return await booked_seats(self.session, ids), await pending_requests(self.session, ids)

    async def view(self, trip: Trip, viewer: User) -> TripOut:
        """Detalle segun quien consulta: el conductor ve las recogidas de sus pasajeros; el
        pasajero aceptado ve placa, datos de pago y companeros; todos ven el cupo."""
        cutoff = await self.cutoff_minutes()
        booked, pending = await self.counts([trip])
        out = trip_out(trip, viewer, cutoff, booked.get(trip.id, 0), pending.get(trip.id, 0))
        own = trip.driver_id == viewer.id
        mine = await self.session.scalar(
            select(Booking)
            .where(Booking.trip_id == trip.id, Booking.passenger_id == viewer.id)
            .order_by(Booking.status.in_(ACTIVE_STATUSES).desc(), Booking.created_at.desc())
            .limit(1)
        )
        riding = (*HOLDING_STATUSES, BookingStatus.COMPLETED)
        accepted = mine is not None and mine.status in riding
        if own or accepted:
            riders = (
                await self.session.scalars(
                    select(Booking)
                    .where(Booking.trip_id == trip.id, Booking.status.in_(riding))
                    .order_by(Booking.pickup_eta)
                )
            ).all()
            out.passengers = [
                CoPassenger(
                    id=b.passenger_id,
                    full_name=b.passenger.full_name,
                    seats=b.seats,
                    pickup_name=b.pickup_name if own else None,
                    pickup_eta=b.pickup_eta if own else None,
                )
                for b in riders
            ]
        if accepted:
            out.vehicle.plate = trip.vehicle.plate
            out.payment_note = trip.driver.payment_note
        if mine is not None:
            out.my_booking = MyBooking(
                id=mine.id,
                status=mine.status,
                seats=mine.seats,
                pickup_name=mine.pickup_name,
                pickup_eta=mine.pickup_eta,
                dropoff_name=mine.dropoff_name,
                dropoff_eta=mine.dropoff_eta,
            )
        entry = await self.session.scalar(
            select(WaitlistEntry).where(
                WaitlistEntry.trip_id == trip.id,
                WaitlistEntry.passenger_id == viewer.id,
                WaitlistEntry.status.in_(WAITLIST_OPEN),
            )
        )
        out.chat_id = await ChatService(self.session).for_trip(viewer, trip.id)
        if entry is not None:
            out.my_waitlist = MyWaitlist(
                id=entry.id,
                status=entry.status,
                seats=entry.seats,
                offer_expires_at=entry.offer_expires_at,
            )
        return out

    async def get_own(self, driver: User, trip_id: uuid.UUID) -> Trip:
        trip = await self.session.get(Trip, trip_id)
        if trip is None or trip.deleted_at is not None or trip.driver_id != driver.id:
            raise NotFoundError("trip")
        return trip

    async def list_mine(
        self, driver: User, scope: str, limit: int, cursor: str | None
    ) -> Page[TripSummary]:
        """upcoming: programados y en curso, del mas proximo al mas lejano.
        history: el resto, del mas reciente al mas antiguo. Cursor sobre (departs_at, id).
        """
        now = utcnow()
        query = select(Trip).where(Trip.driver_id == driver.id, Trip.deleted_at.is_(None))
        upcoming = scope == "upcoming"
        active = or_(
            Trip.status == TripStatus.IN_PROGRESS,
            and_(Trip.status == TripStatus.SCHEDULED, Trip.departs_at >= now - timedelta(hours=3)),
        )
        query = query.where(active if upcoming else ~active)
        if cursor:
            at, row_id = decode_cursor(cursor)
            if upcoming:
                query = query.where(
                    or_(Trip.departs_at > at, and_(Trip.departs_at == at, Trip.id > row_id))
                )
            else:
                query = query.where(
                    or_(Trip.departs_at < at, and_(Trip.departs_at == at, Trip.id < row_id))
                )
        order = (
            (Trip.departs_at.asc(), Trip.id.asc())
            if upcoming
            else (Trip.departs_at.desc(), Trip.id.desc())
        )
        rows = list((await self.session.scalars(query.order_by(*order).limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        cutoff = await self.cutoff_minutes()
        booked, pending = await self.counts(rows)
        return Page(
            items=[
                trip_summary(trip, driver, cutoff, booked.get(trip.id, 0), pending.get(trip.id, 0))
                for trip in rows
            ],
            next_cursor=encode_cursor(rows[-1].departs_at, rows[-1].id) if has_more else None,
        )

    async def require_editable(self, trip: Trip) -> None:
        cutoff = await self.cutoff_minutes()
        if not is_editable(trip, cutoff):
            raise AppError(
                "TRIP_NOT_EDITABLE",
                "The trip can no longer be changed",
                409,
                {"status": trip.status, "cutoff_minutes": cutoff},
            )

    async def update(self, driver: User, trip_id: uuid.UUID, data: TripUpdate) -> Trip:
        """Hasta trip_edit_cutoff_minutes antes de salir.

        Los puestos no bajan de los ya aceptados. Si cambian hora, ruta, vehiculo o aporte se
        recalcula el punto de encuentro de cada reserva y los pasajeros pueden cancelar sin
        penalizacion. Si suben los puestos se ofrece el cupo a la lista de espera.
        """
        trip = await self.get_own(driver, trip_id)
        await self.require_editable(trip)
        await require_can_publish(self.session, driver)

        vehicle = (
            await self.planner.vehicle(driver, data.vehicle_id)
            if data.vehicle_id is not None
            else trip.vehicle
        )
        seats = data.seats if data.seats is not None else trip.seats_total
        self.planner.check_seats(vehicle, seats)
        price = data.price_per_seat if data.price_per_seat is not None else trip.price_per_seat
        if data.price_per_seat is not None:
            await self.planner.check_price(price)
        rules = self.planner.check_rules(
            driver, data.rules if data.rules is not None else rules_in(trip)
        )
        departs_at = data.departs_at or trip.departs_at
        if data.departs_at is not None:
            await self.planner.check_departure(departs_at, single=trip.series_id is None)
        await self.planner.check_pico_placa(vehicle, departs_at)
        place_ids = data.place_ids or [stop.place_id for stop in trip.stops]
        await check_bookings_fit(self.session, trip, seats, rules)
        planned = await self.planner.plan_route(driver, place_ids)

        before = (
            trip.departs_at,
            [stop.place_id for stop in trip.stops],
            trip.vehicle_id,
            trip.price_per_seat,
        )
        more_seats = seats > trip.seats_total
        trip.vehicle_id = vehicle.id
        trip.vehicle = vehicle
        trip.seats_total = seats
        trip.price_per_seat = price
        await self.planner.apply(trip, planned, departs_at, rules)
        await self.planner.check_overlaps(
            driver.id, [(trip.departs_at, trip.est_duration_s)], exclude={trip.id}
        )
        if before != (trip.departs_at, planned.place_ids, trip.vehicle_id, trip.price_per_seat):
            await trip_changed(self.session, trip)
        if more_seats:
            await offer_next(self.session, trip)
        await self.session.commit()
        return await self.reload(trip.id)

    async def cancel(self, driver: User, trip_id: uuid.UUID, reason: str) -> Trip:
        """Siempre con motivo; cuenta en la reputacion del conductor (paso 11). Las reservas
        pasan a cancelled_by_driver con el mismo motivo y se avisa a los pasajeros."""
        trip = await self.get_own(driver, trip_id)
        if trip.status != TripStatus.SCHEDULED:
            raise AppError(
                "TRIP_NOT_EDITABLE",
                "Only scheduled trips can be cancelled",
                409,
                {"status": trip.status},
            )
        mark_cancelled(trip, reason)
        await end_trip_bookings(self.session, trip, BookingStatus.CANCELLED_BY_DRIVER, reason)
        await self.session.commit()
        return await self.reload(trip.id)

    async def duplicate(self, driver: User, trip_id: uuid.UUID, departs_at: datetime) -> Trip:
        source = await self.get_own(driver, trip_id)
        data = TripCreate(
            place_ids=[stop.place_id for stop in source.stops],
            departs_at=departs_at,
            vehicle_id=source.vehicle_id,
            seats=source.seats_total,
            price_per_seat=source.price_per_seat,
            rules=rules_in(source),
        )
        return await self.create(driver, data)


async def check_bookings_fit(
    session: AsyncSession, trip: Trip, seats: int, rules: list[dict[str, str]]
) -> None:
    """Un cambio no puede dejar afuera a pasajeros ya aceptados ni volver "solo mujeres" un
    viaje con pasajeros que no lo son."""
    booked = (await booked_seats(session, [trip.id])).get(trip.id, 0)
    if seats < booked:
        raise AppError(
            "SEATS_BELOW_BOOKED",
            "There are more accepted seats than that",
            409,
            {"booked": booked, "trip_id": str(trip.id)},
        )
    if any(rule["kind"] == RuleKind.WOMEN_ONLY for rule in rules):
        bookings = await active_bookings(session, trip.id)
        if any(b.passenger.sex != Sex.FEMALE for b in bookings):
            raise AppError(
                "WOMEN_ONLY_CONFLICT",
                "The trip has passengers who are not women",
                409,
                {"trip_id": str(trip.id)},
            )


def mark_cancelled(trip: Trip, reason: str) -> None:
    trip.status = TripStatus.CANCELLED_BY_DRIVER
    trip.cancel_reason = reason.strip()
    trip.cancelled_at = utcnow()


# --- Pico y placa ---------------------------------------------------------------------


@dataclass(frozen=True)
class PicoPlacaRecheck:
    cancelled: int
    restored: int


async def recheck_pico_placa(session: AsyncSession) -> PicoPlacaRecheck:
    """Aplica las reglas vigentes a los viajes futuros (diario y al editar reglas).

    Programados que caen en pico y placa pasan a cancelled_pico_placa; los que ya no caen
    (regla borrada o corregida) vuelven a programados. Se avisa al conductor y las reservas
    de los cancelados pasan a auto_cancelled_pico_placa con aviso a cada pasajero.
    """
    now = utcnow()
    trips = list(
        (
            await session.scalars(
                select(Trip).where(
                    Trip.deleted_at.is_(None),
                    Trip.departs_at > now,
                    Trip.status.in_((TripStatus.SCHEDULED, TripStatus.CANCELLED_PICO_PLACA)),
                )
            )
        ).all()
    )
    by_vehicle: dict[uuid.UUID, list[Trip]] = defaultdict(list)
    for trip in trips:
        by_vehicle[trip.vehicle_id].append(trip)

    pico_placa = PicoPlacaService(session)
    notifications = NotificationService(session)
    cancelled = restored = 0
    for group in by_vehicle.values():
        vehicle = group[0].vehicle
        days = [local_date(trip.departs_at) for trip in group]
        restricted = await pico_placa.restricted_dates(
            vehicle.type, vehicle.plate, min(days), max(days)
        )
        for trip, day in zip(group, days, strict=True):
            payload = {"trip_id": str(trip.id), "date": day.isoformat()}
            if trip.status == TripStatus.SCHEDULED and day in restricted:
                trip.status = TripStatus.CANCELLED_PICO_PLACA
                trip.cancelled_at = now
                notifications.notify(trip.driver_id, Kind.TRIP_PICO_PLACA_CANCELLED, payload)
                await end_trip_bookings(session, trip, BookingStatus.AUTO_CANCELLED_PICO_PLACA)
                cancelled += 1
            elif trip.status == TripStatus.CANCELLED_PICO_PLACA and day not in restricted:
                trip.status = TripStatus.SCHEDULED
                trip.cancelled_at = None
                notifications.notify(trip.driver_id, Kind.TRIP_PICO_PLACA_RESTORED, payload)
                restored += 1
    await session.commit()
    logger.info("pico_placa_recheck", cancelled=cancelled, restored=restored)
    return PicoPlacaRecheck(cancelled, restored)
