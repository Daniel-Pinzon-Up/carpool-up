import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import BookingStatus
from app.modules.places.models import Place
from app.modules.trips.models import Trip
from app.modules.users.models import User

# Reservas que ocupan cupo y reservas "activas" (una por pasajero y viaje).
HOLDING_STATUSES = (BookingStatus.ACCEPTED, BookingStatus.CANCEL_REQUESTED)
ACTIVE_STATUSES = (BookingStatus.REQUESTED, *HOLDING_STATUSES)


class Booking(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Reserva de un pasajero en un viaje concreto.

    Guarda los lugares que eligio el pasajero y el punto de encuentro calculado sobre el
    viaje (parada o punto de la ruta) con su hora estimada. Ocupa cupo en accepted y
    cancel_requested.

    Cancelacion tardia: el pasajero la pide (cancel_requested, con su motivo en cancel_reason)
    y el conductor la decide. Ticket: al finalizar el viaje, quien abordo recibe un codigo
    informativo (ticket_code) por el aporte (ticket_amount); el conductor marca si lo recibio.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("seats BETWEEN 1 AND 7", name="seats_range"),
        CheckConstraint("ticket_amount >= 0", name="ticket_amount_non_negative"),
        Index(
            "uq_bookings_active_passenger",
            "trip_id",
            "passenger_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'accepted', 'cancel_requested')"),
        ),
        Index("ix_bookings_trip_status", "trip_id", "status"),
        Index("ix_bookings_passenger_pickup", "passenger_id", "pickup_eta"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    passenger_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    pickup_place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    dropoff_place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    # Punto de encuentro sobre el viaje: parada (con nombre) o punto de la ruta (sin nombre).
    pickup_name: Mapped[str | None] = mapped_column(Text)
    pickup_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_lon: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pickup_walk_m: Mapped[int] = mapped_column(Integer, nullable=False)
    dropoff_name: Mapped[str | None] = mapped_column(Text)
    dropoff_lat: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_lon: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dropoff_walk_m: Mapped[int] = mapped_column(Integer, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[BookingStatus] = mapped_column(
        pg_enum(BookingStatus, "booking_status"), nullable=False, default=BookingStatus.REQUESTED
    )
    # Vence sin respuesta: pending_request_hours o la salida, lo primero que llegue.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # El viaje cambio de hora, ruta o vehiculo: el pasajero cancela sin penalizacion.
    penalty_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    boarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    no_show_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    ticket_code: Mapped[str | None] = mapped_column(Text, unique=True)
    ticket_amount: Mapped[int | None] = mapped_column(Integer)
    ticket_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trip: Mapped[Trip] = relationship(lazy="selectin")
    passenger: Mapped[User] = relationship(foreign_keys=[passenger_id], lazy="selectin")
    pickup_place: Mapped[Place] = relationship(foreign_keys=[pickup_place_id], lazy="selectin")
    dropoff_place: Mapped[Place] = relationship(foreign_keys=[dropoff_place_id], lazy="selectin")
