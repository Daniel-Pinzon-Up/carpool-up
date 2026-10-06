import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.ratings.models import MAX_COMMENT

Stars = Annotated[int, Field(ge=1, le=5)]


class RatingIn(BaseModel):
    target_id: uuid.UUID
    scores: dict[str, Stars] = Field(
        description="Estrellas por criterio. Conductor: punctuality, safe_driving, courtesy, "
        "cleanliness. Pasajero: punctuality, courtesy, compliance."
    )
    comment: Annotated[str, Field(max_length=MAX_COMMENT)] | None = None

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class RatingOut(BaseModel):
    """Sin el autor: quien recibe ve que le calificaron, no quien."""

    id: uuid.UUID
    trip_id: uuid.UUID
    target_role: Literal["driver", "passenger"]
    scores: dict[str, int]
    average: float
    comment: str | None = Field(description="Nulo si un administrador lo oculto")
    hidden: bool
    created_at: datetime


class PendingRating(BaseModel):
    trip_id: uuid.UUID
    departs_at: datetime
    origin: str
    destination: str
    target_id: uuid.UUID
    target_name: str
    target_role: Literal["driver", "passenger"]
    criteria: list[str]
    closes_at: datetime


class RatingSummary(BaseModel):
    """Lo publico de la reputacion de alguien."""

    user_id: uuid.UUID
    full_name: str
    average: float | None
    count: int
    criteria: dict[str, float]
    trips_as_driver: int
    trips_as_passenger: int
