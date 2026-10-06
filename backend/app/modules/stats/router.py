from typing import Annotated

from fastapi import APIRouter, Query

from app.core.auth import Driver, Passenger
from app.core.deps import DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.modules.stats.schemas import (
    DriverHistoryEntry,
    DriverStats,
    PassengerHistoryEntry,
    PassengerStats,
)
from app.modules.stats.service import StatsService

router = APIRouter(tags=["stats"])

Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


@router.get("/stats/passenger")
async def passenger_stats(user: Passenger, session: DbSession) -> PassengerStats:
    """Viajes, aporte total, lugares de salida mas usados y meses."""
    return await StatsService(session).passenger(user)


@router.get("/stats/driver")
async def driver_stats(user: Driver, session: DbSession) -> DriverStats:
    """Viajes, ocupacion, aportes, calificacion por criterio y cancelaciones."""
    return await StatsService(session).driver(user)


@router.get("/history/passenger")
async def passenger_history(
    user: Passenger, session: DbSession, limit: Limit = DEFAULT_LIMIT, cursor: str | None = None
) -> Page[PassengerHistoryEntry]:
    """Viajes pasados con su estado, ticket y si falta calificar."""
    return await StatsService(session).passenger_history(user, limit, cursor)


@router.get("/history/driver")
async def driver_history(
    user: Driver, session: DbSession, limit: Limit = DEFAULT_LIMIT, cursor: str | None = None
) -> Page[DriverHistoryEntry]:
    """Viajes pasados con pasajeros, aportes y calificaciones pendientes."""
    return await StatsService(session).driver_history(user, limit, cursor)
