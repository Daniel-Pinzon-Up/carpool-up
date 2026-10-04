import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PlaceKind
from app.modules.places.models import Place


class PlaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, place_id: uuid.UUID) -> Place | None:
        return await self.session.get(Place, place_id)

    async def catalog(self, kind: PlaceKind | None, include_inactive: bool) -> list[Place]:
        """Puntos predefinidos. Los pines custom nunca aparecen en el catalogo."""
        query = select(Place).where(Place.kind != PlaceKind.CUSTOM)
        if kind is not None:
            query = query.where(Place.kind == kind)
        if not include_inactive:
            query = query.where(Place.is_active.is_(True))
        return list((await self.session.scalars(query.order_by(Place.kind, Place.name))).all())

    async def by_name_and_kind(self, name: str, kind: PlaceKind) -> Place | None:
        return await self.session.scalar(
            select(Place).where(Place.name == name, Place.kind == kind)
        )

    def add(self, place: Place) -> None:
        self.session.add(place)
