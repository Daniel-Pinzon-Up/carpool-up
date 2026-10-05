"""Busqueda geografica de viajes (seccion 7.3).

Un viaje coincide si su ruta pasa a menos de search_radius_meters de la recogida y de la
bajada, la recogida queda antes que la bajada a lo largo de la ruta (ST_LineLocatePoint),
sale dentro de search_time_window_minutes de la hora pedida, esta programado con cupo y sus
reglas son compatibles con las preferencias. Orden: recogida mas cercana, menor diferencia
horaria, mejor calificacion del conductor (paso 11) y salida mas temprana.
"""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Select, and_, cast, exists, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Exists

from app.core.clock import LOCAL_TZ, utcnow
from app.core.enums import RuleKind, Sex, StopKind, TripStatus
from app.core.errors import AppError
from app.core.geo import SRID
from app.modules.bookings.queries import booked_seats_subquery
from app.modules.routing.schemas import RoutePoint
from app.modules.routing.service import resolve_points
from app.modules.search.schemas import (
    DriverCard,
    MatchPoint,
    SearchQuery,
    SearchResult,
    VehicleCard,
)
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip, TripRule, TripStop
from app.modules.trips.schemas import ALLOWED, NOT_ALLOWED, RuleOut
from app.modules.users.models import User

MAX_RESULTS = 50
EARTH_RADIUS_M = 6_371_000


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float


def walk_m(a: Point, b: Point) -> float:
    """Distancia en linea recta (haversine); suficiente a escala de ciudad."""
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _rule(kind: RuleKind, value: str | None = None) -> Exists:
    condition = and_(TripRule.trip_id == Trip.id, TripRule.kind == kind)
    if value is not None:
        condition = and_(condition, TripRule.value == value)
    return exists().where(condition)


def rules_filter(query: Select[Any], prefs: SearchQuery, viewer: User) -> Select[Any]:
    """Preferencias del pasajero contra las reglas del viaje (sin regla = compatible)."""
    if prefs.pets:
        query = query.where(~_rule(RuleKind.PETS, NOT_ALLOWED))
    if prefs.luggage:
        query = query.where(~_rule(RuleKind.LUGGAGE, NOT_ALLOWED))
    if prefs.no_smoking:
        query = query.where(~_rule(RuleKind.SMOKING, ALLOWED))
    if prefs.music:
        query = query.where(~_rule(RuleKind.MUSIC, NOT_ALLOWED))
    if viewer.sex != Sex.FEMALE:
        # Solo pasajeras reservan viajes de solo mujeres: a los demas no se les ofrecen.
        query = query.where(~_rule(RuleKind.WOMEN_ONLY))
    elif prefs.women_only:
        query = query.where(_rule(RuleKind.WOMEN_ONLY))
    return query


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)

    async def resolve(self, viewer: User, prefs: SearchQuery) -> tuple[Point, Point]:
        """Lugares del catalogo o pines propios, dentro del area de servicio."""
        points = [
            RoutePoint(
                place_id=getattr(prefs, f"{p}_place_id"),
                lat=getattr(prefs, f"{p}_lat"),
                lon=getattr(prefs, f"{p}_lon"),
            )
            for p in ("origin", "destination")
        ]
        stops = await resolve_points(self.session, points, viewer)
        return Point(stops[0].lat, stops[0].lon), Point(stops[1].lat, stops[1].lon)

    async def search(self, viewer: User, prefs: SearchQuery) -> list[SearchResult]:
        pickup, dropoff = await self.resolve(viewer, prefs)
        radius = int(await self.settings.get("search_radius_meters"))
        window = int(await self.settings.get("search_time_window_minutes"))
        target = datetime.combine(prefs.date, prefs.time, tzinfo=LOCAL_TZ)
        start = max(target - timedelta(minutes=window), utcnow())
        end = target + timedelta(minutes=window)
        if end <= start:
            raise AppError("SEARCH_IN_PAST", "The requested time has already passed", 422)

        pickup_geom = func.ST_SetSRID(func.ST_MakePoint(pickup.lon, pickup.lat), SRID)
        dropoff_geom = func.ST_SetSRID(func.ST_MakePoint(dropoff.lon, dropoff.lat), SRID)
        route_geo = cast(Trip.route, Geography)
        pickup_distance = func.ST_Distance(route_geo, cast(pickup_geom, Geography))
        pickup_fraction = func.ST_LineLocatePoint(Trip.route, pickup_geom)
        dropoff_fraction = func.ST_LineLocatePoint(Trip.route, dropoff_geom)
        time_gap = func.abs(func.extract("epoch", Trip.departs_at - literal(target)))
        # Cupo: puestos menos los aceptados y con cancelacion pendiente.
        free_seats = Trip.seats_total - booked_seats_subquery()

        query = (
            select(
                Trip,
                free_seats.label("free_seats"),
                pickup_fraction.label("pickup_fraction"),
                dropoff_fraction.label("dropoff_fraction"),
                func.ST_Y(func.ST_LineInterpolatePoint(Trip.route, pickup_fraction)).label("p_lat"),
                func.ST_X(func.ST_LineInterpolatePoint(Trip.route, pickup_fraction)).label("p_lon"),
                func.ST_Y(func.ST_LineInterpolatePoint(Trip.route, dropoff_fraction)).label(
                    "d_lat"
                ),
                func.ST_X(func.ST_LineInterpolatePoint(Trip.route, dropoff_fraction)).label(
                    "d_lon"
                ),
            )
            .where(
                Trip.status == TripStatus.SCHEDULED,
                Trip.deleted_at.is_(None),
                Trip.driver_id != viewer.id,
                Trip.departs_at >= start,
                Trip.departs_at <= end,
                free_seats >= prefs.seats,
                func.ST_DWithin(route_geo, cast(pickup_geom, Geography), radius),
                func.ST_DWithin(route_geo, cast(dropoff_geom, Geography), radius),
                pickup_fraction < dropoff_fraction,
            )
            .order_by(pickup_distance, time_gap, Trip.departs_at, Trip.id)
            .limit(MAX_RESULTS)
        )
        query = rules_filter(query, prefs, viewer)
        rows = (await self.session.execute(query)).all()

        counts = await self.driver_trip_counts({row.Trip.driver_id for row in rows})
        results = []
        for row in rows:
            trip: Trip = row.Trip
            board = self.match(
                trip, pickup, Point(row.p_lat, row.p_lon), row.pickup_fraction, radius, pickup=True
            )
            alight = self.match(
                trip,
                dropoff,
                Point(row.d_lat, row.d_lon),
                row.dropoff_fraction,
                radius,
                pickup=False,
            )
            if board.eta >= alight.eta and board.kind == alight.kind == "stop":
                continue  # Misma parada para subir y bajar: no hay trayecto.
            results.append(
                self.result(
                    trip, board, alight, target, counts.get(trip.driver_id, 0), row.free_seats
                )
            )
        return results

    @staticmethod
    def match(
        trip: Trip, wanted: Point, on_route: Point, fraction: float, radius: int, *, pickup: bool
    ) -> MatchPoint:
        """Parada del viaje mas cercana si queda dentro del radio; si no, el punto de la ruta.

        La recogida no puede ser el destino y la bajada no puede ser el origen.
        """
        excluded = StopKind.DESTINATION if pickup else StopKind.ORIGIN
        candidates = [
            (walk_m(wanted, Point(stop.place.lat, stop.place.lon)), stop)
            for stop in trip.stops
            if stop.kind != excluded
        ]
        best = min(candidates, key=lambda item: item[0], default=None)
        if best is not None and best[0] <= radius:
            distance, stop = best
            return MatchPoint(
                kind="stop",
                name=stop.place.name,
                lat=stop.place.lat,
                lon=stop.place.lon,
                eta=stop.eta,
                walk_m=round(distance),
            )
        eta = trip.departs_at + timedelta(seconds=round(trip.est_duration_s * fraction))
        return MatchPoint(
            kind="route",
            name=None,
            lat=on_route.lat,
            lon=on_route.lon,
            eta=eta,
            walk_m=round(walk_m(wanted, on_route)),
        )

    async def driver_trip_counts(self, driver_ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not driver_ids:
            return {}
        rows = await self.session.execute(
            select(Trip.driver_id, func.count())
            .where(Trip.driver_id.in_(driver_ids), Trip.status == TripStatus.COMPLETED)
            .group_by(Trip.driver_id)
        )
        return {driver_id: count for driver_id, count in rows}

    @staticmethod
    def result(
        trip: Trip,
        board: MatchPoint,
        alight: MatchPoint,
        target: datetime,
        trips_done: int,
        free_seats: int,
    ) -> SearchResult:
        stops: list[TripStop] = trip.stops
        return SearchResult(
            trip_id=trip.id,
            series_id=trip.series_id,
            status=trip.status,
            departs_at=trip.departs_at,
            arrives_at=trip.departs_at + timedelta(seconds=trip.est_duration_s),
            origin=stops[0].place.name,
            destination=stops[-1].place.name,
            price_per_seat=trip.price_per_seat,
            seats_available=free_seats,
            pickup=board,
            dropoff=alight,
            minutes_from_requested=round((trip.departs_at - target).total_seconds() / 60),
            driver=DriverCard(
                id=trip.driver.id,
                full_name=trip.driver.full_name,
                rating=None,
                trips_as_driver=trips_done,
            ),
            vehicle=VehicleCard(
                vehicle_id=trip.vehicle.id,
                type=trip.vehicle.type,
                brand=trip.vehicle.brand,
                model=trip.vehicle.model,
                color=trip.vehicle.color,
                has_photo=trip.vehicle.photo_path is not None,
            ),
            rules=[RuleOut(kind=rule.kind, value=rule.value) for rule in trip.rules],
        )
