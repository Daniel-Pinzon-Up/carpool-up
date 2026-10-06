import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.auth import ActiveUser
from app.core.deps import DbSession
from app.core.errors import NotFoundError
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.modules.ratings.schemas import PendingRating, RatingIn, RatingOut, RatingSummary
from app.modules.ratings.service import RatingService
from app.modules.stats.summary import stats_for
from app.modules.users.models import User

router = APIRouter(tags=["ratings"])


@router.get("/ratings/pending")
async def pending_ratings(user: ActiveUser, session: DbSession) -> list[PendingRating]:
    """Personas que el usuario aun puede calificar, con el cierre del plazo."""
    return await RatingService(session).pending(user)


@router.post(
    "/trips/{trip_id}/ratings",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "RATING_NOT_OPEN, RATING_WINDOW_CLOSED, RATING_EXISTS"},
        422: {"description": "RATING_TARGET_INVALID, RATING_CRITERIA_INVALID"},
    },
)
async def rate(
    trip_id: uuid.UUID, body: RatingIn, user: ActiveUser, session: DbSession
) -> RatingOut:
    return await RatingService(session).rate(user, trip_id, body)


@router.get("/users/{user_id}/ratings")
async def ratings_received(
    user_id: uuid.UUID,
    user: ActiveUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[RatingOut]:
    """Calificaciones recibidas. Los comentarios ocultos salen sin texto."""
    return await RatingService(session).received(user_id, limit, cursor)


@router.get("/users/{user_id}/rating-summary")
async def rating_summary(user_id: uuid.UUID, user: ActiveUser, session: DbSession) -> RatingSummary:
    """Reputacion publica: promedio general, por criterio y viajes hechos."""
    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise NotFoundError("user")
    stats = (await stats_for(session, [user_id])).get(user_id)
    return RatingSummary(
        user_id=target.id,
        full_name=target.full_name,
        average=stats.rating_avg if stats else None,
        count=stats.rating_count if stats else 0,
        criteria=stats.criteria if stats else {},
        trips_as_driver=stats.trips_as_driver if stats else 0,
        trips_as_passenger=stats.trips_as_passenger if stats else 0,
    )
