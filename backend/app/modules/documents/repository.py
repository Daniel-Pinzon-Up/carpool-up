import uuid
from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DocKind
from app.modules.documents.models import Document


async def latest_document(
    session: AsyncSession, user_id: uuid.UUID, kinds: Sequence[DocKind]
) -> Document | None:
    """El ultimo documento de esos tipos que subio la persona (el que vale)."""
    return await session.scalar(
        select(Document)
        .where(Document.user_id == user_id, Document.kind.in_(kinds))
        .order_by(desc(Document.created_at), desc(Document.id))
        .limit(1)
    )


async def documents_of(
    session: AsyncSession, user_id: uuid.UUID, kinds: Sequence[DocKind]
) -> list[Document]:
    rows = await session.scalars(
        select(Document)
        .where(Document.user_id == user_id, Document.kind.in_(kinds))
        .order_by(desc(Document.created_at))
    )
    return list(rows.all())
