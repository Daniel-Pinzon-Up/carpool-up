"""Series recurrentes: ventana dentro del semestre y generacion de ocurrencias (seccion 7.2)."""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today, utcnow
from app.core.enums import BookingStatus, SeriesStatus, SubscriptionStatus, TripStatus
from app.core.errors import AppError, NotFoundError
from app.modules.bookings.lifecycle import end_trip_bookings, trip_changed
from app.modules.bookings.models import ACTIVE_STATUSES, Booking, SeriesSubscription
from app.modules.bookings.queries import booked_seats, pending_requests
from app.modules.notifications.service import Kind, NotificationService
from app.modules.routing.osrm import RouteProvider
from app.modules.semesters.models import Semester
from app.modules.semesters.repository import SemesterRepository
from app.modules.series.models import SeriesStop, TripSeries
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.trips.planning import (
    PlannedRoute,
    TripPlanner,
    local_date,
    local_departure,
    stop_kind,
)
from app.modules.trips.schemas import (
    DriverOut,
    MySubscription,
    OccurrenceCounts,
    RuleIn,
    RuleOut,
    SeriesCreate,
    SeriesOut,
    SeriesSummary,
    SeriesUpdate,
    StopOut,
)
from app.modules.trips.service import (
    check_bookings_fit,
    mark_cancelled,
    trip_summary,
    vehicle_summary,
)
from app.modules.users.models import User
from app.modules.vehicles.eligibility import require_can_publish
from app.modules.vehicles.models import Vehicle
from app.modules.waitlist.offers import offer_next

CANCELLED = (TripStatus.CANCELLED_BY_DRIVER, TripStatus.NOT_HELD)


def series_days(start: date, end: date, weekdays: list[int]) -> list[date]:
    """Fechas del rango [start, end] que caen en los dias de la semana pedidos."""
    wanted = set(weekdays)
    days = (start + timedelta(days=n) for n in range((end - start).days + 1))
    return [day for day in days if day.weekday() in wanted]


def window_end(start: date, window: int | str, semester: Semester) -> date:
    """La ventana nunca pasa del fin del semestre."""
    if window == "semester":
        return semester.ends_on
    return min(start + timedelta(days=int(window) - 1), semester.ends_on)


def counts(trips: list[Trip]) -> OccurrenceCounts:
    statuses = [trip.status for trip in trips]
    return OccurrenceCounts(
        total=len(statuses),
        scheduled=statuses.count(TripStatus.SCHEDULED),
        pico_placa=statuses.count(TripStatus.CANCELLED_PICO_PLACA),
        cancelled=sum(statuses.count(status) for status in CANCELLED),
    )


def template_stop(stop: SeriesStop) -> StopOut:
    return StopOut(
        position=stop.position,
        kind=stop.kind,
        place_id=stop.place_id,
        name=stop.place.name,
        lat=stop.place.lat,
        lon=stop.place.lon,
        eta=None,
    )


class SeriesService:
    def __init__(self, session: AsyncSession, provider: RouteProvider) -> None:
        self.session = session
        self.planner = TripPlanner(session, provider)
        self.settings = SettingsService(session)

    # --- Lectura ------------------------------------------------------------------------

    async def occurrences(self, series_id: uuid.UUID) -> list[Trip]:
        query = (
            select(Trip)
            .where(Trip.series_id == series_id, Trip.deleted_at.is_(None))
            .order_by(Trip.departs_at)
        )
        return list((await self.session.scalars(query)).all())

    async def get_own(self, driver: User, series_id: uuid.UUID) -> TripSeries:
        series = await self.session.get(TripSeries, series_id)
        if series is None or series.driver_id != driver.id:
            raise NotFoundError("series")
        return series

    async def get_visible(self, viewer: User, series_id: uuid.UUID) -> TripSeries:
        """El conductor ve sus series; los demas, solo las activas."""
        series = await self.session.get(TripSeries, series_id)
        if series is None or (
            series.driver_id != viewer.id and series.status != SeriesStatus.ACTIVE
        ):
            raise NotFoundError("series")
        return series

    async def summary(self, series: TripSeries, viewer: User) -> SeriesSummary:
        trips = await self.occurrences(series.id)
        now = utcnow()
        upcoming = [t for t in trips if t.status == TripStatus.SCHEDULED and t.departs_at > now]
        return SeriesSummary(
            id=series.id,
            status=series.status,
            weekdays=series.weekdays,
            departure_time=series.departure_time,
            window_start=series.window_start,
            window_end=series.window_end,
            seats=series.seats,
            price_per_seat=series.price_per_seat,
            origin=series.stops[0].place.name,
            destination=series.stops[-1].place.name,
            vehicle=vehicle_summary(series.vehicle, viewer),
            next_departure=upcoming[0].departs_at if upcoming else None,
            counts=counts(trips),
        )

    async def detail(self, series: TripSeries, viewer: User) -> SeriesOut:
        cutoff = int(await self.settings.get("trip_edit_cutoff_minutes"))
        trips = await self.occurrences(series.id)
        if series.driver_id != viewer.id:
            trips = [t for t in trips if t.status == TripStatus.SCHEDULED]
        summary = await self.summary(series, viewer)
        ids = [trip.id for trip in trips]
        booked = await booked_seats(self.session, ids)
        pending = await pending_requests(self.session, ids)
        mine = await self.session.scalar(
            select(SeriesSubscription)
            .where(
                SeriesSubscription.series_id == series.id,
                SeriesSubscription.passenger_id == viewer.id,
            )
            .order_by(SeriesSubscription.created_at.desc())
            .limit(1)
        )
        return SeriesOut(
            **summary.model_dump(),
            stops=[template_stop(stop) for stop in series.stops],
            rules=[RuleOut(kind=rule["kind"], value=rule["value"]) for rule in series.rules],
            driver=DriverOut(id=series.driver.id, full_name=series.driver.full_name),
            cancel_reason=series.cancel_reason,
            occurrences=[
                trip_summary(trip, viewer, cutoff, booked.get(trip.id, 0), pending.get(trip.id, 0))
                for trip in trips
            ],
            my_subscription=(
                MySubscription(
                    id=mine.id, status=mine.status, from_date=mine.from_date, to_date=mine.to_date
                )
                if mine is not None
                else None
            ),
        )

    async def list_mine(self, driver: User) -> list[SeriesSummary]:
        query = (
            select(TripSeries)
            .where(TripSeries.driver_id == driver.id)
            .order_by(TripSeries.status, TripSeries.window_start.desc())
        )
        return [await self.summary(s, driver) for s in (await self.session.scalars(query)).all()]

    # --- Generacion ---------------------------------------------------------------------

    async def semester_for(self, start: date) -> Semester:
        semester = await SemesterRepository(self.session).containing(start)
        if semester is None:
            raise AppError(
                "SERIES_OUTSIDE_SEMESTER",
                "The start date is not inside an academic semester",
                422,
                {"start_date": start.isoformat()},
            )
        return semester

    async def check_window(self, start: date, window: int | str) -> None:
        options = await self.settings.get("series_window_options_days")
        if window not in options:
            raise AppError("SERIES_WINDOW_INVALID", "Window not allowed", 422, {"options": options})
        if start < local_today():
            raise AppError("SERIES_START_IN_PAST", "The series cannot start in the past", 422)

    async def first_departure(self) -> datetime:
        """Las ocurrencias empiezan despues de la antelacion minima y del corte de edicion."""
        lead = int(await self.settings.get("trip_publish_min_lead_minutes"))
        cutoff = int(await self.settings.get("trip_edit_cutoff_minutes"))
        return utcnow() + timedelta(minutes=max(lead, cutoff))

    async def new_occurrence(
        self,
        series: TripSeries,
        planned: PlannedRoute,
        departs_at: datetime,
        restricted: bool,
    ) -> Trip:
        trip = Trip(
            driver_id=series.driver_id,
            vehicle_id=series.vehicle_id,
            series_id=series.id,
            seats_total=series.seats,
            price_per_seat=series.price_per_seat,
            status=TripStatus.CANCELLED_PICO_PLACA if restricted else TripStatus.SCHEDULED,
            cancelled_at=utcnow() if restricted else None,
        )
        await self.planner.apply(trip, planned, departs_at, series.rules)
        return trip

    async def validated(
        self,
        driver: User,
        vehicle_id: uuid.UUID,
        seats: int,
        price: int,
        rules: list[RuleIn],
        place_ids: list[uuid.UUID],
    ) -> tuple[Vehicle, list[dict[str, str]], PlannedRoute]:
        await require_can_publish(self.session, driver)
        vehicle = await self.planner.vehicle(driver, vehicle_id)
        self.planner.check_seats(vehicle, seats)
        await self.planner.check_price(price)
        normalized = self.planner.check_rules(driver, rules)
        planned = await self.planner.plan_route(driver, place_ids)
        return vehicle, normalized, planned

    @staticmethod
    def set_stops(series: TripSeries, planned: PlannedRoute) -> None:
        count = len(planned.place_ids)
        series.stops = [
            SeriesStop(place_id=place_id, position=n, kind=stop_kind(n, count))
            for n, place_id in enumerate(planned.place_ids)
        ]

    async def create(self, driver: User, data: SeriesCreate) -> TripSeries:
        await self.check_window(data.start_date, data.window)
        semester = await self.semester_for(data.start_date)
        vehicle, rules, planned = await self.validated(
            driver, data.vehicle_id, data.seats, data.price_per_seat, data.rules, data.place_ids
        )
        end = window_end(data.start_date, data.window, semester)
        series = TripSeries(
            driver_id=driver.id,
            vehicle_id=vehicle.id,
            semester_id=semester.id,
            weekdays=data.weekdays,
            departure_time=data.departure_time,
            window_start=data.start_date,
            window_end=end,
            seats=data.seats,
            price_per_seat=data.price_per_seat,
            rules=rules,
            status=SeriesStatus.ACTIVE,
        )
        self.set_stops(series, planned)
        self.session.add(series)
        await self.session.flush()

        first = await self.first_departure()
        departures = [
            local_departure(day, data.departure_time)
            for day in series_days(data.start_date, end, data.weekdays)
        ]
        departures = [at for at in departures if at >= first]
        restricted = await self.planner.restricted_dates(vehicle, data.start_date, end)
        trips = [
            await self.new_occurrence(series, planned, at, local_date(at) in restricted)
            for at in departures
        ]
        if not any(trip.status == TripStatus.SCHEDULED for trip in trips):
            raise AppError(
                "SERIES_EMPTY",
                "The series has no trip that can be published",
                422,
                {"pico_placa_dates": sorted(d.isoformat() for d in restricted)},
            )
        await self.planner.check_overlaps(
            driver.id,
            [(t.departs_at, t.est_duration_s) for t in trips if t.status == TripStatus.SCHEDULED],
        )
        self.session.add_all(trips)
        await self.session.commit()
        return await self.reload(series.id)

    async def reload(self, series_id: uuid.UUID) -> TripSeries:
        series = await self.session.scalar(
            select(TripSeries)
            .where(TripSeries.id == series_id)
            .execution_options(populate_existing=True)
        )
        if series is None:
            raise NotFoundError("series")
        return series

    # --- Edicion ------------------------------------------------------------------------

    def require_active(self, series: TripSeries) -> None:
        if series.status != SeriesStatus.ACTIVE:
            raise AppError(
                "SERIES_NOT_ACTIVE", "The series is not active", 409, {"status": series.status}
            )

    async def update(self, driver: User, series_id: uuid.UUID, data: SeriesUpdate) -> TripSeries:
        """Cambia la plantilla y rehace las ocurrencias futuras (despues del corte de edicion).

        Las fechas que siguen en la serie se actualizan en su lugar; las que salen se quitan y
        las nuevas se crean. Las ocurrencias pasadas, en curso o canceladas no cambian.
        Si alguna ocurrencia futura tiene reservas hay que confirmar (SERIES_HAS_BOOKINGS):
        las fechas que salen cancelan sus reservas y las que cambian avisan a los pasajeros.
        """
        series = await self.get_own(driver, series_id)
        self.require_active(series)
        if not data.confirm:
            await self.require_no_bookings(series)
        rules_source = (
            data.rules
            if data.rules is not None
            else [RuleIn(kind=r["kind"], value=r["value"]) for r in series.rules]
        )
        vehicle, rules, planned = await self.validated(
            driver,
            data.vehicle_id or series.vehicle_id,
            data.seats if data.seats is not None else series.seats,
            data.price_per_seat if data.price_per_seat is not None else series.price_per_seat,
            rules_source,
            data.place_ids or [stop.place_id for stop in series.stops],
        )
        series.vehicle_id = vehicle.id
        series.vehicle = vehicle
        series.weekdays = data.weekdays or series.weekdays
        series.departure_time = data.departure_time or series.departure_time
        if data.seats is not None:
            series.seats = data.seats
        if data.price_per_seat is not None:
            series.price_per_seat = data.price_per_seat
        series.rules = rules
        if data.place_ids:
            series.stops.clear()
            await self.session.flush()
            self.set_stops(series, planned)

        await self.regenerate(series, vehicle, planned)
        await self.session.commit()
        return await self.reload(series.id)

    async def require_no_bookings(self, series: TripSeries) -> None:
        first = await self.first_departure()
        rows = (
            await self.session.execute(
                select(Booking.trip_id, Booking.passenger_id)
                .join(Trip, Trip.id == Booking.trip_id)
                .where(
                    Trip.series_id == series.id,
                    Trip.deleted_at.is_(None),
                    Trip.departs_at >= first,
                    Booking.status.in_(ACTIVE_STATUSES),
                )
            )
        ).all()
        if rows:
            raise AppError(
                "SERIES_HAS_BOOKINGS",
                "Some upcoming trips have bookings: confirm the change",
                409,
                {
                    "trips": len({row.trip_id for row in rows}),
                    "passengers": len({row.passenger_id for row in rows}),
                },
            )

    async def regenerate(self, series: TripSeries, vehicle: Vehicle, planned: PlannedRoute) -> None:
        first = await self.first_departure()
        start = max(series.window_start, local_date(first))
        wanted = {
            local_date(at): at
            for at in (
                local_departure(day, series.departure_time)
                for day in series_days(start, series.window_end, series.weekdays)
            )
            if at >= first
        }
        restricted = await self.planner.restricted_dates(vehicle, start, series.window_end)
        existing = await self.occurrences(series.id)
        taken_days = {local_date(trip.departs_at) for trip in existing}
        future = [
            trip
            for trip in existing
            if trip.departs_at >= first
            and trip.status in (TripStatus.SCHEDULED, TripStatus.CANCELLED_PICO_PLACA)
        ]

        now = utcnow()
        kept: list[Trip] = []
        for trip in future:
            day = local_date(trip.departs_at)
            if day not in wanted:
                trip.deleted_at = now
                taken_days.discard(day)
                await end_trip_bookings(self.session, trip, BookingStatus.CANCELLED_BY_DRIVER)
                continue
            await check_bookings_fit(self.session, trip, series.seats, series.rules)
            before = (
                trip.departs_at,
                [stop.place_id for stop in trip.stops],
                trip.vehicle_id,
                trip.price_per_seat,
            )
            more_seats = series.seats > trip.seats_total
            trip.vehicle_id = vehicle.id
            trip.vehicle = vehicle
            trip.seats_total = series.seats
            trip.price_per_seat = series.price_per_seat
            trip.status = (
                TripStatus.CANCELLED_PICO_PLACA if day in restricted else TripStatus.SCHEDULED
            )
            trip.cancelled_at = now if day in restricted else None
            await self.planner.apply(trip, planned, wanted[day], series.rules)
            if day in restricted:
                await end_trip_bookings(self.session, trip, BookingStatus.AUTO_CANCELLED_PICO_PLACA)
            elif before != (trip.departs_at, planned.place_ids, vehicle.id, trip.price_per_seat):
                await trip_changed(self.session, trip)
            if more_seats:
                await offer_next(self.session, trip)
            kept.append(trip)

        created = [
            await self.new_occurrence(series, planned, at, day in restricted)
            for day, at in sorted(wanted.items())
            if day not in taken_days
        ]
        scheduled = [t for t in kept + created if t.status == TripStatus.SCHEDULED]
        await self.planner.check_overlaps(
            series.driver_id,
            [(t.departs_at, t.est_duration_s) for t in scheduled],
            exclude={t.id for t in existing},
        )
        self.session.add_all(created)

    async def cancel(self, driver: User, series_id: uuid.UUID, reason: str) -> TripSeries:
        """Cancela la serie y todas sus ocurrencias futuras programadas con sus reservas.
        Las suscripciones pendientes se rechazan y las activas terminan."""
        series = await self.get_own(driver, series_id)
        self.require_active(series)
        now = utcnow()
        series.status = SeriesStatus.CANCELLED
        series.cancel_reason = reason.strip()
        series.cancelled_at = now
        for trip in await self.occurrences(series.id):
            if trip.status == TripStatus.SCHEDULED and trip.departs_at > now:
                mark_cancelled(trip, reason)
                await end_trip_bookings(
                    self.session, trip, BookingStatus.CANCELLED_BY_DRIVER, reason
                )
        await self.close_subscriptions(series, reason)
        await self.session.commit()
        return await self.reload(series.id)

    async def close_subscriptions(self, series: TripSeries, reason: str) -> None:
        notifications = NotificationService(self.session)
        subscriptions = (
            await self.session.scalars(
                select(SeriesSubscription).where(
                    SeriesSubscription.series_id == series.id,
                    SeriesSubscription.status.in_(
                        (SubscriptionStatus.REQUESTED, SubscriptionStatus.ACTIVE)
                    ),
                )
            )
        ).all()
        now = utcnow()
        for sub in subscriptions:
            payload = {"series_id": str(series.id), "subscription_id": str(sub.id)}
            if sub.status == SubscriptionStatus.REQUESTED:
                sub.status = SubscriptionStatus.REJECTED
                sub.decided_at = now
                sub.reject_reason = reason.strip()
                notifications.notify(sub.passenger_id, Kind.SUBSCRIPTION_REJECTED, payload)
            else:
                sub.status = SubscriptionStatus.FINISHED
                notifications.notify(sub.passenger_id, Kind.SUBSCRIPTION_ENDED, payload)

    async def duplicate(
        self, driver: User, series_id: uuid.UUID, start: date, window: int | str
    ) -> TripSeries:
        source = await self.get_own(driver, series_id)
        data = SeriesCreate(
            place_ids=[stop.place_id for stop in source.stops],
            weekdays=source.weekdays,
            departure_time=source.departure_time,
            start_date=start,
            window=window,
            vehicle_id=source.vehicle_id,
            seats=source.seats,
            price_per_seat=source.price_per_seat,
            rules=[RuleIn(kind=r["kind"], value=r["value"]) for r in source.rules],
        )
        return await self.create(driver, data)


async def finish_past_series(session: AsyncSession, today: date) -> int:
    """Las series cuya ventana ya termino pasan a finished."""
    series = (
        await session.scalars(
            select(TripSeries).where(
                TripSeries.status == SeriesStatus.ACTIVE, TripSeries.window_end < today
            )
        )
    ).all()
    for item in series:
        item.status = SeriesStatus.FINISHED
    await session.commit()
    return len(series)
