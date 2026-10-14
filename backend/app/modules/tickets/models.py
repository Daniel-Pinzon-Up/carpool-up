import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Authorship, Base, UUIDPrimaryKey
from app.modules.bookings.models import Booking


class Ticket(UUIDPrimaryKey, Authorship, Base):
    """Comprobante informativo (sin pago en la app ni QR): uno por reserva que abordo.

    Se emite al finalizar el viaje. El conductor puede marcar que recibio el aporte.
    """

    __tablename__ = "tickets"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount_non_negative"),)

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking: Mapped[Booking] = relationship(lazy="selectin")
