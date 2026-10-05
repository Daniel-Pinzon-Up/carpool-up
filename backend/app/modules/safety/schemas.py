import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import StopKind, TripStatus, VehicleType

Name = Annotated[str, Field(min_length=2, max_length=80)]
Phone = Annotated[str, Field(min_length=7, max_length=20)]
Relation = Annotated[str, Field(max_length=40)]
PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")


def _phone(value: str) -> str:
    """Solo digitos y un + inicial; se quitan espacios, guiones y parentesis."""
    cleaned = re.sub(r"[\s\-().]", "", value)
    if not PHONE_PATTERN.match(cleaned):
        raise ValueError("phone must have 7 to 15 digits")
    return cleaned


class ContactIn(BaseModel):
    name: Name
    phone: Phone
    relationship: Relation | None = None

    _phone = field_validator("phone")(_phone)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class ContactUpdate(BaseModel):
    name: Name | None = None
    phone: Phone | None = None
    relationship: Relation | None = None

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        return _phone(value) if value is not None else None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    relationship: str | None = Field(validation_alias="relation")


class ShareLinkOut(BaseModel):
    token: str = Field(description="Se muestra una sola vez: solo se guarda su hash")
    path: str = Field(description="Ruta publica de la app: /compartido/{token}")
    expires_at: datetime


class LiveLocation(BaseModel):
    lat: float
    lon: float
    accuracy: float | None = None
    heading: float | None = None
    speed: float | None = None
    at: datetime


class PublicVehicle(BaseModel):
    type: VehicleType
    brand: str
    model: str
    color: str
    plate: str


class PublicStop(BaseModel):
    name: str
    lat: float
    lon: float
    kind: StopKind


class PublicTrip(BaseModel):
    """Vista del enlace compartido: sin nombres, correos ni telefonos."""

    status: TripStatus
    departs_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    arrives_at: datetime
    geometry: list[list[float]]
    stops: list[PublicStop]
    vehicle: PublicVehicle
    location: LiveLocation | None
    expires_at: datetime


class EmergencyIn(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    note: Annotated[str, Field(max_length=500)] | None = None


class EmergencyOut(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    trip_status: TripStatus
    route: str
    user_id: uuid.UUID
    user_name: str
    lat: float | None
    lon: float | None
    note: str | None
    created_at: datetime
    handled_at: datetime | None
    resolution: str | None


class EmergencyReport(BaseModel):
    """Respuesta al usuario: el evento y la linea de emergencias a la que debe llamar."""

    emergency: EmergencyOut
    phone: str


class HandleIn(BaseModel):
    resolution: Annotated[str, Field(min_length=5, max_length=500)]
