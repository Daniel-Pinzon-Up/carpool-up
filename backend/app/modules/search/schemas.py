import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.enums import TripStatus, VehicleType
from app.modules.trips.schemas import RuleOut


class SearchQuery(BaseModel):
    """Origen y destino (lugar o pin), fecha y hora locales de Pamplona, puestos y preferencias."""

    origin_place_id: uuid.UUID | None = None
    origin_lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    origin_lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    destination_place_id: uuid.UUID | None = None
    destination_lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    destination_lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    date: date
    time: time
    seats: Annotated[int, Field(ge=1, le=7)] = 1
    pets: bool = Field(default=False, description="Viajo con mascota")
    luggage: bool = Field(default=False, description="Llevo equipaje grande")
    no_smoking: bool = Field(default=False, description="Sin humo")
    music: bool = Field(default=False, description="Quiero musica")
    women_only: bool = Field(default=False, description="Solo viajes de solo mujeres")

    @model_validator(mode="after")
    def one_form_per_point(self) -> "SearchQuery":
        for prefix in ("origin", "destination"):
            place = getattr(self, f"{prefix}_place_id")
            lat, lon = getattr(self, f"{prefix}_lat"), getattr(self, f"{prefix}_lon")
            coords = lat is not None and lon is not None
            partial = (lat is None) != (lon is None)
            if partial or (place is not None) == coords:
                raise ValueError(f"send {prefix}_place_id or {prefix}_lat and {prefix}_lon")
        return self


class MatchPoint(BaseModel):
    """Recogida o bajada ajustada a una parada del viaje o al punto mas cercano de la ruta."""

    kind: Literal["stop", "route"]
    name: str | None = Field(description="Nombre de la parada; nulo si es un punto de la ruta")
    lat: float
    lon: float
    eta: datetime
    walk_m: int = Field(description="Distancia en linea recta desde el punto pedido")


class DriverCard(BaseModel):
    """Datos publicos del conductor: sin correo, telefono ni documentos."""

    id: uuid.UUID
    full_name: str
    rating: float | None = Field(description="Promedio de calificaciones (paso 11)")
    trips_as_driver: int


class VehicleCard(BaseModel):
    """Sin placa: se muestra solo al pasajero aceptado (paso 8)."""

    type: VehicleType
    brand: str
    model: str
    color: str
    has_photo: bool
    vehicle_id: uuid.UUID


class SearchResult(BaseModel):
    trip_id: uuid.UUID
    series_id: uuid.UUID | None
    status: TripStatus
    departs_at: datetime
    arrives_at: datetime
    origin: str
    destination: str
    price_per_seat: int
    seats_available: int
    pickup: MatchPoint
    dropoff: MatchPoint
    minutes_from_requested: int = Field(description="Diferencia entre la salida y la hora pedida")
    driver: DriverCard
    vehicle: VehicleCard
    rules: list[RuleOut]
