import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints

from app.core.enums import DocKind, ReviewStatus, Sex, UserRole, UserStatus

ApprovalType = Literal["identity", "license"]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]


class Applicant(BaseModel):
    """Lo que el revisor necesita para comparar con el documento. Sin correo ni telefono."""

    id: uuid.UUID
    full_name: str
    program: str | None
    role: UserRole
    sex: Sex
    status: UserStatus


class ApprovalItem(BaseModel):
    id: uuid.UUID
    type: ApprovalType
    doc_kind: DocKind | None
    status: ReviewStatus
    submitted_at: datetime
    reviewed_at: datetime | None
    rejection_reason: str | None
    semester: str | None
    license_expires_on: date | None
    applicant: Applicant


class ApprovalCounts(BaseModel):
    identity: int
    license: int


class ApproveRequest(BaseModel):
    """sex: correccion del sexo si el documento muestra otro distinto al declarado."""

    sex: Sex | None = None


class RejectRequest(BaseModel):
    reason: Reason


class AdminCreate(BaseModel):
    email: EmailStr
    full_name: PersonName
    sex: Sex
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class RoleChange(BaseModel):
    role: Literal[UserRole.PASSENGER, UserRole.DRIVER, UserRole.ADMIN]


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    status: UserStatus
