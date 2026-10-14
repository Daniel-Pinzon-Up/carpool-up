"""Enumeraciones del dominio (seccion 5.2 del plan). Se guardan como tipos enum de PostgreSQL."""

from enum import StrEnum


class UserRole(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class UserStatus(StrEnum):
    PENDING_EMAIL = "pending_email"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"


class VehicleType(StrEnum):
    CAR = "car"
    MOTORCYCLE = "motorcycle"


class PlaceKind(StrEnum):
    CAMPUS = "campus"
    SECTOR = "sector"
    LANDMARK = "landmark"
    CUSTOM = "custom"


ADMIN_ROLES = frozenset({UserRole.ADMIN, UserRole.SUPERADMIN})


class DocKind(StrEnum):
    STUDENT_CARD = "student_card"
    INSTITUTIONAL_PROOF = "institutional_proof"
    DRIVER_LICENSE = "driver_license"


# Documentos que acreditan a la persona ante la universidad (no la licencia).
IDENTITY_KINDS = (DocKind.STUDENT_CARD, DocKind.INSTITUTIONAL_PROOF)


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AuthPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    TWO_FACTOR = "two_factor"
    PASSWORD_RESET = "password_reset"  # noqa: S105 - proposito del codigo, no un secreto


class TripStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED_BY_DRIVER = "cancelled_by_driver"
    CANCELLED_PICO_PLACA = "cancelled_pico_placa"
    NOT_HELD = "not_held"


class StopKind(StrEnum):
    ORIGIN = "origin"
    STOP = "stop"
    DESTINATION = "destination"


class RuleKind(StrEnum):
    """Reglas del viaje. Se guardan en trips.rules (JSONB) como {"kind", "value"}."""

    WOMEN_ONLY = "women_only"
    PETS = "pets"
    LUGGAGE = "luggage"
    SMOKING = "smoking"
    MUSIC = "music"
    CUSTOM = "custom"


class BookingStatus(StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED_BY_PASSENGER = "cancelled_by_passenger"
    CANCELLED_BY_DRIVER = "cancelled_by_driver"
    AUTO_CANCELLED_LATE = "auto_cancelled_late"
    AUTO_CANCELLED_PICO_PLACA = "auto_cancelled_pico_placa"
    EXPIRED = "expired"
    NO_SHOW = "no_show"
    COMPLETED = "completed"
