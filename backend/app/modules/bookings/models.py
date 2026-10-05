import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import BookingStatus, SubscriptionStatus
from app.modules.places.models import Place
from app.modules.series.models import TripSeries
from app.modules.trips.models import Trip
from app.modules.users.models import User

# Reservas que ocupan cupo y reservas "activas" (una por pasajero y viaje).
HOLDING_STATUSES = (BookingStatus.ACCEPTED, BookingStatus.CANCEL_REQUESTED)
ACTIVE_STATUSES = (BookingStatus.REQUESTED, *HOLDING_STATUSES)


class SeriesSubscription(UUIDPrimaryKey, Timestamps, Base):
    """Solicitud de un pasajero para unirse a una serie durante un rango de fechas.

    El conductor la aprueba una sola vez; al aprobarla se crean las reservas aceptadas de
    cada ocurrencia del rango con cupo y sin pico y placa.
    """

    __tablename__ = "series_subscriptions"
    __table_args__ = (
        CheckConstraint("to_date >= from_date", name="range_order"),
        CheckConstraint("seats BETWEEN 1 AND 7", name="seats_range"),
        Index(
            "uq_series_subscriptions_open",
            "series_id",
            "passenger_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'active')"),
        ),
        Index("ix_series_subscriptions_passenger", "passenger_id", "status"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_series.id", ondelete="CASCADE"), nullable=False
    )
    passenger_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    pickup_place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    dropoff_place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="RESTRICT"), nullable=False
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[SubscriptionStatus] = mapped_column(
        pg_enum(SubscriptionStatus, "subscription_status"),
        nullable=False,
        default=SubscriptionStatus.REQUESTED,
    )
    # Vence sin respuesta: pending_request_hours o la primera salida del rango.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)

    series: Mapped[TripSeries] = relationship(lazy="selectin")
    passenger: Mapped[User] = relationship(lazy="selectin")
    pickup_place: Mapped[Place] = relationship(foreign_keys=[pickup_place_id], lazy="selectin")
    dropoff_place: Mapped[Place] = relationship(foreign_keys=[dropoff_place_id], lazy="selectin")


class Booking(UUIDPrimaryKey, Timestamps, Base):
    """Reserva de un pasajero en un viaje concreto.

    Guarda los lugares que eligio el pasajero y el punto de encuentro calculado sobre el
    viaje (parada o punto de la ruta) con su hora estimada. Ocupa cupo en accepted y
    cancel_requested.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("seats BETWEEN 1 AND 7", name="seats_range"),
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
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series_subscriptions.id", ondelete="SET NULL"),
        index=True,
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

    trip: Mapped[Trip] = relationship(lazy="selectin")
    passenger: Mapped[User] = relationship(lazy="selectin")
    pickup_place: Mapped[Place] = relationship(foreign_keys=[pickup_place_id], lazy="selectin")
    dropoff_place: Mapped[Place] = relationship(foreign_keys=[dropoff_place_id], lazy="selectin")
