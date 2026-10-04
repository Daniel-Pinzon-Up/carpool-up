import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import VehicleType

Weekday = Annotated[int, Field(ge=0, le=6, description="0 = lunes ... 6 = domingo")]
Digits = Annotated[list[Annotated[int, Field(ge=0, le=9)]], Field(min_length=1, max_length=10)]


def _normalize_digits(digits: list[int] | None) -> list[int] | None:
    if digits is None:
        return None
    if len(set(digits)) != len(digits):
        raise ValueError("digits must not repeat")
    return sorted(digits)


class PicoPlacaRuleCreate(BaseModel):
    vehicle_type: VehicleType
    weekday: Weekday
    restricted_digits: Digits
    valid_from: date
    valid_to: date | None = None
    is_active: bool = True

    _digits = field_validator("restricted_digits")(_normalize_digits)

    @model_validator(mode="after")
    def check_validity(self) -> "PicoPlacaRuleCreate":
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be before valid_from")
        return self


class PicoPlacaRuleUpdate(BaseModel):
    vehicle_type: VehicleType | None = None
    weekday: Weekday | None = None
    restricted_digits: Digits | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool | None = None

    _digits = field_validator("restricted_digits")(_normalize_digits)


class PicoPlacaRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_type: VehicleType
    weekday: int
    restricted_digits: list[int]
    valid_from: date
    valid_to: date | None
    is_active: bool
