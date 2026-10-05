"""Ultima ubicacion del conductor durante el viaje (seccion 9).

Vive solo en Redis con vencimiento (live_location_ttl_seconds): no se guarda historial de
recorridos. La leen los participantes y el enlace compartido; el canal trip:{id}:loc la
difunde en vivo.
"""

import json
import uuid
from typing import Any, Protocol

from app.core.redis import redis_client


def location_key(trip_id: uuid.UUID | str) -> str:
    return f"trip:{trip_id}:loc"


def location_channel(trip_id: uuid.UUID | str) -> str:
    return f"trip:{trip_id}:loc"


class LocationBackend(Protocol):
    async def set(self, key: str, value: str, ttl: int) -> None: ...
    async def get(self, key: str) -> str | None: ...
    async def delete(self, key: str) -> None: ...


class RedisLocations:
    async def set(self, key: str, value: str, ttl: int) -> None:
        await redis_client.set(key, value, ex=ttl)

    async def get(self, key: str) -> str | None:
        value = await redis_client.get(key)
        return str(value) if value is not None else None

    async def delete(self, key: str) -> None:
        await redis_client.delete(key)


_backend: LocationBackend = RedisLocations()


def set_backend(backend: LocationBackend) -> LocationBackend:
    """Las pruebas guardan las ubicaciones en memoria."""
    global _backend
    previous, _backend = _backend, backend
    return previous


async def save_location(trip_id: uuid.UUID, point: dict[str, Any], ttl: int) -> None:
    await _backend.set(location_key(trip_id), json.dumps(point, default=str), ttl)


async def last_location(trip_id: uuid.UUID) -> dict[str, Any] | None:
    raw = await _backend.get(location_key(trip_id))
    return json.loads(raw) if raw else None


async def forget_location(trip_id: uuid.UUID) -> None:
    await _backend.delete(location_key(trip_id))
