"""Documento de identidad como tipo de documento.

El registro pide ahora el documento de identidad en lugar del carnet o la constancia.
Los valores anteriores se conservan para los documentos que ya existen.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE doc_kind ADD VALUE IF NOT EXISTS 'identity_document'")


def downgrade() -> None:
    # PostgreSQL no permite quitar un valor de un enum; las filas con este tipo pasan a carnet.
    op.execute(
        "UPDATE identity_documents SET kind = 'student_card' WHERE kind = 'identity_document'"
    )
    op.execute("ALTER TYPE doc_kind RENAME TO doc_kind_old")
    op.execute("CREATE TYPE doc_kind AS ENUM ('student_card', 'institutional_proof')")
    op.execute(
        "ALTER TABLE identity_documents ALTER COLUMN kind TYPE doc_kind USING kind::text::doc_kind"
    )
    op.execute("DROP TYPE doc_kind_old")
