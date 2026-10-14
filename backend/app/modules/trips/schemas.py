import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.core.enums import BookingStatus, RuleKind, StopKind, TripStatus, VehicleType

ALLOWED = "allowed"
NOT_ALLOWED = "not_allowed"

Seats = Annotated[int, Field(ge=1, le=7, description="Puestos ofrecidos (hasta capacidad - 1)")]
Price = Annotated[int, Field(ge=0, le=1_000_000, description="Aporte por puesto en COP")]
PlaceIds = Annotated[
    list[uuid.UUID],
    Field(min_length=2, description="Origen, paradas intermedias en orden y destino"),
]
Reason = Annotated[str, Field(min_length=5, max_length=500)]


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
    eta: datetime


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
    chat_id: uuid.UUID | None = Field(
        default=None, description="Chat del viaje (su id es el del viaje) si quien consulta esta"
    )
