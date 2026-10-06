import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import BookingStatus, TripStatus

RatingState = Literal["none", "pending", "done", "closed"]


class RatingBlock(BaseModel):
    average: float | None
    count: int
    criteria: dict[str, float]


class PlaceCount(BaseModel):
    name: str
    count: int


class PassengerMonth(BaseModel):
    month: str = Field(description="YYYY-MM en hora de Pamplona")
    trips: int
    spent: int


class PassengerStats(BaseModel):
    trips: int = Field(description="Viajes completados")
    spent: int = Field(description="Suma de los tickets (aportes) en COP")
    no_shows: int
    cancellations: int
    rating: RatingBlock
    top_origins: list[PlaceCount] = Field(description="Lugares de recogida mas usados")
    by_month: list[PassengerMonth] = Field(description="Ultimos 12 meses")


class DriverMonth(BaseModel):
    month: str
    trips: int
    passengers: int


class DriverStats(BaseModel):
    trips: int = Field(description="Viajes completados")
    passengers: int = Field(description="Pasajeros que viajaron")
    occupancy: float | None = Field(description="Promedio de puestos usados / ofrecidos (0 a 1)")
    contributions: int = Field(description="Suma de los tickets")
    confirmed_contributions: int = Field(description="Aportes que el conductor confirmo")
    cancellations: int
    rating: RatingBlock
    by_month: list[DriverMonth]


class PassengerHistoryEntry(BaseModel):
    booking_id: uuid.UUID
    trip_id: uuid.UUID
    departs_at: datetime
    origin: str
    destination: str
    driver_name: str
    trip_status: TripStatus
    booking_status: BookingStatus
    seats: int
    amount: int | None
    ticket_code: str | None
    paid_confirmed: bool | None
    rating: RatingState
    rating_closes_at: datetime | None


class DriverHistoryEntry(BaseModel):
    trip_id: uuid.UUID
    series_id: uuid.UUID | None
    departs_at: datetime
    origin: str
    destination: str
    trip_status: TripStatus
    seats_total: int
    passengers: int = Field(description="Puestos de quienes viajaron")
    contributions: int
    to_rate: int = Field(description="Pasajeros que aun puede calificar")
    rating: RatingState
    rating_closes_at: datetime | None
