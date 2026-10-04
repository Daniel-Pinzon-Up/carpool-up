import uuid

from fastapi import APIRouter, status

from app.core.auth import ActiveUser, SuperAdmin, SuperAdminActor
from app.core.deps import DbSession
from app.core.enums import PlaceKind
from app.modules.places.schemas import CustomPlaceCreate, PlaceCreate, PlaceOut, PlaceUpdate
from app.modules.places.service import PlaceService

router = APIRouter(prefix="/places", tags=["places"])
admin_router = APIRouter(prefix="/admin/places", tags=["admin: places"])


@router.get("")
async def list_places(session: DbSession, kind: PlaceKind | None = None) -> list[PlaceOut]:
    """Catalogo publico de puntos activos de Pamplona."""
    return [PlaceOut.model_validate(p) for p in await PlaceService(session).catalog(kind)]


@router.post("/custom", status_code=status.HTTP_201_CREATED)
async def create_custom_place(
    body: CustomPlaceCreate, session: DbSession, user: ActiveUser
) -> PlaceOut:
    """Pin libre elegido en el mapa. Debe estar dentro del area de servicio."""
    return PlaceOut.model_validate(await PlaceService(session).create_custom(body, user))


@admin_router.get("")
async def admin_list_places(
    session: DbSession, _: SuperAdmin, kind: PlaceKind | None = None
) -> list[PlaceOut]:
    places = await PlaceService(session).catalog(kind, include_inactive=True)
    return [PlaceOut.model_validate(p) for p in places]


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def create_place(body: PlaceCreate, session: DbSession, actor: SuperAdminActor) -> PlaceOut:
    return PlaceOut.model_validate(await PlaceService(session).create(body, actor))


@admin_router.patch("/{place_id}")
async def update_place(
    place_id: uuid.UUID, body: PlaceUpdate, session: DbSession, actor: SuperAdminActor
) -> PlaceOut:
    return PlaceOut.model_validate(await PlaceService(session).update(place_id, body, actor))


@admin_router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_place(place_id: uuid.UUID, session: DbSession, actor: SuperAdminActor) -> None:
    """Desactiva el punto: deja de aparecer en el catalogo pero se conserva el historial."""
    await PlaceService(session).deactivate(place_id, actor)
