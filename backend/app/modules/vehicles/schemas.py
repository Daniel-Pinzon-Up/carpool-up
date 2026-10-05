import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.clock import local_today
from app.core.enums import VehicleType

# Placas colombianas: carro ABC123, moto ABC12D. Se ignoran espacios y guiones al escribirlas.
PLATE_PATTERNS = {
    VehicleType.CAR: re.compile(r"^[A-Z]{3}\d{3}$"),
    VehicleType.MOTORCYCLE: re.compile(r"^[A-Z]{3}\d{2}[A-Z]$"),
}
CAPACITY = {VehicleType.CAR: (2, 8), VehicleType.MOTORCYCLE: (2, 2)}
MIN_YEAR = 1980

Text40 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=40)]


def normalize_plate(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


def check_vehicle(vehicle_type: VehicleType, plate: str, capacity: int, year: int) -> None:
    """Reglas que dependen del tipo. Lanza ValueError con un mensaje estable."""
    if not PLATE_PATTERNS[vehicle_type].match(plate):
        raise ValueError(f"plate_format_{vehicle_type.value}")
    low, high = CAPACITY[vehicle_type]
    if not low <= capacity <= high:
        raise ValueError(f"capacity_{vehicle_type.value}")
    if not MIN_YEAR <= year <= local_today().year + 1:
        raise ValueError("year_range")


class VehicleCreate(BaseModel):
    type: VehicleType
    plate: Annotated[str, StringConstraints(max_length=10)]
    brand: Text40
    model: Text40
    color: Text40
    year: int
    capacity: int = Field(description="Puestos totales incluido el conductor")
    luggage_space: bool = False

    _plate = field_validator("plate")(normalize_plate)

    @model_validator(mode="after")
    def by_type(self) -> "VehicleCreate":
        check_vehicle(self.type, self.plate, self.capacity, self.year)
        return self


class VehicleUpdate(BaseModel):
    """El tipo y la placa no cambian: si cambian, es otro vehiculo."""

    brand: Text40 | None = None
    model: Text40 | None = None
    color: Text40 | None = None
    year: int | None = None
    capacity: int | None = None
    luggage_space: bool | None = None
    is_active: bool | None = None


class VehicleOut(BaseModel):
    """Vista del propio conductor (incluye la placa)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: VehicleType
    plate: str
    brand: str
    model: str
    color: str
    year: int
    capacity: int
    luggage_space: bool
    is_active: bool
    has_photo: bool
    created_at: datetime
