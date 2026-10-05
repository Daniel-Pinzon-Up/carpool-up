"""Cola de aprobacion de carnets, constancias y licencias (administrador y superadmin)."""

import uuid
from typing import Any, cast

from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import local_today, utcnow
from app.core.enums import ReviewStatus, Sex, UserStatus
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.core.storage import private_file_response
from app.modules.admin.schemas import Applicant, ApprovalCounts, ApprovalItem, ApprovalType
from app.modules.audit.service import AuditService
from app.modules.documents.models import DriverLicense, IdentityDocument
from app.modules.notifications.service import Kind, NotificationService
from app.modules.semesters.models import Semester
from app.modules.semesters.repository import SemesterRepository
from app.modules.users.models import User

Reviewable = IdentityDocument | DriverLicense
MODELS: dict[ApprovalType, type[IdentityDocument] | type[DriverLicense]] = {
    "identity": IdentityDocument,
    "license": DriverLicense,
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

    async def _item(self, record: Reviewable, user: User) -> ApprovalItem:
        if isinstance(record, IdentityDocument):
            semester = (
                await self.session.get(Semester, record.semester_id) if record.semester_id else None
            )
            return ApprovalItem(
                id=record.id,
                type="identity",
                doc_kind=record.kind,
                status=record.status,
                submitted_at=record.updated_at,
                reviewed_at=record.reviewed_at,
                rejection_reason=record.rejection_reason,
                semester=semester.name if semester else None,
                license_expires_on=None,
                applicant=_applicant(user),
            )
        return ApprovalItem(
            id=record.id,
            type="license",
            doc_kind=None,
            status=record.status,
            submitted_at=record.updated_at,
            reviewed_at=record.reviewed_at,
            rejection_reason=record.rejection_reason,
            semester=None,
            license_expires_on=record.expires_on,
            applicant=_applicant(user),
        )

    async def queue(
        self, kind: ApprovalType, status: ReviewStatus, limit: int, cursor: str | None
    ) -> Page[ApprovalItem]:
        """Mas antiguos primero: se atiende en orden de llegada."""
        model = MODELS[kind]
        query = (
            select(model, User)
            .join(User, User.id == model.user_id)
            .where(model.status == status, User.deleted_at.is_(None))
        )
        if cursor:
            after_at, after_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    model.updated_at > after_at,
                    and_(model.updated_at == after_at, model.id > after_id),
                )
            )
        query = query.order_by(model.updated_at, model.id).limit(limit + 1)
        # La consulta depende del modelo elegido; mypy no puede inferir el tipo de la fila.
        rows = [
            (cast(Reviewable, record), user)
            for record, user in (await self.session.execute(query)).all()
        ]
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [await self._item(record, user) for record, user in rows]
        last = rows[-1][0] if rows else None
        return Page(
            items=items,
            next_cursor=encode_cursor(last.updated_at, last.id) if has_more and last else None,
        )

    async def counts(self) -> ApprovalCounts:
        async def pending(model: type[IdentityDocument] | type[DriverLicense]) -> int:
            query = (
                select(func.count()).select_from(model).where(model.status == ReviewStatus.PENDING)
            )
            return int(await self.session.scalar(query) or 0)

        return ApprovalCounts(
            identity=await pending(IdentityDocument), license=await pending(DriverLicense)
        )

    async def _find(self, approval_id: uuid.UUID) -> tuple[Reviewable, User]:
        record: Reviewable | None = await self.session.get(IdentityDocument, approval_id)
        if record is None:
            record = await self.session.get(DriverLicense, approval_id)
        if record is None:
            raise NotFoundError("approval")
        user = await self.session.get(User, record.user_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundError("approval")
        return record, user

    async def detail(self, approval_id: uuid.UUID) -> ApprovalItem:
        record, user = await self._find(approval_id)
        return await self._item(record, user)

    async def file(self, approval_id: uuid.UUID) -> FileResponse:
        record, _ = await self._find(approval_id)
        return private_file_response(record.file_path, record.content_type)

    # --- Decisiones -------------------------------------------------------------------------

    async def _reviewable(self, approval_id: uuid.UUID, actor: Actor) -> tuple[Reviewable, User]:
        record, user = await self._find(approval_id)
        if user.id == actor.user.id:
            raise ForbiddenError("You cannot review your own documents")
        if record.status != ReviewStatus.PENDING:
            raise AppError(
                "APPROVAL_NOT_PENDING",
                "This item was already reviewed",
                409,
                {"status": record.status},
            )
        return record, user

    async def _reload(self, record: Reviewable, user: User) -> None:
        """updated_at cambia en la base al guardar; se recarga antes de responder."""
        await self.session.refresh(record)
        await self.session.refresh(user)

    @staticmethod
    def _snapshot(record: Reviewable, user: User) -> dict[str, Any]:
        return {
            "status": record.status.value,
            "rejection_reason": record.rejection_reason,
            "user_status": user.status.value,
            "user_sex": user.sex.value,
        }

    async def approve(self, approval_id: uuid.UUID, actor: Actor, sex: Sex | None) -> ApprovalItem:
        record, user = await self._reviewable(approval_id, actor)
        if isinstance(record, DriverLicense) and record.expires_on < local_today():
            raise AppError("LICENSE_EXPIRED", "The license is already expired", 422)
        before = self._snapshot(record, user)
        now = utcnow()
        record.status = ReviewStatus.APPROVED
        record.reviewed_by = actor.user.id
        record.reviewed_at = now
        record.rejection_reason = None

        if isinstance(record, IdentityDocument):
            if sex is not None and sex != user.sex:
                user.sex = sex
            if record.semester_id is None:
                current = await SemesterRepository(self.session).containing(local_today())
                record.semester_id = current.id if current else None
            semester = (
                await self.session.get(Semester, record.semester_id) if record.semester_id else None
            )
            record.valid_until = semester.ends_on if semester else None
            if user.status == UserStatus.PENDING_APPROVAL:
                user.status = UserStatus.ACTIVE
            self.notifications.notify(
                user.id, Kind.DOCUMENT_APPROVED, {"document_id": str(record.id)}
            )
            action = "identity_document.approve"
        else:
            self.notifications.notify(
                user.id, Kind.LICENSE_APPROVED, {"license_id": str(record.id)}
            )
            action = "driver_license.approve"

        self.audit.record(
            actor, action, record.__tablename__, record.id, before, self._snapshot(record, user)
        )
        await self.session.commit()
        await self._reload(record, user)
        return await self._item(record, user)

    async def reject(self, approval_id: uuid.UUID, actor: Actor, reason: str) -> ApprovalItem:
        record, user = await self._reviewable(approval_id, actor)
        before = self._snapshot(record, user)
        record.status = ReviewStatus.REJECTED
        record.reviewed_by = actor.user.id
        record.reviewed_at = utcnow()
        record.rejection_reason = reason
        is_identity = isinstance(record, IdentityDocument)
        self.notifications.notify(
            user.id,
            Kind.DOCUMENT_REJECTED if is_identity else Kind.LICENSE_REJECTED,
            {"reason": reason},
        )
        self.audit.record(
            actor,
            "identity_document.reject" if is_identity else "driver_license.reject",
            record.__tablename__,
            record.id,
            before,
            self._snapshot(record, user),
        )
        await self.session.commit()
        await self._reload(record, user)
        return await self._item(record, user)
