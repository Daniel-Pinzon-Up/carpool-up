import uuid

from fastapi import APIRouter, Request, status

from app.core.auth import ActiveUser, AdminActor
from app.core.deps import DbSession
from app.core.rate_limit import limiter
from app.modules.safety.schemas import (
    ContactIn,
    ContactOut,
    ContactUpdate,
    EmergencyIn,
    EmergencyOut,
    EmergencyReport,
    HandleIn,
    LiveLocation,
    PublicTrip,
    ShareLinkOut,
)
from app.modules.safety.service import SafetyService

router = APIRouter(tags=["safety"])
public_router = APIRouter(prefix="/public", tags=["public"])
admin_router = APIRouter(prefix="/admin/emergencies", tags=["admin"])


# --- Contactos de confianza ------------------------------------------------------------------


@router.get("/me/trusted-contacts")
async def list_contacts(user: ActiveUser, session: DbSession) -> list[ContactOut]:
    """Solo los ve su dueno."""
    return [ContactOut.model_validate(c) for c in await SafetyService(session).contacts(user)]


@router.post(
    "/me/trusted-contacts",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "TRUSTED_CONTACTS_LIMIT"}},
)
async def add_contact(body: ContactIn, user: ActiveUser, session: DbSession) -> ContactOut:
    return ContactOut.model_validate(await SafetyService(session).add_contact(user, body))


@router.patch("/me/trusted-contacts/{contact_id}")
async def update_contact(
    contact_id: uuid.UUID, body: ContactUpdate, user: ActiveUser, session: DbSession
) -> ContactOut:
    contact = await SafetyService(session).update_contact(user, contact_id, body)
    return ContactOut.model_validate(contact)


@router.delete("/me/trusted-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: uuid.UUID, user: ActiveUser, session: DbSession) -> None:
    await SafetyService(session).delete_contact(user, contact_id)


# --- Viaje en curso ----------------------------------------------------------------------------


@router.post(
    "/trips/{trip_id}/share-links",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "TRIP_NOT_SHAREABLE"}},
)
@limiter.limit("10/minute")
async def create_share_link(
    request: Request, trip_id: uuid.UUID, user: ActiveUser, session: DbSession
) -> ShareLinkOut:
    """Conductor o pasajero aceptado. El token solo se muestra en esta respuesta."""
    return await SafetyService(session).create_share_link(user, trip_id)


@router.get("/trips/{trip_id}/location")
async def trip_location(
    trip_id: uuid.UUID, user: ActiveUser, session: DbSession
) -> LiveLocation | None:
    """Ultima posicion del conductor (nula si no hay o el viaje no esta en curso)."""
    return await SafetyService(session).location(user, trip_id)


@router.post(
    "/trips/{trip_id}/emergency",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "TRIP_NOT_ACTIVE"}},
)
@limiter.limit("5/minute")
async def report_emergency(
    request: Request, trip_id: uuid.UUID, body: EmergencyIn, user: ActiveUser, session: DbSession
) -> EmergencyReport:
    """Alerta en vivo a los administradores con la ultima ubicacion; muestra la linea 123."""
    service = SafetyService(session)
    event = await service.emergency(user, trip_id, body)
    return EmergencyReport(
        emergency=event, phone=str(await service.settings.get("emergency_phone"))
    )


# --- Enlace publico ----------------------------------------------------------------------------


@public_router.get("/share/{token}", responses={404: {"description": "Vencido o inexistente"}})
@limiter.limit("60/minute")
async def shared_trip(request: Request, token: str, session: DbSession) -> PublicTrip:
    """Sin sesion. Solo lectura: ubicacion en vivo, vehiculo, placa y ruta."""
    return await SafetyService(session).public_trip(token)


# --- Administracion ------------------------------------------------------------------------------


@admin_router.get("")
async def list_emergencies(
    actor: AdminActor, session: DbSession, include_handled: bool = False
) -> list[EmergencyOut]:
    """Abiertas primero, de la mas reciente a la mas antigua."""
    return await SafetyService(session).open_emergencies(include_handled)


@admin_router.post("/{emergency_id}/handle", responses={409: {"description": "EMERGENCY_HANDLED"}})
async def handle_emergency(
    emergency_id: uuid.UUID, body: HandleIn, actor: AdminActor, session: DbSession
) -> EmergencyOut:
    """Queda en la auditoria."""
    return await SafetyService(session).handle_emergency(actor, emergency_id, body.resolution)
