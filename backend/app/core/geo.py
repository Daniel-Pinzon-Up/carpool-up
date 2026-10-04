"""Conversion entre coordenadas y geometrias PostGIS (SRID 4326, orden lon lat)."""

from geoalchemy2 import WKBElement, WKTElement
from geoalchemy2.shape import to_shape

SRID = 4326


def point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=SRID)


def lat_lon(element: WKBElement | WKTElement) -> tuple[float, float]:
    shape = to_shape(element)
    return shape.y, shape.x
