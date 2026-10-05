import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.core.enums import (
    BookingStatus,
    RuleKind,
    SeriesStatus,
    StopKind,
    SubscriptionStatus,
    TripStatus,
    VehicleType,
    WaitlistStatus,
)

ALLOWED = "allowed"
NOT_ALLOWED = "not_allowed"

Seats = Annotated[int, Field(ge=1, le=7, description="Puestos ofrecidos (hasta capacidad - 1)")]
Price = Annotated[int, Field(ge=0, le=1_000_000, description="Aporte por puesto en COP")]
PlaceIds = Annotated[
    list[uuid.UUID],
    Field(min_length=2, description="Origen, paradas intermedias en orden y destino"),
]
Reason = Annotated[str, Field(min_length=5, max_length=500)]
Weekdays = Annotated[
    list[Annotated[int, Field(ge=0, le=6)]],
    Field(min_length=1, max_length=7, description="0 = lunes ... 6 = domingo"),
]
Window = Annotated[
    int | Literal["semester"],
    Field(description="Dias de la ventana (segun series_window_options_days) o 'semester'"),
]


class RuleIn(BaseModel):
    kind: RuleKind
    value: Annotated[str, Field(min_length=1, max_length=200)] = Field(
        description="allowed o not_allowed; texto libre si kind es custom"
    )

    @model_validator(mode="after")
    def check_value(self) -> "RuleIn":
        self.value = self.value.strip()
        if self.kind == RuleKind.CUSTOM:
            if not self.value:
                raise ValueError("custom rules need a text")
        elif self.value not in (ALLOWED, NOT_ALLOWED):
            raise ValueError("value must be allowed or not_allowed")
        return self


Rules = Annotated[list[RuleIn], Field(max_length=len(RuleKind))]


def _unique_kinds(rules: list[RuleIn]) -> list[RuleIn]:
    kinds = [rule.kind for rule in rules]
    if len(set(kinds)) != len(kinds):
        raise ValueError("each rule kind can appear only once")
    return rules


def _unique_weekdays(weekdays: list[int]) -> list[int]:
    if len(set(weekdays)) != len(weekdays):
        raise ValueError("weekdays must not repeat")
    return sorted(weekdays)


class TripCreate(BaseModel):
    place_ids: PlaceIds
    departs_at: AwareDatetime
    vehicle_id: uuid.UUID
    seats: Seats
    price_per_seat: Price
    rules: Rules = []

    _rules = field_validator("rules")(_unique_kinds)


class TripUpdate(BaseModel):
    """Solo se envian los campos que cambian."""

    place_ids: PlaceIds | None = None
    departs_at: AwareDatetime | None = None
    vehicle_id: uuid.UUID | None = None
    seats: Seats | None = None
    price_per_seat: Price | None = None
    rules: Rules | None = None

    @field_validator("rules")
    @classmethod
    def unique_rules(cls, rules: list[RuleIn] | None) -> list[RuleIn] | None:
        return _unique_kinds(rules) if rules is not None else None


class TripDuplicate(BaseModel):
    departs_at: AwareDatetime


class CancelRequest(BaseModel):
    reason: Reason


class SeriesCreate(BaseModel):
    place_ids: PlaceIds
    weekdays: Weekdays
    departure_time: time = Field(description="Hora local de Pamplona, sin zona")
    start_date: date
    window: Window
    vehicle_id: uuid.UUID
    seats: Seats
    price_per_seat: Price
    rules: Rules = []

    _rules = field_validator("rules")(_unique_kinds)
    _weekdays = field_validator("weekdays")(_unique_weekdays)


class SeriesUpdate(BaseModel):
    """Cambia la plantilla y las ocurrencias futuras. La ventana no se edita."""

    confirm: bool = Field(
        default=False,
        description="Confirma el cambio cuando hay reservas afectadas (SERIES_HAS_BOOKINGS)",
    )

    place_ids: PlaceIds | None = None
    weekdays: Weekdays | None = None
    departure_time: time | None = None
    vehicle_id: uuid.UUID | None = None
    seats: Seats | None = None
    price_per_seat: Price | None = None
    rules: Rules | None = None

    @field_validator("rules")
    @classmethod
    def unique_rules(cls, rules: list[RuleIn] | None) -> list[RuleIn] | None:
        return _unique_kinds(rules) if rules is not None else None

    @field_validator("weekdays")
    @classmethod
    def unique_weekdays(cls, weekdays: list[int] | None) -> list[int] | None:
        return _unique_weekdays(weekdays) if weekdays is not None else None


class SeriesDuplicate(BaseModel):
    start_date: date
    window: Window


# --- Respuestas -----------------------------------------------------------------------


class RuleOut(BaseModel):
    kind: RuleKind
    value: str


class StopOut(BaseModel):
    position: int
    kind: StopKind
    place_id: uuid.UUID
    name: str
    lat: float
    lon: float
    eta: datetime | None = Field(description="Nulo en la plantilla de una serie")


class DriverOut(BaseModel):
    """Datos publicos del conductor: nunca correo, telefono ni documentos."""

    id: uuid.UUID
    full_name: str


class VehicleSummary(BaseModel):
    id: uuid.UUID
    type: VehicleType
    brand: str
    model: str
    color: str
    has_photo: bool
    plate: str | None = Field(
        description="Solo para el conductor y los pasajeros con reserva aceptada"
    )


class TripSummary(BaseModel):
    id: uuid.UUID
    series_id: uuid.UUID | None
    status: TripStatus
    departs_at: datetime
    arrives_at: datetime
    seats_total: int
    price_per_seat: int
    origin: str
    destination: str
    stop_count: int = Field(description="Paradas intermedias")
    vehicle: VehicleSummary
    editable: bool = Field(description="El conductor todavia puede editarlo o cancelarlo")
    seats_available: int = Field(description="Puestos sin reserva aceptada")
    pending_requests: int = Field(
        default=0, description="Solicitudes y cancelaciones por decidir (solo el conductor)"
    )


class CoPassenger(BaseModel):
    """Pasajero aceptado. La recogida solo la ve el conductor."""

    id: uuid.UUID
    full_name: str
    seats: int
    pickup_name: str | None = None
    pickup_eta: datetime | None = None


class MyBooking(BaseModel):
    id: uuid.UUID
    status: BookingStatus
    seats: int
    pickup_name: str | None
    pickup_eta: datetime
    dropoff_name: str | None
    dropoff_eta: datetime


class MyWaitlist(BaseModel):
    id: uuid.UUID
    status: WaitlistStatus
    seats: int
    offer_expires_at: datetime | None


class TripOut(TripSummary):
    geometry: list[list[float]] = Field(description="LineString GeoJSON: [[lon, lat], ...]")
    distance_m: int
    est_duration_s: int
    stops: list[StopOut]
    rules: list[RuleOut]
    driver: DriverOut
    cancel_reason: str | None
    cancelled_at: datetime | None
    passengers: list[CoPassenger] = Field(
        default=[], description="Aceptados; visibles para el conductor y los otros aceptados"
    )
    payment_note: str | None = Field(
        default=None, description="Datos de pago del conductor, para pasajeros aceptados"
    )
    my_booking: MyBooking | None = Field(default=None, description="Reserva del que consulta")
    my_waitlist: MyWaitlist | None = None


class OccurrenceCounts(BaseModel):
    total: int
    scheduled: int
    pico_placa: int
    cancelled: int


class SeriesSummary(BaseModel):
    id: uuid.UUID
    status: SeriesStatus
    weekdays: list[int]
    departure_time: time
    window_start: date
    window_end: date
    seats: int
    price_per_seat: int
    origin: str
    destination: str
    vehicle: VehicleSummary
    next_departure: datetime | None
    counts: OccurrenceCounts


class MySubscription(BaseModel):
    id: uuid.UUID
    status: SubscriptionStatus
    from_date: date
    to_date: date


class SeriesOut(SeriesSummary):
    stops: list[StopOut]
    rules: list[RuleOut]
    driver: DriverOut
    cancel_reason: str | None
    occurrences: list[TripSummary]
    my_subscription: MySubscription | None = Field(
        default=None, description="Suscripcion abierta o mas reciente del que consulta"
    )
