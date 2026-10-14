"""Ruta, ETA ajustada por trafico y precio sugerido (secciones 7.2, 7.4 y 10)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PlaceKind, VehicleType
from app.core.errors import AppError
from app.modules.places.models import Place
from app.modules.routing.osrm import RouteProvider, RouteResult
from app.modules.routing.schemas import ResolvedPoint, RoutePoint, RoutePreview
from app.modules.settings.service import SettingsService
from app.modules.users.models import User

COST_KEYS = {VehicleType.CAR: "cost_per_km_car", VehicleType.MOTORCYCLE: "cost_per_km_motorcycle"}


def round_to_hundred(value: float) -> int:
    """Redondeo a la centena mas cercana (las mitades suben)."""
    return int((value + 50) // 100 * 100)


def estimate_price(distance_m: float, cost_per_km: int, seats: int, max_price: int | None) -> int:
    """distancia_km * costo_km / (puestos + 1) (incluye al conductor), a la centena, con tope."""
    estimate = round_to_hundred(distance_m / 1000 * cost_per_km / (seats + 1))
    return min(estimate, max_price) if max_price is not None else estimate


@dataclass(frozen=True)
class Stop:
    place_id: uuid.UUID | None
    name: str | None
    lat: float
    lon: float


async def resolve_points(session: AsyncSession, points: list[RoutePoint], user: User) -> list[Stop]:
    """Convierte place_id o coordenadas en paradas dentro del area de servicio."""
    settings = SettingsService(session)
    max_stops = int(await settings.get("max_trip_stops"))
    if len(points) > max_stops + 2:
        raise AppError(
            "TOO_MANY_STOPS", "Too many intermediate stops", 422, {"max_stops": max_stops}
        )
    area = await settings.service_area()
    stops: list[Stop] = []
    for index, point in enumerate(points):
        if point.place_id is not None:
            place = await session.get(Place, point.place_id)
            usable = (
                place is not None
                and place.is_active
                and (place.kind != PlaceKind.CUSTOM or place.created_by == user.id)
            )
            if not usable or place is None:
                raise AppError("PLACE_NOT_FOUND", "Place not found", 404, {"index": index})
            stop = Stop(place.id, place.name, place.lat, place.lon)
        else:
            assert point.lat is not None and point.lon is not None  # noqa: S101 - validado
            stop = Stop(None, None, point.lat, point.lon)
        if not area.contains(stop.lat, stop.lon):
            raise AppError(
                "PLACE_OUT_OF_AREA", "Point is outside the service area", 422, {"index": index}
            )
        stops.append(stop)
    return stops


class RoutingService:
    def __init__(self, session: AsyncSession, provider: RouteProvider) -> None:
        self.session = session
        self.provider = provider
        self.settings = SettingsService(session)

    async def resolve(self, points: list[RoutePoint], user: User) -> list[Stop]:
        return await resolve_points(self.session, points, user)

    async def suggested_price(
        self, distance_m: float, vehicle_type: VehicleType | None, seats: int | None
    ) -> tuple[bool, int | None, int | None]:
        """(precios configurados, sugerido, tope)."""
        max_price = await self.settings.get("max_price_per_seat")
        if vehicle_type is None:
            costs = [await self.settings.get(key) for key in COST_KEYS.values()]
            return all(c is not None for c in costs), None, max_price
        cost = await self.settings.get(COST_KEYS[vehicle_type])
        if cost is None or seats is None:
            return cost is not None, None, max_price
        return True, estimate_price(distance_m, int(cost), seats, max_price), max_price

    async def preview(
        self,
        points: list[RoutePoint],
        user: User,
        departs_at: datetime | None,
        vehicle_type: VehicleType | None,
        seats: int | None,
    ) -> RoutePreview:
        stops = await self.resolve(points, user)
        route: RouteResult = await self.provider.route([(s.lat, s.lon) for s in stops])
        configured, price, max_price = await self.suggested_price(
            route.distance_m, vehicle_type, seats
        )

        offsets = [0.0]
        for leg in route.legs:
            offsets.append(offsets[-1] + leg.duration_s)
        resolved = [
            ResolvedPoint(
                place_id=stop.place_id,
                name=stop.name,
                lat=stop.lat,
                lon=stop.lon,
                eta_offset_s=round(offset),
                eta=departs_at + timedelta(seconds=round(offset)) if departs_at else None,
            )
            for stop, offset in zip(stops, offsets, strict=True)
        ]
        return RoutePreview(
            geometry=route.coordinates,
            distance_m=round(route.distance_m),
            duration_s=round(route.duration_s),
            points=resolved,
            pricing_configured=configured,
            suggested_price=price,
            max_price_per_seat=max_price,
        )
