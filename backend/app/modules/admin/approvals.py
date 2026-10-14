"""Cola de aprobacion de carnets, constancias y licencias (administrador y superadmin).

Todos viven en la tabla documents; el tipo de la cola ("identity" o "license") decide que
clases de documento se muestran.
"""

import uuid
from typing import Any

from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import local_today, utcnow
from app.core.enums import IDENTITY_KINDS, DocKind, ReviewStatus, Sex, UserStatus
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.core.storage import private_file_response
from app.modules.admin.schemas import Applicant, ApprovalCounts, ApprovalItem, ApprovalType
from app.modules.audit.service import AuditService
from app.modules.documents.models import Document
from app.modules.notifications.service import Kind, NotificationService
from app.modules.semesters.models import Semester
from app.modules.semesters.repository import SemesterRepository
from app.modules.users.models import User

KINDS: dict[ApprovalType, tuple[DocKind, ...]] = {
    "identity": IDENTITY_KINDS,
    "license": (DocKind.DRIVER_LICENSE,),
}


def _applicant(user: User) -> Applicant:
    return Applicant(
        id=user.id,
        full_name=user.full_name,
        program=user.program,
        role=user.role,
        sex=user.sex,
        status=user.status,
    )


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)

    # --- Consulta -----------------------------------------------------------------------

    async def _item(self, document: Document, user: User) -> ApprovalItem:
        semester = (
            await self.session.get(Semester, document.semester_id) if document.semester_id else None
        )
        return ApprovalItem(
            id=document.id,
            type="license" if document.is_license else "identity",
            doc_kind=None if document.is_license else document.kind,
            status=document.status,
            submitted_at=document.updated_at,
            reviewed_at=document.reviewed_at,
            rejection_reason=document.rejection_reason,
            semester=semester.name if semester else None,
            license_expires_on=document.expires_on,
            applicant=_applicant(user),
        )

    async def queue(
        self, kind: ApprovalType, status: ReviewStatus, limit: int, cursor: str | None
    ) -> Page[ApprovalItem]:
        """Mas antiguos primero: se atiende en orden de llegada."""
        query = (
            select(Document, User)
            .join(User, User.id == Document.user_id)
            .where(
                Document.kind.in_(KINDS[kind]),
                Document.status == status,
                User.deleted_at.is_(None),
            )
        )
        if cursor:
            after_at, after_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    Document.updated_at > after_at,
                    and_(Document.updated_at == after_at, Document.id > after_id),
                )
            )
        query = query.order_by(Document.updated_at, Document.id).limit(limit + 1)
        rows = list((await self.session.execute(query)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [await self._item(document, user) for document, user in rows]
        last = rows[-1][0] if rows else None
        return Page(
            items=items,
            next_cursor=encode_cursor(last.updated_at, last.id) if has_more and last else None,
        )

    async def counts(self) -> ApprovalCounts:
        async def pending(kinds: tuple[DocKind, ...]) -> int:
            query = select(func.count()).where(
                Document.kind.in_(kinds), Document.status == ReviewStatus.PENDING
            )
            return int(await self.session.scalar(query) or 0)

        return ApprovalCounts(
            identity=await pending(KINDS["identity"]), license=await pending(KINDS["license"])
        )

    async def _find(self, approval_id: uuid.UUID) -> tuple[Document, User]:
        document = await self.session.get(Document, approval_id)
        if document is None:
            raise NotFoundError("approval")
        user = await self.session.get(User, document.user_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundError("approval")
        return document, user

    async def detail(self, approval_id: uuid.UUID) -> ApprovalItem:
        document, user = await self._find(approval_id)
        return await self._item(document, user)

    async def file(self, approval_id: uuid.UUID) -> FileResponse:
        document, _ = await self._find(approval_id)
        return private_file_response(document.file_path, document.content_type)

    # --- Decisiones -------------------------------------------------------------------------

    async def _reviewable(self, approval_id: uuid.UUID, actor: Actor) -> tuple[Document, User]:
        document, user = await self._find(approval_id)
        if user.id == actor.user.id:
            raise ForbiddenError("You cannot review your own documents")
        if document.status != ReviewStatus.PENDING:
            raise AppError(
                "APPROVAL_NOT_PENDING",
                "This item was already reviewed",
                409,
                {"status": document.status},
            )
        return document, user

    async def _reload(self, document: Document, user: User) -> None:
        """updated_at cambia en la base al guardar; se recarga antes de responder."""
        await self.session.refresh(document)
        await self.session.refresh(user)

    @staticmethod
    def _snapshot(document: Document, user: User) -> dict[str, Any]:
        return {
            "status": document.status.value,
            "rejection_reason": document.rejection_reason,
            "user_status": user.status.value,
            "user_sex": user.sex.value,
        }

    async def approve(self, approval_id: uuid.UUID, actor: Actor, sex: Sex | None) -> ApprovalItem:
        document, user = await self._reviewable(approval_id, actor)
        if document.is_license and (
            document.expires_on is None or document.expires_on < local_today()
        ):
            raise AppError("LICENSE_EXPIRED", "The license is already expired", 422)
        before = self._snapshot(document, user)
        document.status = ReviewStatus.APPROVED
        document.reviewed_by = actor.user.id
        document.reviewed_at = utcnow()
        document.rejection_reason = None

        if document.is_license:
            self.notifications.notify(
                user.id, Kind.LICENSE_APPROVED, {"license_id": str(document.id)}
            )
            action = "driver_license.approve"
        else:
            if sex is not None and sex != user.sex:
                user.sex = sex
            if document.semester_id is None:
                current = await SemesterRepository(self.session).containing(local_today())
                document.semester_id = current.id if current else None
            if user.status == UserStatus.PENDING_APPROVAL:
                user.status = UserStatus.ACTIVE
            self.notifications.notify(
                user.id, Kind.DOCUMENT_APPROVED, {"document_id": str(document.id)}
            )
            action = "identity_document.approve"

        self.audit.record(
            actor, action, "document", document.id, before, self._snapshot(document, user)
        )
        await self.session.commit()
        await self._reload(document, user)
        return await self._item(document, user)

    async def reject(self, approval_id: uuid.UUID, actor: Actor, reason: str) -> ApprovalItem:
        document, user = await self._reviewable(approval_id, actor)
        before = self._snapshot(document, user)
        document.status = ReviewStatus.REJECTED
        document.reviewed_by = actor.user.id
        document.reviewed_at = utcnow()
        document.rejection_reason = reason
        self.notifications.notify(
            user.id,
            Kind.LICENSE_REJECTED if document.is_license else Kind.DOCUMENT_REJECTED,
            {"reason": reason},
        )
        self.audit.record(
            actor,
            "driver_license.reject" if document.is_license else "identity_document.reject",
            "document",
            document.id,
            before,
            self._snapshot(document, user),
        )
        await self.session.commit()
        await self._reload(document, user)
        return await self._item(document, user)
