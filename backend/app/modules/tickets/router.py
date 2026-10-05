import uuid
from typing import Literal

from fastapi import APIRouter

from app.core.auth import ActiveUser, Driver
from app.core.deps import DbSession
from app.modules.tickets.service import PaidIn, TicketOut, TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/mine")
async def my_tickets(
    user: ActiveUser,
    session: DbSession,
    role: Literal["passenger", "driver"] = "passenger",
    trip_id: uuid.UUID | None = None,
) -> list[TicketOut]:
    """Como pasajero, los propios; como conductor, los de sus viajes (opcional por viaje)."""
    return await TicketService(session).list_for(user, role, trip_id)


@router.post("/{ticket_id}/paid")
async def mark_paid(
    ticket_id: uuid.UUID, body: PaidIn, user: Driver, session: DbSession
) -> TicketOut:
    """El conductor confirma (o desmarca) que recibio el aporte. Informativo."""
    return await TicketService(session).set_paid(user, ticket_id, body.paid)
