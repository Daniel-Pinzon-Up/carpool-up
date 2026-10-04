"""Contrasenas con argon2id, tokens JWT y secretos de un solo uso."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.enums import AuthPurpose, UserRole

_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - tipo de token, no un secreto
CHALLENGE_TOKEN_TYPE = "challenge"  # noqa: S105 - tipo de token, no un secreto
CODE_DIGITS = 6

# Hash fijo para comparar cuando el correo no existe y igualar el tiempo de respuesta.
DUMMY_PASSWORD_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _encode(payload: dict[str, object]) -> str:
    return jwt.encode(payload, get_settings().secret_key, algorithm=JWT_ALGORITHM)


def _decode(token: str, token_type: str) -> dict[str, object] | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == token_type else None


# --- Token de acceso ---------------------------------------------------------------------


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: UserRole
    session_id: uuid.UUID | None


def create_access_token(
    user_id: uuid.UUID, role: UserRole, session_id: uuid.UUID | None = None
) -> str:
    """session_id liga el token a una sesion: al revocarla el token deja de servir."""
    now = utcnow()
    payload: dict[str, object] = {
        "sub": str(user_id),
        "role": role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().access_token_minutes),
    }
    if session_id is not None:
        payload["sid"] = str(session_id)
    return _encode(payload)


def decode_access_token(token: str) -> AccessClaims | None:
    """Claims si el token es valido y de tipo acceso; None en cualquier otro caso."""
    payload = _decode(token, ACCESS_TOKEN_TYPE)
    if payload is None:
        return None
    try:
        sid = payload.get("sid")
        return AccessClaims(
            user_id=uuid.UUID(str(payload["sub"])),
            role=UserRole(str(payload["role"])),
            session_id=uuid.UUID(str(sid)) if sid else None,
        )
    except (KeyError, ValueError):
        return None


# --- Token de desafio (verificacion por codigo) --------------------------------------------


@dataclass(frozen=True)
class Challenge:
    user_id: uuid.UUID
    purpose: AuthPurpose


def create_challenge_token(user_id: uuid.UUID, purpose: AuthPurpose, minutes: int) -> str:
    """Identifica a quien se le envio un codigo sin exponer su correo."""
    now = utcnow()
    return _encode(
        {
            "sub": str(user_id),
            "purpose": purpose.value,
            "type": CHALLENGE_TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
        }
    )


def decode_challenge_token(token: str, purpose: AuthPurpose) -> Challenge | None:
    payload = _decode(token, CHALLENGE_TOKEN_TYPE)
    if payload is None or payload.get("purpose") != purpose.value:
        return None
    try:
        return Challenge(user_id=uuid.UUID(str(payload["sub"])), purpose=purpose)
    except (KeyError, ValueError):
        return None


# --- Refresh token -----------------------------------------------------------------------


def new_refresh_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def build_refresh_token(session_id: uuid.UUID, secret: str) -> str:
    return f"{session_id}.{secret}"


def parse_refresh_token(token: str) -> tuple[uuid.UUID, str] | None:
    session_part, _, secret = token.partition(".")
    if not secret:
        return None
    try:
        return uuid.UUID(session_part), secret
    except ValueError:
        return None


def secrets_match(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), expected_hash)


# --- Codigos de un solo uso ----------------------------------------------------------------


def new_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(user_id: uuid.UUID, purpose: AuthPurpose, code: str) -> str:
    """HMAC con la clave del servidor: un volcado de la base no permite probar codigos."""
    message = f"{purpose.value}:{user_id}:{code}".encode()
    return hmac.new(get_settings().secret_key.encode(), message, hashlib.sha256).hexdigest()


def code_matches(user_id: uuid.UUID, purpose: AuthPurpose, code: str, expected: str) -> bool:
    return hmac.compare_digest(hash_code(user_id, purpose, code), expected)
