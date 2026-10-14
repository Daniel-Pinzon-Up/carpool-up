"""Quien participa en el chat de un viaje: el conductor y los pasajeros aceptados.

No hay tabla de miembros: se deduce de las reservas. El pasajero entra al ser aceptado y
sale si cancela o no se presenta. El chat esta abierto mientras el viaje esta programado o
en curso; despues queda de solo lectura (tambien para quienes iban aceptados cuando el
viaje se cancelo) hasta que se borra.
"""

import uuid

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BookingStatus, TripStatus
from app.core.realtime import emit, user_channel
from app.modules.bookings.models import HOLDING_STATUSES, Booking
from app.modules.trips.models import Trip
from app.modules.users.models import User

# Pasajeros que siguen en el chat: aceptados o que ya viajaron.
MEMBER_STATUSES = (*HOLDING_STATUSES, BookingStatus.COMPLETED)
# Reservas que termino el viaje (cancelado, pico y placa, retraso o no realizado): quien ya
# estaba aceptado (decided_at) sigue leyendo el chat.
ENDED_WITH_TRIP = (
    BookingStatus.CANCELLED_BY_DRIVER,
    BookingStatus.AUTO_CANCELLED_PICO_PLACA,
    BookingStatus.AUTO_CANCELLED_LATE,
    BookingStatus.EXPIRED,
)
OPEN_TRIP_STATUSES = (TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)


def in_chat() -> ColumnElement[bool]:
    """Condicion SQL: la reserva le da acceso al chat del viaje."""
    return or_(
        Booking.status.in_(MEMBER_STATUSES),
        and_(Booking.status.in_(ENDED_WITH_TRIP), Booking.decided_at.is_not(None)),
    )


def is_open(trip: Trip) -> bool:
    return trip.deleted_at is None and trip.status in OPEN_TRIP_STATUSES


async def passengers_in_chat(session: AsyncSession, trip_id: uuid.UUID) -> list[Booking]:
    rows = await session.scalars(
        select(Booking).where(Booking.trip_id == trip_id, in_chat()).order_by(Booking.decided_at)
    )
    return list(rows.all())


async def can_chat(session: AsyncSession, user: User, trip: Trip) -> bool:
    """El conductor del viaje o un pasajero aceptado (o que ya viajo)."""
    if trip.deleted_at is not None:
        return False
    if trip.driver_id == user.id:
        return (
            await session.scalar(
                select(Booking.id).where(Booking.trip_id == trip.id, in_chat()).limit(1)
            )
            is not None
        )
    found = await session.scalar(
        select(Booking.id).where(
            Booking.trip_id == trip.id,
            Booking.passenger_id == user.id,
            in_chat(),
        )
    )
    return found is not None


async def chat_trip_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Viajes con chat abierto del usuario (los que escucha su conexion WebSocket)."""
    as_passenger = select(Booking.trip_id).where(
        Booking.passenger_id == user_id, Booking.status.in_(HOLDING_STATUSES)
    )
    as_driver = (
        select(Trip.id)
        .join(Booking, Booking.trip_id == Trip.id)
        .where(Trip.driver_id == user_id, Booking.status.in_(HOLDING_STATUSES))
    )
    rows = await session.scalars(
        select(Trip.id).where(
            Trip.id.in_(as_passenger.union(as_driver)),
            Trip.deleted_at.is_(None),
            Trip.status.in_(OPEN_TRIP_STATUSES),
        )
    )
    return list(rows.all())


def announce_joined(session: AsyncSession, booking: Booking) -> None:
    """Al aceptar la reserva, las conexiones abiertas del pasajero y del conductor empiezan a
    escuchar el chat del viaje."""
    for person in (booking.passenger_id, booking.trip.driver_id):
        emit(
            session,
            user_channel(person),
            {"type": "conversation.joined", "conversation_id": str(booking.trip_id)},
        )
