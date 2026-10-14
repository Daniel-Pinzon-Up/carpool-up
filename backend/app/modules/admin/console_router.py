"""Panel de administracion: usuarios, viajes, moderacion e indicadores (seccion 8).

Administradores y superadmin. Cada accion queda en la auditoria con quien la hizo.
"""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.core.auth import AdminActor, AdminOrSuper
from app.core.deps import DbSession
from app.core.enums import TripStatus, UserRole, UserStatus
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.modules.admin.dashboard import overview
from app.modules.admin.schemas import (
    AdminMessage,
    AdminOverview,
    AdminRating,
    AdminTripDetail,
    AdminTripRow,
    AdminUserDetail,
    AdminUserRow,
    HiddenRequest,
    OptionalReason,
    ReasonRequest,
    SuspendRequest,
)
from app.modules.admin.trips import AdminTripService
from app.modules.admin.users import AdminUserService

router = APIRouter(prefix="/admin", tags=["admin: console"])

Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
# Respuestas documentadas de las acciones sobre cuentas.
ACCOUNT_ERRORS: dict[int | str, dict[str, Any]] = {
    403: {"description": "FORBIDDEN: sin permiso sobre esa cuenta"},
    409: {"description": "USER_STATUS_INVALID"},
}


@router.get("/stats")
async def admin_overview(
    session: DbSession,
    _: AdminOrSuper,
    days: Annotated[int, Query(ge=7, le=180)] = 30,
) -> AdminOverview:
    """Usuarios por rol y estado, viajes por dia y hora, ocupacion, cancelaciones,
    no-shows, rutas frecuentes, calificaciones y pendientes."""
    return await overview(session, days)


# --- Usuarios ------------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    session: DbSession,
    _: AdminOrSuper,
    q: str | None = None,
    role: UserRole | None = None,
    status: UserStatus | None = None,
    limit: Limit = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[AdminUserRow]:
    """Busqueda por nombre o correo, del mas reciente al mas antiguo."""
    return await AdminUserService(session).search(q, role, status, limit, cursor)


@router.get("/users/{user_id}")
async def user_detail(user_id: uuid.UUID, session: DbSession, _: AdminOrSuper) -> AdminUserDetail:
    return await AdminUserService(session).detail(user_id)


@router.post("/users/{user_id}/suspend", responses=ACCOUNT_ERRORS)
async def suspend_user(
    user_id: uuid.UUID, body: SuspendRequest, session: DbSession, actor: AdminActor
) -> AdminUserDetail:
    """Suspende la cuenta (con o sin fecha de fin) y cancela sus viajes y reservas."""
    return await AdminUserService(session).suspend(actor, user_id, body.reason, body.days)


@router.post("/users/{user_id}/reinstate", responses=ACCOUNT_ERRORS)
async def reinstate_user(
    user_id: uuid.UUID, body: OptionalReason, session: DbSession, actor: AdminActor
) -> AdminUserDetail:
    return await AdminUserService(session).reinstate(actor, user_id, body.reason)


@router.post("/users/{user_id}/block", responses=ACCOUNT_ERRORS)
async def block_user(
    user_id: uuid.UUID, body: ReasonRequest, session: DbSession, actor: AdminActor
) -> AdminUserDetail:
    """Bloqueo definitivo: cierra sus sesiones y cancela sus viajes y reservas."""
    return await AdminUserService(session).block(actor, user_id, body.reason)


@router.post("/users/{user_id}/lift-ban", responses={409: {"description": "SUSPENSION_ENDED"}})
async def lift_booking_ban(
    user_id: uuid.UUID, body: OptionalReason, session: DbSession, actor: AdminActor
) -> AdminUserDetail:
    """Levanta antes de tiempo la suspension de reservas por ausencias."""
    return await AdminUserService(session).lift_booking_ban(actor, user_id, body.reason)


# --- Viajes --------------------------------------------------------------------------------


@router.get("/trips")
async def list_trips(
    session: DbSession,
    _: AdminOrSuper,
    status: TripStatus | None = None,
    day: date | None = Query(default=None, description="Fecha local de salida"),
    q: str | None = Query(default=None, description="Nombre o correo del conductor"),
    limit: Limit = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[AdminTripRow]:
    return await AdminTripService(session).search(status, day, q, limit, cursor)


@router.get("/trips/{trip_id}")
async def trip_detail(trip_id: uuid.UUID, session: DbSession, _: AdminOrSuper) -> AdminTripDetail:
    """Viaje con vehiculo, placa, reservas y emergencias."""
    return await AdminTripService(session).detail(trip_id)


@router.post("/trips/{trip_id}/cancel", responses={409: {"description": "TRIP_NOT_EDITABLE"}})
async def cancel_trip(
    trip_id: uuid.UUID, body: ReasonRequest, session: DbSession, actor: AdminActor
) -> AdminTripDetail:
    return await AdminTripService(session).cancel(actor, trip_id, body.reason)


@router.get("/trips/{trip_id}/messages")
async def trip_messages(
    trip_id: uuid.UUID, session: DbSession, actor: AdminActor
) -> list[AdminMessage]:
    """Chat grupal del viaje (incluidos los ocultos). Cada lectura queda en la auditoria."""
    return await AdminTripService(session).messages(actor, trip_id)


# --- Moderacion ----------------------------------------------------------------------------


@router.post("/messages/{message_id}/hide")
async def hide_message(
    message_id: uuid.UUID, body: HiddenRequest, session: DbSession, actor: AdminActor
) -> AdminMessage:
    """{hidden: true} lo oculta del chat; false lo vuelve a mostrar."""
    return await AdminTripService(session).set_message_hidden(actor, message_id, body.hidden)


@router.get("/ratings")
async def list_ratings(
    session: DbSession,
    _: AdminOrSuper,
    hidden: bool | None = None,
    limit: Limit = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[AdminRating]:
    """Calificaciones con comentario, para moderar."""
    return await AdminTripService(session).ratings(hidden, limit, cursor)


@router.post("/ratings/{rating_id}/hide")
async def hide_rating(
    rating_id: uuid.UUID, body: HiddenRequest, session: DbSession, actor: AdminActor
) -> AdminRating:
    """Oculta o muestra el comentario; las estrellas siguen contando."""
    return await AdminTripService(session).set_rating_hidden(actor, rating_id, body.hidden)
