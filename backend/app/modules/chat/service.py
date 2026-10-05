"""Chat: lista de conversaciones, historial, envio y lectura (secciones 5.8 y 9)."""

import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today, utcnow
from app.core.enums import ConversationKind, SeriesStatus, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.realtime import conversation_channel, emit
from app.modules.chat.models import Conversation, ConversationMember, Message
from app.modules.chat.schemas import (
    ConversationOut,
    MemberOut,
    MessageOut,
    UnreadMessages,
)
from app.modules.notifications.models import Notification
from app.modules.notifications.service import Kind, NotificationService
from app.modules.series.models import TripSeries
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.users.models import User

logger = structlog.get_logger("chat")

HISTORY_LIMIT = 50


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=message.sender.full_name,
        body=message.body,
        sent_at=message.sent_at,
    )


def title_of(conversation: Conversation) -> tuple[str, datetime | None]:
    if conversation.trip is not None:
        trip = conversation.trip
        return f"{trip.stops[0].place.name} - {trip.stops[-1].place.name}", trip.departs_at
    series = conversation.series
    assert series is not None  # noqa: S101 - restriccion kind_shape
    return f"{series.stops[0].place.name} - {series.stops[-1].place.name}", None


def _unread_since(member: ConversationMember) -> datetime:
    """Lo escrito despues de entrar y despues de la ultima lectura."""
    return max(filter(None, [member.joined_at, member.last_read_at]))


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Acceso -------------------------------------------------------------------------

    async def membership(
        self, user: User, conversation_id: uuid.UUID
    ) -> tuple[Conversation, ConversationMember]:
        """Solo los miembros que no han salido ven el chat."""
        member = await self.session.get(ConversationMember, (conversation_id, user.id))
        if member is None or member.left_at is not None:
            raise NotFoundError("conversation")
        conversation = await self.session.get(Conversation, conversation_id)
        if conversation is None:
            raise NotFoundError("conversation")
        return conversation, member

    async def active_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Chats que la conexion WebSocket del usuario debe escuchar."""
        rows = await self.session.scalars(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == user_id, ConversationMember.left_at.is_(None)
            )
        )
        return list(rows.all())

    # --- Lectura ------------------------------------------------------------------------

    async def unread_count(self, member: ConversationMember) -> int:
        count = await self.session.scalar(
            select(func.count()).where(
                Message.conversation_id == member.conversation_id,
                Message.sender_id != member.user_id,
                Message.hidden.is_(False),
                Message.sent_at > _unread_since(member),
            )
        )
        return int(count or 0)

    async def last_message(self, conversation_id: uuid.UUID) -> Message | None:
        return await self.session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.hidden.is_(False))
            .order_by(Message.sent_at.desc(), Message.id.desc())
            .limit(1)
        )

    async def out(self, conversation: Conversation, member: ConversationMember) -> ConversationOut:
        title, departs_at = title_of(conversation)
        members = [m for m in conversation.members if m.left_at is None]
        counterpart = None
        if conversation.kind == ConversationKind.DIRECT:
            other = (
                conversation.passenger
                if member.user_id == conversation.driver_id
                else conversation.driver
            )
            counterpart = other.full_name if other is not None else None
        last = await self.last_message(conversation.id)
        return ConversationOut(
            id=conversation.id,
            kind=conversation.kind,
            trip_id=conversation.trip_id,
            series_id=conversation.series_id,
            title=title,
            departs_at=departs_at,
            counterpart=counterpart,
            members=[
                MemberOut(
                    id=m.user_id,
                    full_name=m.user.full_name,
                    is_driver=m.user_id == conversation.driver_id,
                )
                for m in sorted(
                    members, key=lambda m: (m.user_id != conversation.driver_id, m.joined_at)
                )
            ],
            last_message=message_out(last) if last is not None else None,
            unread=await self.unread_count(member),
            closed=conversation.closed_at is not None,
        )

    async def list_for(self, user: User) -> list[ConversationOut]:
        """Chats abiertos y cerrados (hasta que se borran), con mensajes nuevos primero."""
        members = (
            await self.session.scalars(
                select(ConversationMember).where(
                    ConversationMember.user_id == user.id, ConversationMember.left_at.is_(None)
                )
            )
        ).all()
        outs = []
        for member in members:
            conversation = await self.session.get(Conversation, member.conversation_id)
            if conversation is not None:
                outs.append(await self.out(conversation, member))

        def activity(item: ConversationOut) -> float:
            moment = item.last_message.sent_at if item.last_message else item.departs_at
            return moment.timestamp() if moment else 0.0

        return sorted(outs, key=lambda item: (item.closed, -activity(item)))

    async def get(self, user: User, conversation_id: uuid.UUID) -> ConversationOut:
        conversation, member = await self.membership(user, conversation_id)
        return await self.out(conversation, member)

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
        await self.membership(user, conversation_id)
        query = select(Message).where(
            Message.conversation_id == conversation_id, Message.hidden.is_(False)
        )
        anchor_id = before or after
        if anchor_id is not None:
            anchor = await self.session.get(Message, anchor_id)
            if anchor is None or anchor.conversation_id != conversation_id:
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
        members = (
            await self.session.scalars(
                select(ConversationMember).where(
                    ConversationMember.user_id == user.id, ConversationMember.left_at.is_(None)
                )
            )
        ).all()
        counts = [await self.unread_count(member) for member in members]
        return UnreadMessages(unread=sum(counts), conversations=sum(1 for c in counts if c))

    async def for_trip(self, user: User, trip_id: uuid.UUID) -> uuid.UUID | None:
        """Chat grupal del viaje si quien consulta es miembro."""
        return await self.session.scalar(
            select(Conversation.id)
            .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
            .where(
                Conversation.kind == ConversationKind.TRIP_GROUP,
                Conversation.trip_id == trip_id,
                ConversationMember.user_id == user.id,
                ConversationMember.left_at.is_(None),
            )
        )

    # --- Escritura ------------------------------------------------------------------------

    async def send(self, user: User, conversation_id: uuid.UUID, body: str) -> MessageOut:
        conversation, member = await self.membership(user, conversation_id)
        if conversation.closed_at is not None:
            raise AppError("CONVERSATION_CLOSED", "This chat is closed", 409)
        text = body.strip()
        if not text:
            raise AppError("MESSAGE_EMPTY", "The message is empty", 422)
        message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            sender_id=user.id,
            body=text,
            sent_at=utcnow(),
        )
        message.sender = user
        self.session.add(message)
        member.last_read_at = message.sent_at
        out = message_out(message)
        emit(
            self.session,
            conversation_channel(conversation.id),
            {"type": "message", "message": out.model_dump(mode="json")},
        )
        await self.notify_others(conversation, user, out)
        await self.session.commit()
        return out

    async def notify_others(
        self, conversation: Conversation, sender: User, message: MessageOut
    ) -> None:
        """Un solo aviso por chat mientras el anterior siga sin leer (sin llenar la bandeja)."""
        notifications = NotificationService(self.session)
        for member in conversation.members:
            if member.user_id == sender.id or member.left_at is not None:
                continue
            pending = await self.session.scalar(
                select(Notification.id).where(
                    Notification.user_id == member.user_id,
                    Notification.kind == Kind.MESSAGE_NEW,
                    Notification.read_at.is_(None),
                    Notification.payload["conversation_id"].astext == str(conversation.id),
                )
            )
            if pending is None:
                notifications.notify(
                    member.user_id,
                    Kind.MESSAGE_NEW,
                    {
                        "conversation_id": str(conversation.id),
                        "sender_name": sender.full_name,
                    },
                )

    async def mark_read(self, user: User, conversation_id: uuid.UUID) -> None:
        """Marca el chat como leido, y su aviso de mensajes nuevos tambien."""
        _, member = await self.membership(user, conversation_id)
        member.last_read_at = utcnow()
        await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.kind == Kind.MESSAGE_NEW,
                Notification.read_at.is_(None),
                Notification.payload["conversation_id"].astext == str(conversation_id),
            )
            .values(read_at=utcnow())
        )
        await self.session.commit()


# --- Retencion (jobs) -------------------------------------------------------------------


async def close_finished_conversations(session: AsyncSession) -> int:
    """Diario: cierra los chats de viajes que ya terminaron (o se cancelaron) y de series que
    ya no estan activas. Un viaje se da por terminado 3 horas despues de su llegada estimada
    si nadie lo cerro antes (el paso 10 lo cierra al finalizar)."""
    now = utcnow()
    ended_trip = or_(
        Trip.status.in_(
            (
                TripStatus.COMPLETED,
                TripStatus.CANCELLED_BY_DRIVER,
                TripStatus.CANCELLED_PICO_PLACA,
                TripStatus.NOT_HELD,
            )
        ),
        Trip.deleted_at.is_not(None),
        Trip.departs_at + func.make_interval(0, 0, 0, 0, 0, 0, Trip.est_duration_s)
        < now - timedelta(hours=3),
    )
    by_trip = await session.execute(
        update(Conversation)
        .where(
            Conversation.closed_at.is_(None),
            Conversation.series_id.is_(None),
            Conversation.trip_id.in_(select(Trip.id).where(ended_trip)),
        )
        .values(closed_at=now)
    )
    by_series = await session.execute(
        update(Conversation)
        .where(
            Conversation.closed_at.is_(None),
            Conversation.series_id.in_(
                select(TripSeries.id).where(
                    or_(
                        TripSeries.status != SeriesStatus.ACTIVE,
                        TripSeries.window_end < local_today(),
                    )
                )
            ),
        )
        .values(closed_at=now)
    )
    await session.commit()
    total = int(by_trip.rowcount or 0) + int(by_series.rowcount or 0)  # type: ignore[attr-defined]
    logger.info("chats_closed", total=total)
    return total


async def purge_chat(session: AsyncSession) -> int:
    """Diario: borra los chats cerrados hace mas de chat_retention_days (con sus mensajes)."""
    days = int(await SettingsService(session).get("chat_retention_days"))
    result = await session.execute(
        delete(Conversation).where(Conversation.closed_at < utcnow() - timedelta(days=days))
    )
    await session.commit()
    removed = int(result.rowcount or 0)  # type: ignore[attr-defined]
    logger.info("chats_purged", conversations=removed)
    return removed
