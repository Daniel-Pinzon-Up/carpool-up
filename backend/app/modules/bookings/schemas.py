import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.enums import (
    BookingStatus,
    CancelRequestStatus,
    SubscriptionStatus,
    TripStatus,
    WaitlistStatus,
)
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


class SubscriptionCreate(PointsIn):
    option: int | Literal["series"] = Field(
        description="Dias del rango segun subscription_options_days, o 'series' (toda la serie)"
    )
    start_date: date


class WaitlistJoin(PointsIn):
    pass


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
    series_id: uuid.UUID | None
    status: TripStatus
    departs_at: datetime
    arrives_at: datetime
    origin: str
    destination: str
    price_per_seat: int
    driver: DriverOut
    vehicle: VehicleSummary = Field(description="La placa se ve con la reserva aceptada")


class CancellationOut(BaseModel):
    id: uuid.UUID
    reason: str
    status: CancelRequestStatus
    created_at: datetime
    resolved_at: datetime | None


class BookingOut(BaseModel):
    id: uuid.UUID
    trip: TripBrief
    passenger: PassengerCard
    subscription_id: uuid.UUID | None
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
    cancelled_at: datetime | None
    cancel_reason: str | None
    cancellation: CancellationOut | None
    payment_note: str | None = Field(description="Datos de pago del conductor, al ser aceptado")


class SeriesBrief(BaseModel):
    id: uuid.UUID
    origin: str
    destination: str
    weekdays: list[int]
    departure_time: time
    window_end: date
    price_per_seat: int
    driver: DriverOut


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    series: SeriesBrief
    passenger: PassengerCard
    from_date: date
    to_date: date
    seats: int
    pickup_place: str
    dropoff_place: str
    preferences: Preferences
    status: SubscriptionStatus
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None
    reject_reason: str | None
    booked_dates: list[date] = Field(description="Fechas con reserva activa de la suscripcion")
    skipped_dates: list[date] = Field(
        description="Fechas del rango sin reserva (llenas, pico y placa o solapadas)"
    )


class AvailabilityDay(BaseModel):
    trip_id: uuid.UUID
    date: date
    departs_at: datetime
    status: TripStatus
    seats_available: int
    bookable: bool = Field(description="Programado, con cupo para los puestos pedidos")


class SeriesAvailability(BaseModel):
    series_id: uuid.UUID
    options: list[int | Literal["series"]]
    days: list[AvailabilityDay]


class WaitlistOut(BaseModel):
    id: uuid.UUID
    trip: TripBrief
    seats: int
    status: WaitlistStatus
    ahead: int = Field(description="Personas antes en la fila")
    offered_at: datetime | None
    offer_expires_at: datetime | None
    booking_id: uuid.UUID | None
    created_at: datetime


class InboxOut(BaseModel):
    """Bandeja del conductor: lo que espera su decision."""

    bookings: list[BookingOut]
    cancellations: list[BookingOut]
    subscriptions: list[SubscriptionOut]
