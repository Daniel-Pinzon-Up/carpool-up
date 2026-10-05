"""Quien entra y sale de cada chat segun sus reservas (seccion 7.5). Ninguna funcion hace commit.

Al aceptarse una reserva el pasajero entra al chat grupal de la ocurrencia y al directo con
el conductor (que dura toda la serie). Si la reserva deja de estar vigente sale del grupal;
el directo de una serie sigue. Cuando el viaje se cancela, sus chats se cierran.
"""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import ConversationKind
from app.core.realtime import emit, user_channel
from app.modules.bookings.models import Booking
from app.modules.chat.models import Conversation, ConversationMember
from app.modules.trips.models import Trip


async def _find(session: AsyncSession, **where: Any) -> Conversation | None:
    query = select(Conversation)
    for column, value in where.items():
        attribute = getattr(Conversation, column)
        query = query.where(attribute.is_(None) if value is None else attribute == value)
    return await session.scalar(query)


async def _get_or_create(session: AsyncSession, **fields: Any) -> Conversation:
    """Busca el chat; si no existe lo crea en un savepoint (dos aceptaciones a la vez)."""
    key = {k: v for k, v in fields.items() if k != "driver_id"}
    found = await _find(session, **key)
    if found is not None:
        return found
    try:
        async with session.begin_nested():
            conversation = Conversation(**fields)
            session.add(conversation)
        return conversation
    except IntegrityError:
        found = await _find(session, **key)
        assert found is not None  # noqa: S101 - la otra transaccion lo acaba de crear
        return found


async def _add_member(
    session: AsyncSession, conversation: Conversation, user_id: uuid.UUID
) -> None:
    member = await session.get(ConversationMember, (conversation.id, user_id))
    if member is not None and member.left_at is None:
        return
    if member is None:
        session.add(ConversationMember(conversation_id=conversation.id, user_id=user_id))
    else:
        member.left_at = None
    # La conexion abierta del usuario empieza a escuchar el chat nuevo.
    emit(
        session,
        user_channel(user_id),
        {"type": "conversation.joined", "conversation_id": str(conversation.id)},
    )


async def join_trip_chats(session: AsyncSession, booking: Booking) -> None:
    trip = booking.trip
    group = await _get_or_create(
        session,
        kind=ConversationKind.TRIP_GROUP,
        trip_id=trip.id,
        driver_id=trip.driver_id,
    )
    direct = await _get_or_create(
        session,
        kind=ConversationKind.DIRECT,
        series_id=trip.series_id,
        trip_id=None if trip.series_id else trip.id,
        passenger_id=booking.passenger_id,
        driver_id=trip.driver_id,
    )
    for conversation in (group, direct):
        conversation.closed_at = None
        await _add_member(session, conversation, trip.driver_id)
        await _add_member(session, conversation, booking.passenger_id)


async def leave_trip_chat(session: AsyncSession, booking: Booking) -> None:
    """El pasajero ya no viaja: sale del chat grupal de esa ocurrencia."""
    group = await _find(session, kind=ConversationKind.TRIP_GROUP, trip_id=booking.trip_id)
    if group is None:
        return
    await session.execute(
        update(ConversationMember)
        .where(
            ConversationMember.conversation_id == group.id,
            ConversationMember.user_id == booking.passenger_id,
            ConversationMember.left_at.is_(None),
        )
        .values(left_at=utcnow())
    )


async def close_trip_chats(session: AsyncSession, trip: Trip) -> None:
    """Viaje cancelado o terminado: su grupal y los directos de viaje puntual se cierran."""
    await session.execute(
        update(Conversation)
        .where(Conversation.trip_id == trip.id, Conversation.closed_at.is_(None))
        .values(closed_at=utcnow())
    )


async def close_series_chats(session: AsyncSession, series_id: uuid.UUID) -> None:
    await session.execute(
        update(Conversation)
        .where(Conversation.series_id == series_id, Conversation.closed_at.is_(None))
        .values(closed_at=utcnow())
    )
