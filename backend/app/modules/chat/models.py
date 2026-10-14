import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, UUIDPrimaryKey
from app.modules.trips.models import Trip
from app.modules.users.models import User

MAX_MESSAGE_LENGTH = 1000


class Message(UUIDPrimaryKey, Base):
    """Mensaje del chat de un viaje: lo leen y escriben el conductor y los pasajeros aceptados.

    El chat se cierra (solo lectura) cuando el viaje termina o se cancela, y se borra
    chat_retention_days despues. hidden lo marca la moderacion.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {MAX_MESSAGE_LENGTH}", name="body_length"
        ),
        Index("ix_messages_trip_sent", "trip_id", "sent_at", "id"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    trip: Mapped[Trip] = relationship(lazy="selectin")
    sender: Mapped[User] = relationship(lazy="selectin")
