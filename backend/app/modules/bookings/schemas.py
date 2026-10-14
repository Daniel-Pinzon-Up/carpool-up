import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.enums import BookingStatus, TripStatus
from app.modules.trips.schemas import DriverOut, VehicleSummary

Seats = Annotated[int, Field(ge=1, le=7)]
OptionalReason = Annotated[str, Field(min_length=5, max_length=500)] | None


class Preferences(BaseModel):
    """Lo que el pasajero lleva o pide; debe ser compatible con las reglas del viaje."""

    pets: bool = False
    luggage: bool = False
    no_smoking: bool = False
    music: bool = False


class PointsIn(BaseModel):
    seats: Seats = 1
    pickup_place_id: uuid.UUID = Field(description="Lugar del catalogo o pin propio")
    dropoff_place_id: uuid.UUID
    preferences: Preferences = Preferences()


class BookingCreate(PointsIn):
    pass


class ReasonIn(BaseModel):
    reason: OptionalReason = None


# --- Respuestas -----------------------------------------------------------------------


class PassengerCard(BaseModel):
    """Datos publicos del pasajero para el conductor: sin correo, telefono ni documentos."""

    id: uuid.UUID
    full_name: str
    program: str | None
    rating: float | None = Field(description="Promedio de calificaciones (paso 11)")
    trips_as_passenger: int


class MeetingPoint(BaseModel):
    place_id: uuid.UUID = Field(description="Lugar que eligio el pasajero")
    place_name: str
    kind: Literal["stop", "route"]
    name: str | None = Field(description="Parada del viaje; nulo si es un punto de la ruta")
    lat: float
    lon: float
    eta: datetime
    walk_m: int


class TripBrief(BaseModel):
    id: uuid.UUID
    status: TripStatus
    departs_at: datetime
    arrives_at: datetime
    origin: str
    destination: str
    price_per_seat: int
    driver: DriverOut
    vehicle: VehicleSummary = Field(description="La placa se ve con la reserva aceptada")


class CancellationOut(BaseModel):
    """Cancelacion tardia pendiente: el conductor la acepta o la rechaza."""

    reason: str | None


class BookingOut(BaseModel):
    id: uuid.UUID
    trip: TripBrief
    passenger: PassengerCard
    seats: int
    amount: int = Field(description="Aporte total: puestos por aporte por puesto")
    status: BookingStatus
    pickup: MeetingPoint
    dropoff: MeetingPoint
    preferences: Preferences
    expires_at: datetime
    penalty_free: bool
    free_cancel: bool = Field(
        description="Cancelar ahora es inmediato; si es falso se crea una solicitud al conductor"
    )
    created_at: datetime
    decided_at: datetime | None
    boarded_at: datetime | None = Field(description="El conductor lo marco a bordo")
    no_show_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    cancellation: CancellationOut | None = Field(
        description="Presente mientras la cancelacion tardia espera al conductor"
    )
    payment_note: str | None = Field(description="Datos de pago del conductor, al ser aceptado")


class InboxOut(BaseModel):
    """Bandeja del conductor: lo que espera su decision."""

    bookings: list[BookingOut]
    cancellations: list[BookingOut]
