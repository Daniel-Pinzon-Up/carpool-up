import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.core.enums import DocKind, Language, Sex, UserRole
from app.modules.users.schemas import MeOut

Code = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]
Password = Annotated[str, StringConstraints(min_length=1, max_length=128)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
Program = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
DeviceLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class RegisterForm(BaseModel):
    """Campos del registro. El documento llega aparte como archivo (multipart)."""

    email: EmailStr
    password: Password
    full_name: PersonName
    sex: Sex
    program: Program | None = None
    role: Literal[UserRole.PASSENGER, UserRole.DRIVER]
    doc_kind: DocKind
    preferred_language: Language = Language.ES
    accept_terms: bool
    accept_data_policy: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: Password
    device_label: DeviceLabel | None = None


class CodeVerifyRequest(BaseModel):
    challenge_id: str = Field(max_length=2000)
    code: Code
    device_label: DeviceLabel | None = None


class ResendRequest(BaseModel):
    challenge_id: str = Field(max_length=2000)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    challenge_id: str = Field(max_length=2000)
    code: Code
    new_password: Password


AuthResultKind = Literal[
    "authenticated",
    "email_verification_required",
    "two_factor_required",
    "password_reset_code_sent",
]


class AuthResult(BaseModel):
    """Respuesta comun de los pasos de autenticacion.

    authenticated trae el token de acceso (el refresh va en una cookie HttpOnly).
    Los demas resultados traen challenge_id para enviar el codigo que llego al correo.
    """

    result: AuthResultKind
    access_token: str | None = None
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - esquema OAuth, no un secreto
    expires_in: int | None = None
    user: MeOut | None = None
    challenge_id: str | None = None
    email_hint: str | None = None
    resend_after_seconds: int | None = None


class ResendResult(BaseModel):
    resend_after_seconds: int


class SessionOut(BaseModel):
    id: uuid.UUID
    device_label: str
    ip: str | None
    created_at: datetime
    last_seen_at: datetime
    current: bool


class RevokedSessions(BaseModel):
    revoked: int
