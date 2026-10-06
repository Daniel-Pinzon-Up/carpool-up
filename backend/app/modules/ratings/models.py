import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, UUIDPrimaryKey
from app.modules.trips.models import Trip

# Criterios por rol de quien recibe la calificacion (seccion 5.7).
DRIVER_CRITERIA = ("punctuality", "safe_driving", "courtesy", "cleanliness")
PASSENGER_CRITERIA = ("punctuality", "courtesy", "compliance")
MAX_COMMENT = 300


class Rating(UUIDPrimaryKey, Base):
    """Una calificacion de un participante a otro por un viaje completado.

    hidden oculta el comentario (moderacion, paso 12); la puntuacion se conserva.
    """

    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("trip_id", "author_id", "target_id", name="uq_ratings_pair"),
        CheckConstraint("author_id <> target_id", name="not_self"),
        CheckConstraint("target_role IN ('driver', 'passenger')", name="target_role_values"),
        CheckConstraint(f"char_length(comment) <= {MAX_COMMENT}", name="comment_length"),
        Index("ix_ratings_target_created", "target_id", "created_at"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Rol de quien recibe: decide los criterios.
    target_role: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trip: Mapped[Trip] = relationship(lazy="selectin")
    scores: Mapped[list["RatingScore"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class RatingScore(Base):
    """Estrellas (1 a 5) de un criterio."""

    __tablename__ = "rating_scores"
    __table_args__ = (CheckConstraint("stars BETWEEN 1 AND 5", name="stars_range"),)

    rating_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ratings.id", ondelete="CASCADE"), primary_key=True
    )
    criterion: Mapped[str] = mapped_column(Text, primary_key=True)
    stars: Mapped[int] = mapped_column(SmallInteger, nullable=False)
