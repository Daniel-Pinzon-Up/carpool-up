import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey
from app.modules.trips.models import Trip
from app.modules.users.models import User


class TrustedContact(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Contacto de confianza del usuario (maximo trusted_contacts_max). Solo lo ve su dueno."""

    __tablename__ = "trusted_contacts"
    __table_args__ = (Index("ix_trusted_contacts_user", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    # Parentesco o relacion (columna relationship; el atributo no tapa a relationship()).
    relation: Mapped[str | None] = mapped_column("relationship", Text)


class EmergencyEvent(UUIDPrimaryKey, Authorship, Base):
    """Boton de emergencia: alerta en vivo a los administradores con la ultima ubicacion."""

    __tablename__ = "emergency_events"
    __table_args__ = (
        CheckConstraint("(lat IS NULL) = (lon IS NULL)", name="location_pair"),
        Index(
            "ix_emergency_events_open",
            "created_at",
            postgresql_where=text("handled_at IS NULL"),
        ),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)

    trip: Mapped[Trip] = relationship(lazy="selectin")
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="selectin")
