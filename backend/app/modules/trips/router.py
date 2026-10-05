import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, status

from app.core.auth import ActiveUser
from app.core.deps import DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.core.rate_limit import limiter
from app.modules.routing.router import Provider
from app.modules.trips.schemas import (
    CancelRequest,
    TripCreate,
    TripDuplicate,
    TripOut,
    TripSummary,
    TripUpdate,
)
from app.modules.trips.service import TripService

router = APIRouter(prefix="/trips", tags=["trips"])

PUBLISH_ERRORS: dict[int | str, dict[str, str]] = {
    403: {"description": "PUBLISH_NOT_ALLOWED, WOMEN_ONLY_FEMALE_DRIVERS"},
    409: {"description": "TRIP_OVERLAP, TRIP_NOT_EDITABLE"},
    422: {
        "description": "PICO_PLACA_RESTRICTED, DEPARTURE_TOO_SOON, DEPARTURE_TOO_FAR, "
        "SEATS_INVALID, PRICE_ABOVE_MAX, VEHICLE_INACTIVE, ROUTE_NOT_FOUND, "
        "PLACE_OUT_OF_AREA, TOO_MANY_STOPS"
    },
    503: {"description": "ROUTING_UNAVAILABLE"},
}


async def _out(service: TripService, trip_id: uuid.UUID, user: ActiveUser) -> TripOut:
    trip = await service.get_visible(user, trip_id)
    return await service.view(trip, user)


@router.post("", status_code=status.HTTP_201_CREATED, responses=PUBLISH_ERRORS)
@limiter.limit("20/minute")
async def publish_trip(
    request: Request, body: TripCreate, user: ActiveUser, session: DbSession, provider: Provider
) -> TripOut:
    """Publica un viaje puntual. La ruta se calcula con OSRM; si no responde, no se publica."""
    service = TripService(session, provider)
    trip = await service.create(user, body)
    return await service.view(trip, user)


@router.get("/mine")
async def my_trips(
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
    scope: Literal["upcoming", "history"] = "upcoming",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[TripSummary]:
    """Viajes del conductor: puntuales y ocurrencias de sus series."""
    return await TripService(session, provider).list_mine(user, scope, limit, cursor)


@router.get("/{trip_id}")
async def get_trip(
    trip_id: uuid.UUID, user: ActiveUser, session: DbSession, provider: Provider
) -> TripOut:
    """Detalle con ruta, paradas, reglas y conductor. La placa solo la ve el conductor."""
    return await _out(TripService(session, provider), trip_id, user)


@router.patch("/{trip_id}", responses=PUBLISH_ERRORS)
async def update_trip(
    trip_id: uuid.UUID, body: TripUpdate, user: ActiveUser, session: DbSession, provider: Provider
) -> TripOut:
    """Edita un viaje o una ocurrencia hasta trip_edit_cutoff_minutes antes de la salida."""
    service = TripService(session, provider)
    trip = await service.update(user, trip_id, body)
    return await service.view(trip, user)


@router.post("/{trip_id}/cancel", responses={409: {"description": "TRIP_NOT_EDITABLE"}})
async def cancel_trip(
    trip_id: uuid.UUID,
    body: CancelRequest,
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
) -> TripOut:
    service = TripService(session, provider)
    trip = await service.cancel(user, trip_id, body.reason)
    return await service.view(trip, user)


@router.post("/{trip_id}/duplicate", status_code=status.HTTP_201_CREATED, responses=PUBLISH_ERRORS)
@limiter.limit("20/minute")
async def duplicate_trip(
    request: Request,
    trip_id: uuid.UUID,
    body: TripDuplicate,
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
) -> TripOut:
    """Publica un viaje nuevo con la ruta, reglas, vehiculo, puestos y precio de otro."""
    service = TripService(session, provider)
    trip = await service.duplicate(user, trip_id, body.departs_at)
    return await service.view(trip, user)
