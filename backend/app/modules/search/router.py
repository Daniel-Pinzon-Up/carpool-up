from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.core.auth import ActiveUser
from app.core.deps import DbSession
from app.core.rate_limit import limiter
from app.modules.search.schemas import SearchQuery, SearchResult
from app.modules.search.service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "/trips",
    responses={
        404: {"description": "PLACE_NOT_FOUND"},
        422: {"description": "PLACE_OUT_OF_AREA, SEARCH_IN_PAST, VALIDATION_ERROR"},
    },
)
@limiter.limit("60/minute")
async def search_trips(
    request: Request,
    query: Annotated[SearchQuery, Query()],
    user: ActiveUser,
    session: DbSession,
) -> list[SearchResult]:
    """Viajes programados que pasan cerca de la recogida y de la bajada, en ese orden.

    Nunca devuelve la placa ni datos de contacto del conductor. Los viajes de solo mujeres
    solo se ofrecen a pasajeras.
    """
    return await SearchService(session).search(user, query)
