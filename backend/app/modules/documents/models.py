import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import DocKind, ReviewStatus


class Document(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Documento que revisa un administrador: carnet o constancia (por semestre) y licencia de
    conduccion (con fecha de vencimiento). Subir uno nuevo crea otra fila; vale el ultimo."""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_user_kind_created", "user_id", "kind", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[DocKind] = mapped_column(pg_enum(DocKind, "doc_kind"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"), nullable=False, default=ReviewStatus.PENDING
    )
    # Carnet o constancia: semestre al que pertenece. Licencia: nulo.
    semester_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="RESTRICT"), index=True
    )
    # Licencia: vencimiento. Carnet o constancia: nulo.
    expires_on: Mapped[date | None] = mapped_column(Date)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    @property
    def is_license(self) -> bool:
        return self.kind == DocKind.DRIVER_LICENSE

    def is_valid_on(self, day: date) -> bool:
        """Licencia aprobada y no vencida: requisito para publicar viajes."""
        return (
            self.status == ReviewStatus.APPROVED
            and self.expires_on is not None
            and self.expires_on >= day
        )
