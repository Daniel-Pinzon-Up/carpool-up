import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import SuspensionKind


class Suspension(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Sancion temporal. booking_ban impide reservar; las de no-show son automaticas
    (created_by nulo, paso 10) y las demas las crea un administrador (paso 12)."""

    __tablename__ = "suspensions"
    # created_by lo pone el servicio: nulo significa sancion automatica.
    stamp_creator = False
    __table_args__ = (
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="period_order"),
        Index("ix_suspensions_user_kind", "user_id", "kind"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[SuspensionKind] = mapped_column(
        pg_enum(SuspensionKind, "suspension_kind"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
