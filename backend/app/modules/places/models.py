import uuid

from geoalchemy2 import Geometry, WKBElement, WKTElement
from sqlalchemy import Boolean, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import PlaceKind
from app.core.geo import lat_lon


class Place(UUIDPrimaryKey, Timestamps, Base):
    """Punto predefinido (campus, sector, referencia) o pin libre de un usuario (custom)."""

    __tablename__ = "places"
    __table_args__ = (Index("ix_places_kind_active", "kind", "is_active"),)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[PlaceKind] = mapped_column(pg_enum(PlaceKind, "place_kind"), nullable=False)
    point: Mapped[WKBElement | WKTElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    @property
    def lat(self) -> float:
        return lat_lon(self.point)[0]

    @property
    def lon(self) -> float:
        return lat_lon(self.point)[1]
