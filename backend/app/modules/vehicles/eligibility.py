"""Requisitos para publicar viajes (seccion 7.2). Unico lugar donde se decide."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.enums import ReviewStatus, UserRole, UserStatus
from app.core.errors import AppError
from app.modules.documents.service import LicenseService
from app.modules.users.models import User
from app.modules.vehicles.service import VehicleService


async def publishing_blockers(session: AsyncSession, user: User) -> list[str]:
    """Lista vacia si puede publicar; si no, los motivos en orden de prioridad."""
    if user.role != UserRole.DRIVER:
        return ["not_driver"]
    blockers: list[str] = []
    if user.status != UserStatus.ACTIVE:
        blockers.append("account_not_active")
    license_ = await LicenseService(session).get(user)
    if license_ is None:
        blockers.append("license_missing")
    elif license_.status == ReviewStatus.PENDING:
        blockers.append("license_pending")
    elif license_.status == ReviewStatus.REJECTED:
        blockers.append("license_rejected")
    elif not license_.is_valid_on(local_today()):
        blockers.append("license_expired")
    if not await VehicleService(session).has_active(user.id):
        blockers.append("no_active_vehicle")
    return blockers


async def require_can_publish(session: AsyncSession, user: User) -> None:
    blockers = await publishing_blockers(session, user)
    if blockers:
        raise AppError(
            "PUBLISH_NOT_ALLOWED", "You cannot publish trips yet", 403, {"blockers": blockers}
        )
