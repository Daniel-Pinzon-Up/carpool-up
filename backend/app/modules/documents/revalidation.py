"""Revalidacion semestral del carnet o constancia (seccion 7.1).

1. Cuando hay un semestre vigente, los documentos aprobados de otros semestres vencen y se
   avisa a sus duenos para que suban el nuevo.
2. Pasado el plazo de revalidacion, las cuentas activas sin documento aprobado del semestre
   vigente vuelven a pending_approval hasta que se apruebe uno nuevo.

Administradores y superadmin no revalidan: sus cuentas las gestiona el superadmin.
"""

from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewStatus, UserRole, UserStatus
from app.modules.audit.service import AuditService
from app.modules.documents.models import IdentityDocument
from app.modules.notifications.service import Kind, NotificationService
from app.modules.semesters.repository import SemesterRepository
from app.modules.users.models import User

logger = structlog.get_logger("revalidation")
REVALIDATED_ROLES = (UserRole.PASSENGER, UserRole.DRIVER)


@dataclass(frozen=True)
class RevalidationResult:
    expired_documents: int
    downgraded_users: int


async def run_revalidation(session: AsyncSession, today: date) -> RevalidationResult:
    """Idempotente: se puede correr varias veces al dia."""
    semester = await SemesterRepository(session).containing(today)
    if semester is None:
        logger.info("revalidation_skipped", reason="sin semestre vigente")
        return RevalidationResult(0, 0)

    notifications = NotificationService(session)

    expired_rows = await session.execute(
        update(IdentityDocument)
        .where(
            IdentityDocument.status == ReviewStatus.APPROVED,
            or_(
                IdentityDocument.semester_id.is_(None),
                IdentityDocument.semester_id != semester.id,
            ),
        )
        .values(status=ReviewStatus.EXPIRED)
        .returning(IdentityDocument.user_id, IdentityDocument.id)
    )
    expired = [(row.user_id, row.id) for row in expired_rows.all()]
    for user_id, document_id in expired:
        notifications.notify(
            user_id,
            Kind.DOCUMENT_EXPIRED,
            {
                "document_id": str(document_id),
                "semester": semester.name,
                "deadline": semester.revalidation_deadline.isoformat(),
            },
        )

    downgraded: list[User] = []
    if today > semester.revalidation_deadline:
        has_current_document = exists().where(
            IdentityDocument.user_id == User.id,
            IdentityDocument.status == ReviewStatus.APPROVED,
            IdentityDocument.semester_id == semester.id,
        )
        query = select(User).where(
            User.status == UserStatus.ACTIVE,
            User.role.in_(REVALIDATED_ROLES),
            User.deleted_at.is_(None),
            ~has_current_document,
        )
        downgraded = list((await session.scalars(query)).all())
        audit = AuditService(session)
        for user in downgraded:
            user.status = UserStatus.PENDING_APPROVAL
            notifications.notify(
                user.id, Kind.ACCOUNT_REVALIDATION_REQUIRED, {"semester": semester.name}
            )
            audit.record(
                None,
                "user.revalidation_downgrade",
                "user",
                user.id,
                {"status": UserStatus.ACTIVE.value},
                {"status": UserStatus.PENDING_APPROVAL.value},
            )

    await session.commit()
    result = RevalidationResult(len(expired), len(downgraded))
    logger.info(
        "revalidation_done",
        semester=semester.name,
        expired_documents=result.expired_documents,
        downgraded_users=result.downgraded_users,
    )
    return result
