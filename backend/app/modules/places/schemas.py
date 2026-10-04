import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.enums import PlaceKind

PlaceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
CatalogKind = Literal[PlaceKind.CAMPUS, PlaceKind.SECTOR, PlaceKind.LANDMARK]


class PlaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: PlaceKind
    lat: float
    lon: float
    is_active: bool


class PlaceCreate(BaseModel):
    name: PlaceName
    kind: CatalogKind
    lat: Latitude
    lon: Longitude


class PlaceUpdate(BaseModel):
    name: PlaceName | None = None
    kind: CatalogKind | None = None
    lat: Latitude | None = None
    lon: Longitude | None = None
    is_active: bool | None = None


class CustomPlaceCreate(BaseModel):
    name: PlaceName
    lat: Latitude
    lon: Longitude
