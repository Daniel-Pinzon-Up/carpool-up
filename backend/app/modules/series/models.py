import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import SeriesStatus, StopKind
from app.modules.places.models import Place
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle


class TripSeries(UUIDPrimaryKey, Timestamps, Base):
    """Plantilla de un viaje recurrente. Al publicarla se generan todas sus ocurrencias."""

    __tablename__ = "trip_series"
    __table_args__ = (
        CheckConstraint("window_end >= window_start", name="window_order"),
        CheckConstraint("seats BETWEEN 1 AND 7", name="seats_range"),
        CheckConstraint("price_per_seat >= 0", name="price_non_negative"),
        CheckConstraint(
            "cardinality(weekdays) BETWEEN 1 AND 7 "
            "AND weekdays <@ ARRAY[0,1,2,3,4,5,6]::smallint[]",
            name="weekdays_valid",
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False
    )
    # 0 = lunes ... 6 = domingo, igual que pico_placa_rules.weekday.
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    departure_time: Mapped[time] = mapped_column(Time, nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price_per_seat: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SeriesStatus] = mapped_column(
        pg_enum(SeriesStatus, "series_status"), nullable=False, default=SeriesStatus.ACTIVE
    )
    # Copia de las reglas: [{"kind": "pets", "value": "allowed"}, ...]
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    driver: Mapped[User] = relationship(lazy="selectin")
    vehicle: Mapped[Vehicle] = relationship(lazy="selectin")
    stops: Mapped[list["SeriesStop"]] = relationship(
        order_by="SeriesStop.position", cascade="all, delete-orphan", lazy="selectin"
    )


class SeriesStop(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "series_stops"
    __table_args__ = (UniqueConstraint("series_id", "position", name="uq_series_stops_position"),)

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_series.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    kind: Mapped[StopKind] = mapped_column(pg_enum(StopKind, "stop_kind"), nullable=False)

    place: Mapped[Place] = relationship(lazy="selectin")
