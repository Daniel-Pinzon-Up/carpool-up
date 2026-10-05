"""Tickets informativos: se emiten al finalizar el viaje para quien abordo (seccion 7.6)."""

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
from app.modules.tickets.models import Ticket
from app.modules.trips.models import Trip
from app.modules.users.models import User

# Sin 0/O ni 1/I/L: el codigo se lee en voz alta o se copia a mano sin confusiones.
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"CP-{body[:4]}-{body[4:]}"


class TicketOut(BaseModel):
    id: uuid.UUID
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


def ticket_out(ticket: Ticket) -> TicketOut:
    booking = ticket.booking
    trip = booking.trip
    return TicketOut(
        id=ticket.id,
        code=ticket.code,
        amount=ticket.amount,
        seats=booking.seats,
        issued_at=ticket.issued_at,
        paid_confirmed=ticket.paid_confirmed,
        paid_confirmed_at=ticket.paid_confirmed_at,
        trip_id=trip.id,
        departs_at=trip.departs_at,
        origin=trip.stops[0].place.name,
        destination=trip.stops[-1].place.name,
        driver_name=trip.driver.full_name,
        passenger_name=booking.passenger.full_name,
    )


async def issue_ticket(session: AsyncSession, booking: Booking) -> Ticket:
    """Un ticket por reserva; el codigo se repite muy rara vez y se reintenta."""
    existing = await session.scalar(select(Ticket).where(Ticket.booking_id == booking.id))
    if existing is not None:
        return existing
    code = new_code()
    while await session.scalar(select(Ticket.id).where(Ticket.code == code)) is not None:
        code = new_code()
    ticket = Ticket(
        booking_id=booking.id,
        code=code,
        amount=booking.seats * booking.trip.price_per_seat,
        issued_at=utcnow(),
    )
    ticket.booking = booking
    session.add(ticket)
    return ticket


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for(
        self, user: User, role: Literal["passenger", "driver"], trip_id: uuid.UUID | None
    ) -> list[TicketOut]:
        query = (
            select(Ticket)
            .join(Booking, Booking.id == Ticket.booking_id)
            .join(Trip, Trip.id == Booking.trip_id)
        )
        if role == "passenger":
            query = query.where(Booking.passenger_id == user.id)
        else:
            query = query.where(Trip.driver_id == user.id)
        if trip_id is not None:
            query = query.where(Trip.id == trip_id)
        rows = await self.session.scalars(query.order_by(Ticket.issued_at.desc()))
        return [ticket_out(t) for t in rows.all()]

    async def set_paid(self, driver: User, ticket_id: uuid.UUID, paid: bool) -> TicketOut:
        """Solo el conductor del viaje confirma que recibio el aporte."""
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None or ticket.booking.trip.driver_id != driver.id:
            raise NotFoundError("ticket")
        ticket.paid_confirmed = paid
        ticket.paid_confirmed_at = utcnow() if paid else None
        await self.session.commit()
        return ticket_out(ticket)
