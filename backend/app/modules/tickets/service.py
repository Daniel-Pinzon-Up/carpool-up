"""Tickets informativos (sin pago en la app): al finalizar el viaje, cada reserva que abordo
recibe un codigo y el monto del aporte. Se guardan en la misma reserva; el id del ticket es
el id de la reserva."""

import secrets
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.errors import NotFoundError
from app.modules.bookings.models import Booking
from app.modules.trips.models import Trip
from app.modules.users.models import User

# Sin 0/O ni 1/I/L: el codigo se lee en voz alta o se copia a mano sin confusiones.
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"CP-{body[:4]}-{body[4:]}"


class TicketOut(BaseModel):
    id: uuid.UUID = Field(description="Id de la reserva")
    booking_id: uuid.UUID
    code: str
    amount: int
    seats: int
    issued_at: datetime
    paid_confirmed: bool
    paid_confirmed_at: datetime | None
    trip_id: uuid.UUID
    departs_at: datetime
    origin: str
    destination: str
    driver_name: str
    passenger_name: str = Field(description="Quien viajo (el conductor ve a cada pasajero)")


class PaidIn(BaseModel):
    paid: bool = True


def ticket_out(booking: Booking) -> TicketOut:
    trip = booking.trip
    assert booking.ticket_code is not None  # noqa: S101 - solo reservas con ticket
    assert booking.ticket_issued_at is not None  # noqa: S101
    return TicketOut(
        id=booking.id,
        booking_id=booking.id,
        code=booking.ticket_code,
        amount=booking.ticket_amount or 0,
        seats=booking.seats,
        issued_at=booking.ticket_issued_at,
        paid_confirmed=booking.paid_confirmed,
        paid_confirmed_at=booking.paid_confirmed_at,
        trip_id=trip.id,
        departs_at=trip.departs_at,
        origin=trip.stops[0].place.name,
        destination=trip.stops[-1].place.name,
        driver_name=trip.driver.full_name,
        passenger_name=booking.passenger.full_name,
    )


async def issue_ticket(session: AsyncSession, booking: Booking) -> str:
    """Asigna el codigo y el monto una sola vez; si el codigo ya existe, se genera otro."""
    if booking.ticket_code is not None:
        return booking.ticket_code
    code = new_code()
    while await session.scalar(select(Booking.id).where(Booking.ticket_code == code)) is not None:
        code = new_code()
    booking.ticket_code = code
    booking.ticket_amount = booking.seats * booking.trip.price_per_seat
    booking.ticket_issued_at = utcnow()
    return code


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for(
        self, user: User, role: Literal["passenger", "driver"], trip_id: uuid.UUID | None
    ) -> list[TicketOut]:
        query = (
            select(Booking)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(Booking.ticket_code.is_not(None))
        )
        if role == "passenger":
            query = query.where(Booking.passenger_id == user.id)
        else:
            query = query.where(Trip.driver_id == user.id)
        if trip_id is not None:
            query = query.where(Trip.id == trip_id)
        rows = await self.session.scalars(query.order_by(Booking.ticket_issued_at.desc()))
        return [ticket_out(b) for b in rows.all()]

    async def set_paid(self, driver: User, ticket_id: uuid.UUID, paid: bool) -> TicketOut:
        """Solo el conductor del viaje confirma que recibio el aporte."""
        booking = await self.session.get(Booking, ticket_id)
        if booking is None or booking.ticket_code is None or booking.trip.driver_id != driver.id:
            raise NotFoundError("ticket")
        booking.paid_confirmed = paid
        booking.paid_confirmed_at = utcnow() if paid else None
        await self.session.commit()
        return ticket_out(booking)
