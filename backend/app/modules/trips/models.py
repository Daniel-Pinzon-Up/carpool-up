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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import RuleKind, StopKind, TripStatus
from app.modules.places.models import Place
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle


class Trip(UUIDPrimaryKey, Timestamps, Base):
    """Un viaje concreto: ocurrencia de una serie (series_id) o viaje puntual (series_id nulo).

    Asientos y precio son copia de la serie al generarse; el conductor puede ajustar una
    ocurrencia sin tocar la serie.
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
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_series.id", ondelete="CASCADE"), index=True
    )
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seats_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price_per_seat: Mapped[int] = mapped_column(Integer, nullable=False)
    route: Mapped[WKBElement | WKTElement] = mapped_column(
        Geometry("LINESTRING", srid=4326, spatial_index=True), nullable=False
    )
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    est_duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    # Duracion de OSRM sin factor de trafico: el job semanal compara la real contra esta.
    osrm_duration_s: Mapped[int | None] = mapped_column(Integer)
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    driver: Mapped[User] = relationship(lazy="selectin")
    vehicle: Mapped[Vehicle] = relationship(lazy="selectin")
    stops: Mapped[list["TripStop"]] = relationship(
        order_by="TripStop.position", cascade="all, delete-orphan", lazy="selectin"
    )
    rules: Mapped[list["TripRule"]] = relationship(
        order_by="TripRule.kind", cascade="all, delete-orphan", lazy="selectin"
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


class TripRule(UUIDPrimaryKey, Timestamps, Base):
    """Regla del viaje: allowed/not_allowed, o texto libre para custom."""

    __tablename__ = "trip_rules"
    __table_args__ = (UniqueConstraint("trip_id", "kind", name="uq_trip_rules_kind"),)

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[RuleKind] = mapped_column(pg_enum(RuleKind, "rule_kind"), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
