import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, Base):
    """Registro inmutable de operaciones sensibles. Un trigger impide UPDATE y DELETE."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at_id", "created_at", "id"),
        Index("ix_audit_log_entity", "entity", "entity_id"),
    )

    # Autor de la entrada. En la base se llama created_by, como en las demas tablas.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        "created_by", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Siempre nulo: la tabla es inmutable (el trigger rechaza UPDATE y DELETE).
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(Text)
    # clock_timestamp y no now(): varias entradas de una misma transaccion quedan ordenadas.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
