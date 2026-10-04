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


class LegalKind(StrEnum):
    TERMS = "terms"
    DATA_POLICY = "data_policy"


class Language(StrEnum):
    ES = "es"
    EN = "en"
    PT = "pt"
    FR = "fr"


class ThemePreference(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


ADMIN_ROLES = frozenset({UserRole.ADMIN, UserRole.SUPERADMIN})
