import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.auth import CurrentUser
from app.core.deps import DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.modules.notifications.schemas import MarkedRead, NotificationOut, UnreadCount
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
    unread_only: bool = False,
) -> Page[NotificationOut]:
    """Bandeja propia, mas reciente primero."""
    return await NotificationService(session).list_for(user.id, limit, cursor, unread_only)


@router.get("/unread-count")
async def unread_count(user: CurrentUser, session: DbSession) -> UnreadCount:
    return UnreadCount(unread=await NotificationService(session).unread_count(user.id))


@router.post("/read-all")
async def read_all(user: CurrentUser, session: DbSession) -> MarkedRead:
    return MarkedRead(marked=await NotificationService(session).mark_all_read(user.id))


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_one(notification_id: uuid.UUID, user: CurrentUser, session: DbSession) -> None:
    await NotificationService(session).mark_read(user.id, notification_id)
