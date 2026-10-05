"""Cliente de OSRM autoalojado con cache en Redis (seccion 10)."""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol

import httpx
import structlog
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import AppError

logger = structlog.get_logger("routing")

CACHE_SECONDS = 24 * 3600
TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class Leg:
    distance_m: float
    duration_s: float


@dataclass(frozen=True)
class RouteResult:
    """Geometria en orden GeoJSON: [[lon, lat], ...]."""

    coordinates: list[list[float]]
    distance_m: float
    duration_s: float
    legs: list[Leg]


class RouteProvider(Protocol):
    async def route(self, points: list[tuple[float, float]]) -> RouteResult:
        """points: [(lat, lon), ...] en orden de paso (origen, paradas, destino)."""
        ...


class RoutingUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "ROUTING_UNAVAILABLE", "The routing service is not available, try again later", 503
        )


def cache_key(points: list[tuple[float, float]]) -> str:
    # 5 decimales son unos 1,1 m: suficiente para reutilizar rutas sin perder precision.
    raw = ";".join(f"{lat:.5f},{lon:.5f}" for lat, lon in points)
    return "route:" + hashlib.sha256(raw.encode()).hexdigest()


class OsrmClient:
    def __init__(self, redis: Redis, base_url: str | None = None) -> None:
        self.redis = redis
        self.base_url = (base_url or get_settings().osrm_url).rstrip("/")

    async def route(self, points: list[tuple[float, float]]) -> RouteResult:
        key = cache_key(points)
        try:
            cached = await self.redis.get(key)
        except Exception:  # sin cache se sigue con OSRM
            cached = None
        if cached:
            data = json.loads(cached)
            return RouteResult(
                coordinates=data["coordinates"],
                distance_m=data["distance_m"],
                duration_s=data["duration_s"],
                legs=[Leg(**leg) for leg in data["legs"]],
            )

        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
        url = f"{self.base_url}/route/v1/driving/{coords}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("osrm_unreachable", error=type(exc).__name__)
            raise RoutingUnavailableError() from exc

        body = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        code = body.get("code")
        if code in {"NoRoute", "NoSegment"}:
            raise AppError(
                "ROUTE_NOT_FOUND", "There is no drivable route between these points", 422
            )
        if response.status_code != 200 or code != "Ok" or not body.get("routes"):
            logger.warning("osrm_error", status=response.status_code, code=code)
            raise RoutingUnavailableError()

        best = body["routes"][0]
        result = RouteResult(
            coordinates=best["geometry"]["coordinates"],
            distance_m=float(best["distance"]),
            duration_s=float(best["duration"]),
            legs=[Leg(float(leg["distance"]), float(leg["duration"])) for leg in best["legs"]],
        )
        try:
            await self.redis.set(key, json.dumps(asdict(result)), ex=CACHE_SECONDS)
        except Exception:
            logger.warning("route_cache_write_failed")
        return result
