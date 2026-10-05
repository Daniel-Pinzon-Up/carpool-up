"""Administradores y roles. Solo el superadmin; todo queda en la auditoria."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.config import get_settings
from app.core.enums import UserRole, UserStatus
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.modules.admin.schemas import AdminCreate, AdminUserOut
from app.modules.audit.service import AuditService
from app.modules.notifications.service import Kind, NotificationService
from app.modules.settings.service import SettingsService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


def _out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role, status=user.status
    )


class AccountAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    async def create_admin(self, data: AdminCreate, actor: Actor) -> AdminUserOut:
        """El administrador entra con la clave inicial y debe confirmar un codigo por correo."""
        email = data.email.lower()
        suffix = get_settings().allowed_email_suffix.lower()
        if not email.endswith(suffix):
            raise AppError(
                "EMAIL_NOT_INSTITUTIONAL", "Use an institutional email", 422, {"suffix": suffix}
            )
        minimum = int(await SettingsService(self.session).get("password_min_length"))
        if len(data.password) < minimum:
            raise AppError(
                "PASSWORD_TOO_SHORT", "Password is too short", 422, {"min_length": minimum}
            )
        if await self.users.email_exists(email):
            raise AppError("EMAIL_TAKEN", "There is already an account with this email", 409)
        user = User(
            email=email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            sex=data.sex,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            two_factor_required=True,
        )
        self.users.add(user)
        await self.session.flush()
        self.audit.record(
            actor,
            "admin.create",
            "user",
            user.id,
            None,
            {"role": UserRole.ADMIN.value, "full_name": user.full_name},
        )
        await self.session.commit()
        return _out(user)

    async def change_role(self, user_id: uuid.UUID, role: UserRole, actor: Actor) -> AdminUserOut:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("user")
        if user.id == actor.user.id:
            raise ForbiddenError("You cannot change your own role")
        if user.role == UserRole.SUPERADMIN:
            raise ForbiddenError("The superadmin role cannot be changed")
        if user.role == role:
            return _out(user)
        before = {"role": user.role.value}
        user.role = role
        if role != UserRole.DRIVER:
            user.payment_note = None  # solo los conductores la usan
        self.audit.record(actor, "user.role_change", "user", user.id, before, {"role": role.value})
        NotificationService(self.session).notify(user.id, Kind.ROLE_CHANGED, {"role": role.value})
        await self.session.commit()
        return _out(user)
