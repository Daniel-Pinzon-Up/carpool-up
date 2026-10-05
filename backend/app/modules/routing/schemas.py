import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.core.enums import VehicleType


class RoutePoint(BaseModel):
    """Un punto del catalogo o un pin propio (place_id), o coordenadas sueltas."""

    place_id: uuid.UUID | None = None
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(ge=-180, le=180)] | None = None

    @model_validator(mode="after")
    def one_form(self) -> "RoutePoint":
        has_coords = self.lat is not None and self.lon is not None
        has_partial = (self.lat is None) != (self.lon is None)
        if has_partial or (self.place_id is not None) == has_coords:
            raise ValueError("send either place_id or lat and lon")
        return self


class RoutePreviewRequest(BaseModel):
    points: list[RoutePoint] = Field(
        min_length=2, description="Origen, paradas intermedias en orden y destino"
    )
    departs_at: AwareDatetime | None = Field(
        default=None, description="Para ajustar la ETA con el factor de trafico de esa franja"
    )
    vehicle_type: VehicleType | None = Field(default=None, description="Para el precio sugerido")
    seats: Annotated[int, Field(ge=1, le=7)] | None = Field(
        default=None, description="Puestos ofrecidos, para el precio sugerido"
    )


class ResolvedPoint(BaseModel):
    place_id: uuid.UUID | None
    name: str | None
    lat: float
    lon: float
    eta_offset_s: int = Field(description="Segundos desde la salida, ya ajustados por trafico")
    eta: datetime | None


class RoutePreview(BaseModel):
    geometry: list[list[float]] = Field(description="LineString GeoJSON: [[lon, lat], ...]")
    distance_m: int
    osrm_duration_s: int
    traffic_factor: float
    duration_s: int = Field(description="Duracion ajustada por el factor de trafico")
    points: list[ResolvedPoint]
    pricing_configured: bool
    suggested_price: int | None
    max_price_per_seat: int | None
