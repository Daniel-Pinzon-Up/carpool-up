import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.enums import PlaceKind
from app.core.errors import AppError, NotFoundError
from app.core.geo import point
from app.modules.audit.service import AuditService
from app.modules.places.models import Place
from app.modules.places.repository import PlaceRepository
from app.modules.places.schemas import CustomPlaceCreate, PlaceCreate, PlaceOut, PlaceUpdate
from app.modules.settings.service import SettingsService
from app.modules.users.models import User

ENTITY = "place"


def _snapshot(place: Place) -> dict[str, Any]:
    return PlaceOut.model_validate(place).model_dump(mode="json")


class PlaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PlaceRepository(session)
        self.audit = AuditService(session)

    async def _check_area(self, lat: float, lon: float) -> None:
        area = await SettingsService(self.session).service_area()
        if not area.contains(lat, lon):
            raise AppError(
                "PLACE_OUT_OF_AREA",
                "Point is outside the service area",
                422,
                {"service_area": area.model_dump()},
            )

    async def _get(self, place_id: uuid.UUID) -> Place:
        place = await self.repo.get(place_id)
        if place is None or place.kind == PlaceKind.CUSTOM:
            raise NotFoundError(ENTITY)
        return place

    async def catalog(
        self, kind: PlaceKind | None = None, include_inactive: bool = False
    ) -> list[Place]:
        return await self.repo.catalog(kind, include_inactive)

    async def create(self, data: PlaceCreate, actor: Actor) -> Place:
        await self._check_area(data.lat, data.lon)
        if await self.repo.by_name_and_kind(data.name, data.kind):
            raise AppError("PLACE_NAME_TAKEN", "A place with this name already exists", 409)
        place = Place(name=data.name, kind=data.kind, point=point(data.lat, data.lon))
        self.repo.add(place)
        await self.session.flush()
        self.audit.record(actor, "place.create", ENTITY, place.id, None, _snapshot(place))
        await self.session.commit()
        return place

    async def update(self, place_id: uuid.UUID, data: PlaceUpdate, actor: Actor) -> Place:
        place = await self._get(place_id)
        before = _snapshot(place)
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        lat = changes.pop("lat", place.lat)
        lon = changes.pop("lon", place.lon)
        if (lat, lon) != (place.lat, place.lon):
            await self._check_area(lat, lon)
            place.point = point(lat, lon)
        new_name = changes.get("name", place.name)
        new_kind = changes.get("kind", place.kind)
        duplicate = await self.repo.by_name_and_kind(new_name, new_kind)
        if duplicate is not None and duplicate.id != place.id:
            raise AppError("PLACE_NAME_TAKEN", "A place with this name already exists", 409)
        for field, value in changes.items():
            setattr(place, field, value)
        self.audit.record(actor, "place.update", ENTITY, place.id, before, _snapshot(place))
        await self.session.commit()
        await self.session.refresh(place)
        return place

    async def deactivate(self, place_id: uuid.UUID, actor: Actor) -> None:
        """Los puntos no se borran: viajes y reservas pasadas pueden apuntar a ellos."""
        place = await self._get(place_id)
        if not place.is_active:
            return
        before = _snapshot(place)
        place.is_active = False
        self.audit.record(actor, "place.deactivate", ENTITY, place.id, before, _snapshot(place))
        await self.session.commit()

    async def create_custom(self, data: CustomPlaceCreate, user: User) -> Place:
        """Pin libre en el mapa. Solo lo ve su autor; no entra al catalogo publico."""
        await self._check_area(data.lat, data.lon)
        place = Place(
            name=data.name,
            kind=PlaceKind.CUSTOM,
            point=point(data.lat, data.lon),
            created_by=user.id,
        )
        self.repo.add(place)
        await self.session.commit()
        await self.session.refresh(place)
        return place
