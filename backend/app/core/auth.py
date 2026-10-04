"""Dependencias de autenticacion y autorizacion por rol.

El login y la emision de tokens llegan en el paso 2; aqui solo se valida el token de acceso.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.deps import DbSession
from app.core.enums import UserRole, UserStatus
from app.core.errors import AppError, ForbiddenError
from app.core.security import decode_access_token
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)


class UnauthorizedError(AppError):
    def __init__(self) -> None:
        super().__init__("UNAUTHORIZED", "Authentication required", 401)


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise UnauthorizedError()
    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise UnauthorizedError()
    user = await session.get(User, claims.user_id)
    if user is None or user.deleted_at is not None or user.status == UserStatus.BLOCKED:
        raise UnauthorizedError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_active_user(user: CurrentUser) -> User:
    if user.status != UserStatus.ACTIVE:
        raise AppError("ACCOUNT_NOT_ACTIVE", "Account is not active", 403, {"status": user.status})
    return user


ActiveUser = Annotated[User, Depends(get_active_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependencia que exige una cuenta activa con alguno de los roles dados."""
    allowed = frozenset(roles)

    async def dependency(user: ActiveUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Role not allowed")
        return user

    return dependency


SuperAdmin = Annotated[User, Depends(require_roles(UserRole.SUPERADMIN))]
AdminOrSuper = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))]


@dataclass(frozen=True)
class Actor:
    """Quien hace una operacion sensible y desde donde, para la auditoria."""

    user: User
    ip: str | None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def get_superadmin_actor(user: SuperAdmin, request: Request) -> Actor:
    return Actor(user=user, ip=client_ip(request))


SuperAdminActor = Annotated[Actor, Depends(get_superadmin_actor)]
