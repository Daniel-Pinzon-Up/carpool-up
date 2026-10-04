import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import utcnow
from app.core.enums import Language
from app.core.errors import AppError
from app.modules.audit.service import AuditService
from app.modules.legal.models import LegalDocument, TermsAcceptance
from app.modules.legal.repository import LegalRepository
from app.modules.legal.schemas import LegalPublish
from app.modules.users.models import User

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

    async def pending_for(self, user: User) -> list[LegalDocument]:
        """Versiones vigentes (en su idioma o en espanol) que el usuario no ha aceptado."""
        accepted = await self.repo.accepted_ids(user.id)
        return [
            doc for doc in await self.current(user.preferred_language) if doc.id not in accepted
        ]

    def record_acceptance(
        self, user_id: uuid.UUID, documents: list[LegalDocument], ip: str | None
    ) -> None:
        """No hace commit: se confirma junto con el registro o con la aceptacion."""
        for document in documents:
            self.repo.add_acceptance(
                TermsAcceptance(user_id=user_id, legal_document_id=document.id, ip=ip)
            )

    async def accept(self, user: User, document_ids: list[uuid.UUID], ip: str | None) -> None:
        """Acepta versiones vigentes pendientes. Ids de versiones no vigentes se rechazan."""
        pending = {doc.id: doc for doc in await self.pending_for(user)}
        current_ids = {doc.id for doc in await self.current(user.preferred_language)}
        unknown = [doc_id for doc_id in document_ids if doc_id not in current_ids]
        if unknown:
            raise AppError(
                "LEGAL_VERSION_NOT_CURRENT",
                "Only current versions can be accepted",
                422,
                {"document_ids": [str(doc_id) for doc_id in unknown]},
            )
        self.record_acceptance(
            user.id, [pending[doc_id] for doc_id in document_ids if doc_id in pending], ip
        )
        await self.session.commit()
