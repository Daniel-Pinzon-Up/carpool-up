import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.enums import (
    DocKind,
    Language,
    LegalKind,
    ReviewStatus,
    Sex,
    ThemePreference,
    UserRole,
    UserStatus,
)


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: DocKind
    status: ReviewStatus
    rejection_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class LicenseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ReviewStatus
    expires_on: date
    rejection_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class PendingLegal(BaseModel):
    id: uuid.UUID
    kind: LegalKind
    version: str
    language: Language


class MeOut(BaseModel):
    """Perfil propio. Es el unico lugar donde se devuelve el correo del usuario."""

    id: uuid.UUID
    email: str
    full_name: str
    sex: Sex
    program: str | None
    role: UserRole
    status: UserStatus
    payment_note: str | None
    preferred_language: Language
    theme_preference: ThemePreference
    last_login_at: datetime | None
    document: DocumentSummary | None
    license: LicenseSummary | None
    can_publish: bool
    pending_legal: list[PendingLegal]


Program = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
PaymentNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class MeUpdate(BaseModel):
    """Lo que el usuario puede cambiar. Nombre, sexo y rol los valida un administrador."""

    program: Program | None = None
    preferred_language: Language | None = None
    theme_preference: ThemePreference | None = None
    payment_note: PaymentNote | None = None
