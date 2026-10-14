"""Permisos por rol en los endpoints del superadmin y validacion del token de acceso."""

from datetime import timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.enums import UserRole, UserStatus
from app.core.security import JWT_ALGORITHM, decode_access_token, hash_password, verify_password
from tests.conftest import API, UserFactory, auth

pytestmark = pytest.mark.integration

ADMIN_ENDPOINTS = [
    ("GET", "/admin/settings"),
    ("PATCH", "/admin/settings/cancel_free_hours"),
    ("GET", "/admin/semesters"),
    ("POST", "/admin/semesters"),
    ("GET", "/admin/places"),
    ("POST", "/admin/places"),
    ("GET", "/admin/pico-placa"),
    ("POST", "/admin/pico-placa"),
    ("GET", "/admin/audit"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_admin_endpoints_require_token(api: AsyncClient, method: str, path: str) -> None:
    response = await api.request(method, f"{API}{path}", json={})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("role", [UserRole.PASSENGER, UserRole.DRIVER, UserRole.ADMIN])
@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_only_superadmin_reaches_configuration(
    api: AsyncClient, make_user: UserFactory, role: UserRole, method: str, path: str
) -> None:
    user = await make_user(role)
    response = await api.request(method, f"{API}{path}", json={}, headers=auth(user))
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_inactive_superadmin_is_rejected(api: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(UserRole.SUPERADMIN, UserStatus.SUSPENDED)
    response = await api.get(f"{API}/admin/settings", headers=auth(user))
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_NOT_ACTIVE"


async def test_blocked_user_token_is_rejected(api: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(UserRole.SUPERADMIN, UserStatus.BLOCKED)
    response = await api.get(f"{API}/admin/settings", headers=auth(user))
    assert response.status_code == 401


async def test_token_of_deleted_user_is_rejected(api: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(UserRole.SUPERADMIN)
    user.deleted_at = utcnow()
    response = await api.get(f"{API}/admin/settings", headers=auth(user))
    assert response.status_code == 401


async def test_malformed_and_expired_tokens_are_rejected(
    api: AsyncClient, make_user: UserFactory
) -> None:
    user = await make_user(UserRole.SUPERADMIN)
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "role": "superadmin",
            "type": "access",
            "exp": utcnow() - timedelta(minutes=1),
        },
        get_settings().secret_key,
        algorithm=JWT_ALGORITHM,
    )
    forged = jwt.encode(
        {
            "sub": str(user.id),
            "role": "superadmin",
            "type": "access",
            "exp": utcnow() + timedelta(minutes=5),
        },
        "otra-clave-secreta-distinta-de-32-bytes-o-mas",
        algorithm=JWT_ALGORITHM,
    )
    for token in ("basura", expired, forged):
        response = await api.get(
            f"{API}/admin/settings", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401, token


def test_refresh_type_tokens_are_not_access_tokens() -> None:
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "role": "passenger",
            "type": "refresh",
            "exp": utcnow() + timedelta(minutes=5),
        },
        get_settings().secret_key,
        algorithm=JWT_ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_password_hashing_uses_argon2id() -> None:
    hashed = hash_password("una-clave-larga-123")
    assert hashed.startswith("$argon2id$")
    assert verify_password("una-clave-larga-123", hashed)
    assert not verify_password("otra-clave", hashed)
    assert not verify_password("x", "no-es-un-hash")
