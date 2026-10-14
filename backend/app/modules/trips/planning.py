"""Reglas compartidas al publicar, editar y duplicar viajes (seccion 7.2).

Un solo lugar decide vehiculo, puestos, precio, reglas, ruta, ETA y solapes.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import LOCAL_TZ, utcnow
from app.core.enums import RuleKind, Sex, StopKind, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.geo import SRID
from app.modules.pico_placa.service import PicoPlacaService
from app.modules.routing.osrm import RouteProvider, RouteResult
from app.modules.routing.schemas import RoutePoint
from app.modules.routing.service import RoutingService, Stop
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip, TripStop
from app.modules.trips.schemas import ALLOWED, RuleIn
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

# Estados que ocupan al conductor y su vehiculo.
BUSY_STATUSES = (TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)


@dataclass(frozen=True)
class PlannedRoute:
    stops: list[Stop]
    route: RouteResult

    @property
    def place_ids(self) -> list[uuid.UUID]:
        return [stop.place_id for stop in self.stops if stop.place_id is not None]


def local_date(moment: datetime) -> date:
    return moment.astimezone(LOCAL_TZ).date()


def stop_kind(position: int, count: int) -> StopKind:
    if position == 0:
        return StopKind.ORIGIN
    return StopKind.DESTINATION if position == count - 1 else StopKind.STOP


def linestring(coordinates: list[list[float]]) -> WKTElement:
    # OSRM devuelve un solo punto si origen y destino coinciden; PostGIS exige dos.
    coords = coordinates if len(coordinates) > 1 else coordinates * 2
    return WKTElement(
        "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in coords) + ")", srid=SRID
    )


def normalize_rules(rules: list[RuleIn]) -> list[dict[str, str]]:
    """ "Solo mujeres" se guarda solo si esta activo; el resto tal cual, en orden estable."""
    kept = [
        {"kind": rule.kind.value, "value": rule.value}
        for rule in rules
        if not (rule.kind == RuleKind.WOMEN_ONLY and rule.value != ALLOWED)
    ]
    return sorted(kept, key=lambda rule: rule["kind"])


class TripPlanner:
    def __init__(self, session: AsyncSession, provider: RouteProvider) -> None:
        self.session = session
        self.provider = provider
        self.settings = SettingsService(session)
        self.routing = RoutingService(session, provider)

    # --- Validaciones -------------------------------------------------------------------

    async def vehicle(self, driver: User, vehicle_id: uuid.UUID) -> Vehicle:
        vehicle = await self.session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.deleted_at is not None or vehicle.owner_id != driver.id:
            raise NotFoundError("vehicle")
        if not vehicle.is_active:
            raise AppError("VEHICLE_INACTIVE", "The vehicle is not active", 422)
        return vehicle

    @staticmethod
    def check_seats(vehicle: Vehicle, seats: int) -> None:
        maximum = vehicle.capacity - 1
        if seats > maximum:
            raise AppError(
                "SEATS_INVALID", "More seats than the vehicle allows", 422, {"max_seats": maximum}
            )

    async def check_price(self, price: int) -> None:
        maximum = await self.settings.get("max_price_per_seat")
        if maximum is not None and price > int(maximum):
            raise AppError(
                "PRICE_ABOVE_MAX", "Price is above the allowed maximum", 422, {"max": maximum}
            )

    @staticmethod
    def check_rules(driver: User, rules: list[RuleIn]) -> list[dict[str, str]]:
        normalized = normalize_rules(rules)
        women_only = any(rule["kind"] == RuleKind.WOMEN_ONLY for rule in normalized)
        if women_only and driver.sex != Sex.FEMALE:
            raise AppError(
                "WOMEN_ONLY_FEMALE_DRIVERS", "Only female drivers can publish women-only trips", 403
            )
        return normalized

    async def check_departure(self, departs_at: datetime) -> None:
        now = utcnow()
        lead = int(await self.settings.get("trip_publish_min_lead_minutes"))
        if departs_at < now + timedelta(minutes=lead):
            raise AppError(
                "DEPARTURE_TOO_SOON",
                "Departure must be further in the future",
                422,
                {"min_lead_minutes": lead},
            )
        days = int(await self.settings.get("trip_max_days_ahead"))
        if departs_at > now + timedelta(days=days):
            raise AppError(
                "DEPARTURE_TOO_FAR", "Departure is too far ahead", 422, {"max_days": days}
            )

    async def restricted_dates(self, vehicle: Vehicle, start: date, end: date) -> set[date]:
        return await PicoPlacaService(self.session).restricted_dates(
            vehicle.type, vehicle.plate, start, end
        )

    async def check_pico_placa(self, vehicle: Vehicle, departs_at: datetime) -> None:
        day = local_date(departs_at)
        if await self.restricted_dates(vehicle, day, day):
            raise AppError(
                "PICO_PLACA_RESTRICTED",
                "The vehicle has pico y placa that day",
                422,
                {"date": day.isoformat()},
            )

    async def check_overlaps(
        self,
        driver_id: uuid.UUID,
        windows: list[tuple[datetime, int]],
        exclude: set[uuid.UUID] | None = None,
    ) -> None:
        """Un conductor no puede tener dos viajes activos que se crucen en el tiempo."""
        if not windows:
            return
        start = min(at for at, _ in windows) - timedelta(days=1)
        end = max(at + timedelta(seconds=d) for at, d in windows)
        rows = await self.session.execute(
            select(Trip.id, Trip.departs_at, Trip.est_duration_s).where(
                Trip.driver_id == driver_id,
                Trip.deleted_at.is_(None),
                Trip.status.in_(BUSY_STATUSES),
                Trip.departs_at >= start,
                Trip.departs_at <= end,
            )
        )
        busy = [
            (at, at + timedelta(seconds=d))
            for trip_id, at, d in rows
            if trip_id not in (exclude or set())
        ]
        clashes = sorted(
            {
                local_date(at).isoformat()
                for at, duration in windows
                for other_start, other_end in busy
                if at < other_end and other_start < at + timedelta(seconds=duration)
            }
        )
        if clashes:
            raise AppError(
                "TRIP_OVERLAP", "You already have a trip at that time", 409, {"dates": clashes}
            )

    # --- Ruta y armado ------------------------------------------------------------------

    async def plan_route(self, driver: User, place_ids: list[uuid.UUID]) -> PlannedRoute:
        """Lugares del catalogo o pines propios dentro del area, y la ruta de OSRM."""
        stops = await self.routing.resolve([RoutePoint(place_id=pid) for pid in place_ids], driver)
        route = await self.provider.route([(stop.lat, stop.lon) for stop in stops])
        return PlannedRoute(stops, route)

    @staticmethod
    def stop_rows(planned: PlannedRoute, departs_at: datetime) -> list[TripStop]:
        """Hora estimada de cada parada: la salida mas la duracion acumulada de OSRM."""
        offsets = [0.0]
        for leg in planned.route.legs:
            offsets.append(offsets[-1] + leg.duration_s)
        count = len(planned.stops)
        return [
            TripStop(
                place_id=stop.place_id,
                position=position,
                kind=stop_kind(position, count),
                eta=departs_at + timedelta(seconds=round(offset)),
            )
            for position, (stop, offset) in enumerate(zip(planned.stops, offsets, strict=True))
        ]

    async def apply(
        self,
        trip: Trip,
        planned: PlannedRoute,
        departs_at: datetime,
        rules: list[dict[str, Any]],
    ) -> None:
        """Copia ruta, ETA y reglas al viaje (nuevo o editado)."""
        if trip.stops:
            # Las posiciones son unicas: se borran las paradas viejas antes de insertar.
            trip.stops.clear()
            await self.session.flush()
        trip.departs_at = departs_at
        trip.route = linestring(planned.route.coordinates)
        trip.distance_m = round(planned.route.distance_m)
        trip.est_duration_s = round(planned.route.duration_s)
        trip.stops = self.stop_rows(planned, departs_at)
        trip.rules = rules
