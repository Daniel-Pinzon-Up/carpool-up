"""Punto de encuentro de una reserva sobre un viaje concreto (misma regla que la busqueda)."""

from dataclasses import dataclass
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import Function

from app.core.geo import SRID
from app.modules.bookings.models import Booking
from app.modules.search.schemas import MatchPoint
from app.modules.search.service import Point, SearchService
from app.modules.trips.models import Trip


@dataclass(frozen=True)
class Meeting:
    pickup: MatchPoint
    dropoff: MatchPoint
    # La ruta pasa a menos del radio de ambos puntos y en el orden correcto.
    on_route: bool


async def meeting_points(
    session: AsyncSession, trip: Trip, pickup: Point, dropoff: Point, radius: int
) -> Meeting:
    def geom(p: Point) -> Function[Any]:
        return func.ST_SetSRID(func.ST_MakePoint(p.lon, p.lat), SRID)

    route_geo = cast(Trip.route, Geography)
    p_fraction = func.ST_LineLocatePoint(Trip.route, geom(pickup))
    d_fraction = func.ST_LineLocatePoint(Trip.route, geom(dropoff))
    p_on = func.ST_LineInterpolatePoint(Trip.route, p_fraction)
    d_on = func.ST_LineInterpolatePoint(Trip.route, d_fraction)
    row = (
        await session.execute(
            select(
                p_fraction.label("pf"),
                d_fraction.label("df"),
                func.ST_Y(p_on).label("p_lat"),
                func.ST_X(p_on).label("p_lon"),
                func.ST_Y(d_on).label("d_lat"),
                func.ST_X(d_on).label("d_lon"),
                func.ST_Distance(route_geo, cast(geom(pickup), Geography)).label("p_dist"),
                func.ST_Distance(route_geo, cast(geom(dropoff), Geography)).label("d_dist"),
            ).where(Trip.id == trip.id)
        )
    ).one()
    board = SearchService.match(
        trip, pickup, Point(row.p_lat, row.p_lon), row.pf, radius, pickup=True
    )
    alight = SearchService.match(
        trip, dropoff, Point(row.d_lat, row.d_lon), row.df, radius, pickup=False
    )
    on_route = (
        row.p_dist <= radius and row.d_dist <= radius and row.pf < row.df and board.eta < alight.eta
    )
    return Meeting(board, alight, on_route)


def apply_meeting(booking: Booking, meeting: Meeting) -> None:
    board, alight = meeting.pickup, meeting.dropoff
    booking.pickup_name = board.name
    booking.pickup_lat = board.lat
    booking.pickup_lon = board.lon
    booking.pickup_eta = board.eta
    booking.pickup_walk_m = board.walk_m
    booking.dropoff_name = alight.name
    booking.dropoff_lat = alight.lat
    booking.dropoff_lon = alight.lon
    booking.dropoff_eta = alight.eta
    booking.dropoff_walk_m = alight.walk_m
