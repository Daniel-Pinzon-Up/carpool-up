from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import Language, LegalKind


class LegalDocument(UUIDPrimaryKey, Timestamps, Base):
    """Terminos y condiciones y autorizacion de tratamiento de datos (Ley 1581 de 2012).

    Las versiones publicadas no se editan: un cambio es una version nueva.
    """

    __tablename__ = "legal_documents"
    __table_args__ = (
        UniqueConstraint("kind", "language", "version", name="uq_legal_documents_version"),
        Index(
            "uq_legal_documents_current",
            "kind",
            "language",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    kind: Mapped[LegalKind] = mapped_column(pg_enum(LegalKind, "legal_kind"), nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Language] = mapped_column(pg_enum(Language, "language"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
