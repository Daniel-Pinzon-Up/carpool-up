import uuid
from datetime import datetime

from geoalchemy2 import Geometry, WKBElement, WKTElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import StopKind, TripStatus
from app.modules.places.models import Place
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle


class Trip(UUIDPrimaryKey, Timestamps, Base):
    """Un viaje publicado por un conductor, con su ruta (PostGIS) y sus paradas.

    rules guarda las reglas del viaje como lista de {"kind", "value"} (por ejemplo
    {"kind": "pets", "value": "not_allowed"}). share_token_hash es el enlace publico para
    seguir el viaje: se guarda el hash del token, nunca el token.
    """

    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("seats_total BETWEEN 1 AND 7", name="seats_range"),
        CheckConstraint("price_per_seat >= 0", name="price_non_negative"),
        CheckConstraint(
            "status <> 'cancelled_by_driver' OR cancel_reason IS NOT NULL",
            name="cancel_has_reason",
        ),
        Index("ix_trips_driver_departs", "driver_id", "departs_at"),
        # Busqueda en metros: ST_DWithin(route::geography, ...) (migracion 0008).
        Index(
            "ix_trips_route_geography",
            text("(route::geography)"),
            postgresql_using="gist",
            postgresql_where=text("status = 'scheduled' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_trips_scheduled_departs",
            "departs_at",
            postgresql_where=text("status = 'scheduled' AND deleted_at IS NULL"),
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seats_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price_per_seat: Mapped[int] = mapped_column(Integer, nullable=False)
    route: Mapped[WKBElement | WKTElement] = mapped_column(
        Geometry("LINESTRING", srid=4326, spatial_index=True), nullable=False
    )
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    est_duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        pg_enum(TripStatus, "trip_status"), nullable=False, default=TripStatus.SCHEDULED
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ultimo aviso para calificar antes de que cierre el plazo.
    rating_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rules: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    share_token_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    driver: Mapped[User] = relationship(lazy="selectin")
    vehicle: Mapped[Vehicle] = relationship(lazy="selectin")
    stops: Mapped[list["TripStop"]] = relationship(
        order_by="TripStop.position", cascade="all, delete-orphan", lazy="selectin"
    )


class TripStop(UUIDPrimaryKey, Timestamps, Base):
    """Paradas ordenadas: el origen es la posicion 0 y el destino la ultima."""

    __tablename__ = "trip_stops"
    __table_args__ = (UniqueConstraint("trip_id", "position", name="uq_trip_stops_position"),)

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    kind: Mapped[StopKind] = mapped_column(pg_enum(StopKind, "stop_kind"), nullable=False)
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    place: Mapped[Place] = relationship(lazy="selectin")
