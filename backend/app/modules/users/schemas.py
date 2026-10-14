import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.enums import DocKind, ReviewStatus, Sex, UserRole, UserStatus


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
    expires_on: date | None
    rejection_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


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
    last_login_at: datetime | None
    document: DocumentSummary | None
    license: LicenseSummary | None
    can_publish: bool
    # Motivos por los que un conductor aun no puede publicar (vacio si puede).
    publish_blockers: list[str]
    # Reservas suspendidas por ausencias hasta esta fecha (nulo si puede reservar).
    booking_ban_until: datetime | None


Program = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
PaymentNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class AccountDeleteRequest(BaseModel):
    """La contrasena confirma que quien pide borrar la cuenta es su duena."""

    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class MeUpdate(BaseModel):
    """Lo que el usuario puede cambiar. Nombre, sexo y rol los valida un administrador."""

    program: Program | None = None
    payment_note: PaymentNote | None = None
