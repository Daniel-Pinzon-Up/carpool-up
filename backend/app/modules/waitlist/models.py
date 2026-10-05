import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, SmallInteger, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import WaitlistStatus
from app.modules.trips.models import Trip
from app.modules.users.models import User

OPEN_STATUSES = (WaitlistStatus.WAITING, WaitlistStatus.OFFERED)


class WaitlistEntry(UUIDPrimaryKey, Timestamps, Base):
    """Fila de espera de un viaje lleno. Guarda lo necesario para crear la reserva al
    confirmar la oferta (puestos, lugares y preferencias)."""

    __tablename__ = "waitlist_entries"
    __table_args__ = (
        CheckConstraint("seats BETWEEN 1 AND 7", name="seats_range"),
        Index(
            "uq_waitlist_entries_open",
            "trip_id",
            "passenger_id",
            unique=True,
            postgresql_where=text("status IN ('waiting', 'offered')"),
        ),
        Index("ix_waitlist_entries_trip_position", "trip_id", "position"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    passenger_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    pickup_place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    dropoff_place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[WaitlistStatus] = mapped_column(
        pg_enum(WaitlistStatus, "waitlist_status"), nullable=False, default=WaitlistStatus.WAITING
    )
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL")
    )

    trip: Mapped[Trip] = relationship(lazy="selectin")
    passenger: Mapped[User] = relationship(lazy="selectin")
