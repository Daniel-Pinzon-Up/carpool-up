"""Chat del viaje: lista, historial, envio y lectura (secciones 5.8 y 9).

Cada viaje tiene un chat; su id es el id del viaje. Los mensajes sin leer se cuentan desde
el aviso "mensaje nuevo" pendiente del usuario: al marcar el chat como leido, ese aviso se
marca leido y el contador vuelve a cero.
"""

import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.realtime import conversation_channel, emit
from app.modules.bookings.models import Booking
from app.modules.chat.membership import can_chat, in_chat, is_open, passengers_in_chat
from app.modules.chat.models import Message
from app.modules.chat.schemas import ConversationOut, MemberOut, MessageOut, UnreadMessages
from app.modules.notifications.models import Notification
from app.modules.notifications.service import Kind, NotificationService
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.users.models import User

logger = structlog.get_logger("chat")

HISTORY_LIMIT = 50


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.trip_id,
        sender_id=message.sender_id,
        sender_name=message.sender.full_name,
        body=message.body,
        sent_at=message.sent_at,
    )


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Acceso -------------------------------------------------------------------------

    async def chat_trip(self, user: User, trip_id: uuid.UUID) -> Trip:
        """Solo el conductor y los pasajeros aceptados ven el chat."""
        trip = await self.session.get(Trip, trip_id)
        if trip is None or not await can_chat(self.session, user, trip):
            raise NotFoundError("conversation")
        return trip

    async def my_trips(self, user: User) -> list[Trip]:
        """Viajes con chat del usuario (abiertos y cerrados, hasta que se borran)."""
        as_passenger = select(Booking.trip_id).where(Booking.passenger_id == user.id, in_chat())
        as_driver = (
            select(Booking.trip_id)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(Trip.driver_id == user.id, in_chat())
        )
        rows = await self.session.scalars(
            select(Trip).where(
                Trip.id.in_(as_passenger.union(as_driver)), Trip.deleted_at.is_(None)
            )
        )
        return list(rows.all())

    # --- Lectura ------------------------------------------------------------------------

    async def unread_since(self, user: User, trip_id: uuid.UUID) -> datetime | None:
        """Desde cuando hay mensajes sin leer: la hora del primer mensaje que genero el aviso
        de mensaje nuevo que sigue pendiente."""
        since = await self.session.scalar(
            select(func.min(Notification.payload["since"].astext)).where(
                Notification.user_id == user.id,
                Notification.kind == Kind.MESSAGE_NEW,
                Notification.read_at.is_(None),
                Notification.payload["conversation_id"].astext == str(trip_id),
            )
        )
        return datetime.fromisoformat(since) if since else None

    async def unread_count(self, user: User, trip_id: uuid.UUID) -> int:
        since = await self.unread_since(user, trip_id)
        if since is None:
            return 0
        count = await self.session.scalar(
            select(func.count()).where(
                Message.trip_id == trip_id,
                Message.sender_id != user.id,
                Message.hidden.is_(False),
                Message.sent_at >= since,
            )
        )
        return int(count or 0)

    async def last_message(self, trip_id: uuid.UUID) -> Message | None:
        return await self.session.scalar(
            select(Message)
            .where(Message.trip_id == trip_id, Message.hidden.is_(False))
            .order_by(Message.sent_at.desc(), Message.id.desc())
            .limit(1)
        )

    async def out(self, trip: Trip, user: User) -> ConversationOut:
        riders = await passengers_in_chat(self.session, trip.id)
        last = await self.last_message(trip.id)
        return ConversationOut(
            id=trip.id,
            trip_id=trip.id,
            title=f"{trip.stops[0].place.name} - {trip.stops[-1].place.name}",
            departs_at=trip.departs_at,
            members=[
                MemberOut(id=trip.driver_id, full_name=trip.driver.full_name, is_driver=True),
                *(
                    MemberOut(id=b.passenger_id, full_name=b.passenger.full_name, is_driver=False)
                    for b in riders
                ),
            ],
            last_message=message_out(last) if last is not None else None,
            unread=await self.unread_count(user, trip.id),
            closed=not is_open(trip),
        )

    async def list_for(self, user: User) -> list[ConversationOut]:
        """Chats abiertos primero; dentro de cada grupo, los de actividad mas reciente."""
        outs = [await self.out(trip, user) for trip in await self.my_trips(user)]

        def activity(item: ConversationOut) -> float:
            moment = item.last_message.sent_at if item.last_message else item.departs_at
            return moment.timestamp()

        return sorted(outs, key=lambda item: (item.closed, -activity(item)))

    async def get(self, user: User, conversation_id: uuid.UUID) -> ConversationOut:
        return await self.out(await self.chat_trip(user, conversation_id), user)

    async def history(
        self,
        user: User,
        conversation_id: uuid.UUID,
        *,
        before: uuid.UUID | None = None,
        after: uuid.UUID | None = None,
        limit: int = HISTORY_LIMIT,
    ) -> list[MessageOut]:
        """Mensajes en orden cronologico. before: pagina anterior; after: lo nuevo desde el
        ultimo mensaje visto (al reconectar)."""
        trip = await self.chat_trip(user, conversation_id)
        query = select(Message).where(Message.trip_id == trip.id, Message.hidden.is_(False))
        anchor_id = before or after
        if anchor_id is not None:
            anchor = await self.session.get(Message, anchor_id)
            if anchor is None or anchor.trip_id != trip.id:
                raise NotFoundError("message")
            if before is not None:
                query = query.where(
                    or_(
                        Message.sent_at < anchor.sent_at,
                        and_(Message.sent_at == anchor.sent_at, Message.id < anchor.id),
                    )
                )
            else:
                query = query.where(
                    or_(
                        Message.sent_at > anchor.sent_at,
                        and_(Message.sent_at == anchor.sent_at, Message.id > anchor.id),
                    )
                )
        if after is not None:
            rows = await self.session.scalars(
                query.order_by(Message.sent_at, Message.id).limit(limit)
            )
            return [message_out(m) for m in rows.all()]
        rows = await self.session.scalars(
            query.order_by(Message.sent_at.desc(), Message.id.desc()).limit(limit)
        )
        return [message_out(m) for m in reversed(rows.all())]

    async def unread_total(self, user: User) -> UnreadMessages:
        counts = [await self.unread_count(user, trip.id) for trip in await self.my_trips(user)]
        return UnreadMessages(unread=sum(counts), conversations=sum(1 for c in counts if c))

    # --- Escritura ------------------------------------------------------------------------

    async def send(self, user: User, conversation_id: uuid.UUID, body: str) -> MessageOut:
        trip = await self.chat_trip(user, conversation_id)
        if not is_open(trip):
            raise AppError("CONVERSATION_CLOSED", "This chat is closed", 409)
        text = body.strip()
        if not text:
            raise AppError("MESSAGE_EMPTY", "The message is empty", 422)
        message = Message(
            id=uuid.uuid4(), trip_id=trip.id, sender_id=user.id, body=text, sent_at=utcnow()
        )
        message.sender = user
        self.session.add(message)
        out = message_out(message)
        emit(
            self.session,
            conversation_channel(trip.id),
            {"type": "message", "message": out.model_dump(mode="json")},
        )
        await self.notify_others(trip, user, message.sent_at)
        await self.session.commit()
        return out

    async def notify_others(self, trip: Trip, sender: User, sent_at: datetime) -> None:
        """Un solo aviso por chat mientras el anterior siga sin leer (sin llenar la bandeja)."""
        notifications = NotificationService(self.session)
        people = {
            trip.driver_id,
            *(b.passenger_id for b in await passengers_in_chat(self.session, trip.id)),
        }
        for person in people - {sender.id}:
            pending = await self.session.scalar(
                select(Notification.id).where(
                    Notification.user_id == person,
                    Notification.kind == Kind.MESSAGE_NEW,
                    Notification.read_at.is_(None),
                    Notification.payload["conversation_id"].astext == str(trip.id),
                )
            )
            if pending is None:
                notifications.notify(
                    person,
                    Kind.MESSAGE_NEW,
                    {
                        "conversation_id": str(trip.id),
                        "sender_name": sender.full_name,
                        "since": sent_at.isoformat(),
                    },
                )

    async def mark_read(self, user: User, conversation_id: uuid.UUID) -> None:
        """Marca leido el aviso de mensajes nuevos de ese chat."""
        trip = await self.chat_trip(user, conversation_id)
        await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.kind == Kind.MESSAGE_NEW,
                Notification.read_at.is_(None),
                Notification.payload["conversation_id"].astext == str(trip.id),
            )
            .values(read_at=utcnow())
        )
        await self.session.commit()


# --- Retencion (job) -----------------------------------------------------------------------


async def purge_chat(session: AsyncSession) -> int:
    """Diario: borra los mensajes de los viajes que terminaron (o se cancelaron) hace mas de
    chat_retention_days. Un viaje sin cerrar cuenta desde su llegada estimada."""
    days = int(await SettingsService(session).get("chat_retention_days"))
    limit = utcnow() - timedelta(days=days)
    ended = select(Trip.id).where(
        or_(
            Trip.finished_at < limit,
            Trip.cancelled_at < limit,
            Trip.departs_at + func.make_interval(0, 0, 0, 0, 0, 0, Trip.est_duration_s) < limit,
        ),
        Trip.status.not_in((TripStatus.SCHEDULED, TripStatus.IN_PROGRESS)),
    )
    result = await session.execute(delete(Message).where(Message.trip_id.in_(ended)))
    await session.commit()
    removed = int(result.rowcount or 0)  # type: ignore[attr-defined]
    logger.info("chat_purged", messages=removed)
    return removed
