import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.core.enums import (
    BookingStatus,
    DocKind,
    ReviewStatus,
    Sex,
    TripStatus,
    UserRole,
    UserStatus,
)
from app.modules.safety.schemas import EmergencyOut

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


# --- Usuarios (paso 12) -----------------------------------------------------------------


class AdminUserRow(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    status: UserStatus
    program: str | None
    created_at: datetime
    last_login_at: datetime | None


class AdminUserDetail(AdminUserRow):
    sex: Sex
    document_status: ReviewStatus | None
    license_status: ReviewStatus | None
    license_expires_on: date | None
    rating: float | None
    rating_count: int
    trips_as_driver: int
    trips_as_passenger: int
    driver_cancellations: int
    passenger_no_shows: int
    active_bookings: int
    upcoming_trips: int
    suspended_until: datetime | None = Field(
        description="Fin de la suspension de la cuenta (nulo: hasta que la reactiven)"
    )
    suspension_reason: str | None
    booking_ban_until: datetime | None = Field(
        description="Reservas suspendidas por ausencias hasta esta fecha"
    )


class SuspendRequest(BaseModel):
    reason: Reason
    days: Annotated[int, Field(ge=1, le=365)] | None = Field(
        default=None, description="Sin dias: hasta que un administrador la reactive"
    )


class ReasonRequest(BaseModel):
    reason: Reason


class OptionalReason(BaseModel):
    reason: Reason | None = None


# --- Viajes y moderacion ----------------------------------------------------------------


class AdminTripRow(BaseModel):
    id: uuid.UUID

    status: TripStatus
    departs_at: datetime
    origin: str
    destination: str
    driver_id: uuid.UUID
    driver_name: str
    seats_total: int
    seats_booked: int
    open_emergencies: int
    deleted: bool


class AdminBooking(BaseModel):
    id: uuid.UUID
    passenger_id: uuid.UUID
    passenger_name: str
    status: BookingStatus
    seats: int
    boarded_at: datetime | None
    created_at: datetime


class AdminTripDetail(AdminTripRow):
    vehicle: str
    plate: str
    price_per_seat: int
    started_at: datetime | None
    finished_at: datetime | None
    cancel_reason: str | None
    bookings: list[AdminBooking]
    emergencies: list[EmergencyOut]
    has_chat: bool


class AdminMessage(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    body: str
    sent_at: datetime
    hidden: bool


class AdminRating(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    author_name: str
    target_name: str
    target_role: str
    average: float
    comment: str | None
    hidden: bool
    created_at: datetime


class HiddenRequest(BaseModel):
    hidden: bool


# --- Panel -----------------------------------------------------------------------------


class CountItem(BaseModel):
    key: str = Field(description="rol:estado")
    count: int


class DayCount(BaseModel):
    day: str
    count: int


class RouteCount(BaseModel):
    origin: str
    destination: str
    count: int


class AdminOverview(BaseModel):
    days: int
    users: list[CountItem]
    trips_completed: int
    trips_per_day: list[DayCount]
    trips_per_hour: list[int] = Field(description="24 valores, hora local de salida")
    occupancy: float | None
    driver_cancellations: int
    passenger_cancellations: int
    no_shows: int
    top_routes: list[RouteCount]
    rating_distribution: list[int] = Field(description="Calificaciones de 1 a 5 estrellas")
    pending_approvals: int
    open_emergencies: int
