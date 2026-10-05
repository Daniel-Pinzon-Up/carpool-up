import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import CancelRequestStatus
from app.modules.bookings.models import Booking


class CancellationRequest(UUIDPrimaryKey, Timestamps, Base):
    """Cancelacion tardia (menos de cancel_free_hours antes de salir): decide el conductor."""

    __tablename__ = "cancellation_requests"
    __table_args__ = (
        Index(
            "uq_cancellation_requests_pending",
            "booking_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CancelRequestStatus] = mapped_column(
        pg_enum(CancelRequestStatus, "cancel_request_status"),
        nullable=False,
        default=CancelRequestStatus.PENDING,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking: Mapped[Booking] = relationship(lazy="selectin")
