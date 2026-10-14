import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import ConversationKind
from app.modules.series.models import TripSeries
from app.modules.trips.models import Trip
from app.modules.users.models import User

MAX_MESSAGE_LENGTH = 1000


class Conversation(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Hilo de chat.

    trip_group: uno por ocurrencia (trip_id), con el conductor y los pasajeros aceptados.
    direct: conductor y un pasajero; dura toda la serie (series_id) o, en un viaje puntual,
    ese viaje (trip_id). Cerrado (closed_at) se puede leer pero no escribir.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'trip_group' AND trip_id IS NOT NULL AND passenger_id IS NULL) OR "
            "(kind = 'direct' AND passenger_id IS NOT NULL "
            "AND (trip_id IS NOT NULL OR series_id IS NOT NULL))",
            name="kind_shape",
        ),
        Index(
            "uq_conversations_trip_group",
            "trip_id",
            unique=True,
            postgresql_where=text("kind = 'trip_group'"),
        ),
        Index(
            "uq_conversations_direct_series",
            "series_id",
            "passenger_id",
            unique=True,
            postgresql_where=text("kind = 'direct' AND series_id IS NOT NULL"),
        ),
        Index(
            "uq_conversations_direct_trip",
            "trip_id",
            "passenger_id",
            unique=True,
            postgresql_where=text("kind = 'direct' AND series_id IS NULL"),
        ),
    )

    kind: Mapped[ConversationKind] = mapped_column(
        pg_enum(ConversationKind, "conversation_kind"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE")
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_series.id", ondelete="CASCADE")
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    passenger_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trip: Mapped[Trip | None] = relationship(lazy="selectin")
    series: Mapped[TripSeries | None] = relationship(lazy="selectin")
    driver: Mapped[User] = relationship(foreign_keys=[driver_id], lazy="selectin")
    passenger: Mapped[User | None] = relationship(foreign_keys=[passenger_id], lazy="selectin")
    members: Mapped[list["ConversationMember"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class ConversationMember(Authorship, Base):
    """Quien participa. left_at: salio (ya no lee ni escribe); last_read_at: hasta donde leyo."""

    __tablename__ = "conversation_members"
    __table_args__ = (Index("ix_conversation_members_user", "user_id"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="selectin")


class Message(UUIDPrimaryKey, Authorship, Base):
    """Texto plano de hasta 1000 caracteres. hidden lo marca la moderacion (paso 12)."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {MAX_MESSAGE_LENGTH}", name="body_length"
        ),
        Index("ix_messages_conversation_sent", "conversation_id", "sent_at", "id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sender: Mapped[User] = relationship(foreign_keys=[sender_id], lazy="selectin")
