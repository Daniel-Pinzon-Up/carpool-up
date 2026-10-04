from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Language, LegalKind
from app.modules.legal.models import LegalDocument


class LegalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[LegalDocument]:
        query = select(LegalDocument).order_by(
            LegalDocument.kind, LegalDocument.language, LegalDocument.published_at.desc()
        )
        return list((await self.session.scalars(query)).all())

    async def current(self, language: Language) -> list[LegalDocument]:
        query = select(LegalDocument).where(
            LegalDocument.language == language, LegalDocument.is_current.is_(True)
        )
        return list((await self.session.scalars(query.order_by(LegalDocument.kind))).all())

    async def find(self, kind: LegalKind, language: Language, version: str) -> LegalDocument | None:
        return await self.session.scalar(
            select(LegalDocument).where(
                LegalDocument.kind == kind,
                LegalDocument.language == language,
                LegalDocument.version == version,
            )
        )

    async def retire_current(self, kind: LegalKind, language: Language) -> None:
        await self.session.execute(
            update(LegalDocument)
            .where(
                LegalDocument.kind == kind,
                LegalDocument.language == language,
                LegalDocument.is_current.is_(True),
            )
            .values(is_current=False)
        )

    def add(self, document: LegalDocument) -> None:
        self.session.add(document)
