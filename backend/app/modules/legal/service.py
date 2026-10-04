from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import utcnow
from app.core.enums import Language
from app.core.errors import AppError
from app.modules.audit.service import AuditService
from app.modules.legal.models import LegalDocument
from app.modules.legal.repository import LegalRepository
from app.modules.legal.schemas import LegalPublish

FALLBACK_LANGUAGE = Language.ES


class LegalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LegalRepository(session)

    async def list_all(self) -> list[LegalDocument]:
        return await self.repo.list_all()

    async def current(self, language: Language) -> list[LegalDocument]:
        """Version vigente de cada documento; si falta en el idioma pedido se usa el espanol."""
        documents = {doc.kind: doc for doc in await self.repo.current(language)}
        if language != FALLBACK_LANGUAGE:
            for doc in await self.repo.current(FALLBACK_LANGUAGE):
                documents.setdefault(doc.kind, doc)
        return sorted(documents.values(), key=lambda doc: doc.kind)

    async def publish(self, data: LegalPublish, actor: Actor | None) -> LegalDocument:
        """Publica una version nueva y la deja vigente. actor es None solo en el seed."""
        if await self.repo.find(data.kind, data.language, data.version):
            raise AppError(
                "LEGAL_VERSION_EXISTS",
                "This version is already published",
                409,
                {"kind": data.kind, "language": data.language, "version": data.version},
            )
        await self.repo.retire_current(data.kind, data.language)
        document = LegalDocument(**data.model_dump(), published_at=utcnow(), is_current=True)
        self.repo.add(document)
        await self.session.flush()
        AuditService(self.session).record(
            actor,
            "legal.publish",
            "legal_document",
            document.id,
            None,
            {"kind": data.kind, "language": data.language, "version": data.version},
        )
        await self.session.commit()
        return document
