"""Contrasenas con argon2id y tokens de acceso JWT de corta duracion."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.enums import UserRole

_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - tipo de token, no un secreto


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: UserRole


def create_access_token(user_id: uuid.UUID, role: UserRole) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessClaims | None:
    """Devuelve las claims si el token es valido y de tipo acceso; None en cualquier otro caso."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None
        return AccessClaims(user_id=uuid.UUID(payload["sub"]), role=UserRole(payload["role"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
