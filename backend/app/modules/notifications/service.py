"""Notificaciones internas: se guardan en la bandeja y llegan en vivo por WebSocket."""

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.errors import NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.core.realtime import emit, user_channel
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationOut


class Kind:
    """Tipos estables; la interfaz los traduce con notifications.kinds.<tipo>."""

    DOCUMENT_APPROVED = "document_approved"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_EXPIRED = "document_expired"
    LICENSE_APPROVED = "license_approved"
    LICENSE_REJECTED = "license_rejected"
    ACCOUNT_REVALIDATION_REQUIRED = "account_revalidation_required"
    ROLE_CHANGED = "role_changed"
    TRIP_PICO_PLACA_CANCELLED = "trip_pico_placa_cancelled"
    TRIP_PICO_PLACA_RESTORED = "trip_pico_placa_restored"
    # Reservas (paso 8). Al conductor:
    BOOKING_REQUESTED = "booking_requested"
    BOOKING_WITHDRAWN = "booking_withdrawn"
    BOOKING_CANCELLED_BY_PASSENGER = "booking_cancelled_by_passenger"
    CANCELLATION_REQUESTED = "cancellation_requested"
    SUBSCRIPTION_REQUESTED = "subscription_requested"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    # Al pasajero:
    BOOKING_ACCEPTED = "booking_accepted"
    BOOKING_REJECTED = "booking_rejected"
    BOOKING_EXPIRED = "booking_expired"
    BOOKING_CANCELLED_BY_DRIVER = "booking_cancelled_by_driver"
    BOOKING_AUTO_CANCELLED_LATE = "booking_auto_cancelled_late"
    BOOKING_PICO_PLACA_CANCELLED = "booking_pico_placa_cancelled"
    CANCELLATION_ACCEPTED = "cancellation_accepted"
    CANCELLATION_REJECTED = "cancellation_rejected"
    TRIP_CHANGED = "trip_changed"
    SUBSCRIPTION_ACCEPTED = "subscription_accepted"
    SUBSCRIPTION_REJECTED = "subscription_rejected"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_ENDED = "subscription_ended"
    WAITLIST_OFFER = "waitlist_offer"
    WAITLIST_OFFER_EXPIRED = "waitlist_offer_expired"
    # Chat (paso 9): uno por conversacion mientras haya mensajes sin leer.
    MESSAGE_NEW = "message_new"
    # Ciclo del viaje y seguridad (paso 10).
    TRIP_REMINDER = "trip_reminder"
    TRIP_REMINDER_DRIVER = "trip_reminder_driver"
    TRIP_STARTED = "trip_started"
    TRIP_FINISHED = "trip_finished"
    TRIP_NOT_HELD = "trip_not_held"
    PASSENGER_NO_SHOW = "passenger_no_show"
    BOOKING_SUSPENDED = "booking_suspended"
    EMERGENCY_ALERT = "emergency_alert"
    # Calificaciones (paso 11).
    RATING_PENDING = "rating_pending"
    RATING_REMINDER = "rating_reminder"
    RATING_RECEIVED = "rating_received"


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def notify(self, user_id: uuid.UUID, kind: str, payload: dict[str, Any] | None = None) -> None:
        """Agrega la notificacion a la transaccion en curso (sin commit). Al confirmarse llega
        en vivo por el canal del usuario."""
        notification = Notification(
            id=uuid.uuid4(), user_id=user_id, kind=kind, payload=payload or {}
        )
        self.session.add(notification)
        emit(
            self.session,
            user_channel(user_id),
            {
                "type": "notification",
                "notification": {
                    "id": str(notification.id),
                    "kind": kind,
                    "payload": notification.payload,
                    "read_at": None,
                    "created_at": utcnow().isoformat(),
                },
            },
        )

    async def list_for(
        self, user_id: uuid.UUID, limit: int, cursor: str | None, unread_only: bool
    ) -> Page[NotificationOut]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        if cursor:
            created_at, row_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    Notification.created_at < created_at,
                    and_(Notification.created_at == created_at, Notification.id < row_id),
                )
            )
        query = query.order_by(Notification.created_at.desc(), Notification.id.desc())
        rows = list((await self.session.scalars(query.limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return Page(
            items=[NotificationOut.model_validate(row) for row in rows],
            next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None,
        )

    async def unread_count(self, user_id: uuid.UUID) -> int:
        query = select(func.count()).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
        return int(await self.session.scalar(query) or 0)

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        notification = await self.session.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotFoundError("notification")
        if notification.read_at is None:
            notification.read_at = utcnow()
            # Las demas pestanas y dispositivos actualizan su contador.
            emit(
                self.session,
                user_channel(user_id),
                {"type": "notification.read", "id": str(notification_id)},
            )
            await self.session.commit()

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=utcnow())
        )
        emit(self.session, user_channel(user_id), {"type": "notification.read_all"})
        await self.session.commit()
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
