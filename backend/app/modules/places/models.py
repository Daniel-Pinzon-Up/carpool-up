from geoalchemy2 import Geometry, WKBElement, WKTElement
from sqlalchemy import Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import PlaceKind
from app.core.geo import lat_lon


class Place(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Punto predefinido (campus, sector, referencia) o pin libre de un usuario (custom)."""

    __tablename__ = "places"
    __table_args__ = (
        Index("ix_places_kind_active", "kind", "is_active"),
        Index("ix_places_created_by", "created_by"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[PlaceKind] = mapped_column(pg_enum(PlaceKind, "place_kind"), nullable=False)
    point: Mapped[WKBElement | WKTElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @property
    def lat(self) -> float:
        return lat_lon(self.point)[0]

    @property
    def lon(self) -> float:
        return lat_lon(self.point)[1]
