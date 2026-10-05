import uuid

from fastapi import APIRouter, Request, status

from app.core.auth import ActiveUser
from app.core.deps import DbSession
from app.core.rate_limit import limiter
from app.modules.routing.router import Provider
from app.modules.series.service import SeriesService
from app.modules.trips.router import PUBLISH_ERRORS
from app.modules.trips.schemas import (
    CancelRequest,
    SeriesCreate,
    SeriesDuplicate,
    SeriesOut,
    SeriesSummary,
    SeriesUpdate,
)

router = APIRouter(prefix="/series", tags=["series"])

SERIES_ERRORS: dict[int | str, dict[str, str]] = {
    **PUBLISH_ERRORS,
    422: {
        "description": PUBLISH_ERRORS[422]["description"]
        + ", SERIES_OUTSIDE_SEMESTER, SERIES_WINDOW_INVALID, SERIES_START_IN_PAST, SERIES_EMPTY"
    },
}


@router.post("", status_code=status.HTTP_201_CREATED, responses=SERIES_ERRORS)
@limiter.limit("10/minute")
async def publish_series(
    request: Request, body: SeriesCreate, user: ActiveUser, session: DbSession, provider: Provider
) -> SeriesOut:
    """Publica una serie y genera todas sus ocurrencias de una vez.

    Las fechas en pico y placa quedan como cancelled_pico_placa (no reservables).
    """
    service = SeriesService(session, provider)
    series = await service.create(user, body)
    return await service.detail(series, user)


@router.get("/mine")
async def my_series(
    user: ActiveUser, session: DbSession, provider: Provider
) -> list[SeriesSummary]:
    return await SeriesService(session, provider).list_mine(user)


@router.get("/{series_id}")
async def get_series(
    series_id: uuid.UUID, user: ActiveUser, session: DbSession, provider: Provider
) -> SeriesOut:
    """Plantilla y ocurrencias. Los demas usuarios solo ven las ocurrencias programadas."""
    service = SeriesService(session, provider)
    return await service.detail(await service.get_visible(user, series_id), user)


@router.patch("/{series_id}", responses=SERIES_ERRORS)
async def update_series(
    series_id: uuid.UUID,
    body: SeriesUpdate,
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
) -> SeriesOut:
    """Cambia la plantilla y las ocurrencias futuras."""
    service = SeriesService(session, provider)
    series = await service.update(user, series_id, body)
    return await service.detail(series, user)


@router.post("/{series_id}/cancel", responses={409: {"description": "SERIES_NOT_ACTIVE"}})
async def cancel_series(
    series_id: uuid.UUID,
    body: CancelRequest,
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
) -> SeriesOut:
    service = SeriesService(session, provider)
    series = await service.cancel(user, series_id, body.reason)
    return await service.detail(series, user)


@router.post("/{series_id}/duplicate", status_code=status.HTTP_201_CREATED, responses=SERIES_ERRORS)
@limiter.limit("10/minute")
async def duplicate_series(
    request: Request,
    series_id: uuid.UUID,
    body: SeriesDuplicate,
    user: ActiveUser,
    session: DbSession,
    provider: Provider,
) -> SeriesOut:
    service = SeriesService(session, provider)
    series = await service.duplicate(user, series_id, body.start_date, body.window)
    return await service.detail(series, user)
