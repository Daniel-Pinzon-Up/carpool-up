"""Gestion de usuarios (seccion 13): buscar, ver, suspender, reactivar y bloquear.

Un administrador gestiona pasajeros y conductores; el superadmin ademas a los
administradores. Nadie actua sobre el superadmin ni sobre si mismo. Todo queda en la
auditoria.
"""

import uuid
from datetime import timedelta

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import utcnow
from app.core.enums import (
    BookingStatus,
    SubscriptionStatus,
    SuspensionKind,
    TripStatus,
    UserRole,
    UserStatus,
    WaitlistStatus,
)
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.admin.schemas import (
    AdminUserDetail,
    AdminUserRow,
    SuspensionOut,
)
from app.modules.audit.service import AuditService
from app.modules.auth.repository import SessionRepository
from app.modules.bookings.lifecycle import end_trip_bookings
from app.modules.bookings.models import ACTIVE_STATUSES, Booking, SeriesSubscription
from app.modules.chat.membership import leave_trip_chat
from app.modules.documents.models import DriverLicense, IdentityDocument
from app.modules.notifications.service import Kind, NotificationService
from app.modules.stats.summary import stats_for
from app.modules.suspensions.models import Suspension
from app.modules.trips.models import Trip
from app.modules.trips.service import mark_cancelled
from app.modules.users.models import User
from app.modules.waitlist.models import OPEN_STATUSES, WaitlistEntry
from app.modules.waitlist.offers import offer_next

logger = structlog.get_logger("admin")

MANAGED_BY_ADMIN = (UserRole.PASSENGER, UserRole.DRIVER)


def row(user: User) -> AdminUserRow:
    return AdminUserRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
        program=user.program,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def suspension_out(s: Suspension) -> SuspensionOut:
    return SuspensionOut(
        id=s.id,
        kind=s.kind,
        reason=s.reason,
        starts_at=s.starts_at,
        ends_at=s.ends_at,
        automatic=s.created_by is None,
    )


async def withdraw_from_trips(session: AsyncSession, user: User, reason: str) -> dict[str, int]:
    """Una cuenta suspendida o bloqueada deja de viajar: se cancelan sus viajes programados
    (con aviso a los pasajeros), sus reservas y suscripciones vigentes y su lista de espera."""
    now = utcnow()
    trips = (
        await session.scalars(
            select(Trip).where(
                Trip.driver_id == user.id,
                Trip.status == TripStatus.SCHEDULED,
                Trip.deleted_at.is_(None),
                Trip.departs_at > now,
            )
        )
    ).all()
    for trip in trips:
        mark_cancelled(trip, reason)
        await end_trip_bookings(session, trip, BookingStatus.CANCELLED_BY_DRIVER, reason)
    notifications = NotificationService(session)
    bookings = (
        await session.scalars(
            select(Booking)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(
                Booking.passenger_id == user.id,
                Booking.status.in_(ACTIVE_STATUSES),
                Trip.status == TripStatus.SCHEDULED,
            )
        )
    ).all()
    for booking in bookings:
        held = booking.status != BookingStatus.REQUESTED
        booking.status = BookingStatus.CANCELLED_BY_PASSENGER
        booking.cancelled_at = now
        booking.cancel_reason = reason
        notifications.notify(
            booking.trip.driver_id,
            Kind.BOOKING_CANCELLED_BY_PASSENGER if held else Kind.BOOKING_WITHDRAWN,
            {"trip_id": str(booking.trip_id), "booking_id": str(booking.id)},
        )
        if held:
            await leave_trip_chat(session, booking)
            await session.flush()
            await offer_next(session, booking.trip)
    subscriptions = (
        await session.scalars(
            select(SeriesSubscription).where(
                SeriesSubscription.passenger_id == user.id,
                SeriesSubscription.status.in_(
                    (SubscriptionStatus.REQUESTED, SubscriptionStatus.ACTIVE)
                ),
            )
        )
    ).all()
    for sub in subscriptions:
        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_at = now
    entries = (
        await session.scalars(
            select(WaitlistEntry).where(
                WaitlistEntry.passenger_id == user.id, WaitlistEntry.status.in_(OPEN_STATUSES)
            )
        )
    ).all()
    for entry in entries:
        entry.status = WaitlistStatus.LEFT
    return {"trips": len(trips), "bookings": len(bookings), "subscriptions": len(subscriptions)}


class AdminUserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)

    async def search(
        self,
        q: str | None,
        role: UserRole | None,
        status: UserStatus | None,
        limit: int,
        cursor: str | None,
    ) -> Page[AdminUserRow]:
        query = select(User).where(User.deleted_at.is_(None))
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
        if role is not None:
            query = query.where(User.role == role)
        if status is not None:
            query = query.where(User.status == status)
        if cursor:
            at, row_id = decode_cursor(cursor)
            query = query.where(
                or_(User.created_at < at, and_(User.created_at == at, User.id < row_id))
            )
        users = list(
            (
                await self.session.scalars(
                    query.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(users) > limit
        users = users[:limit]
        return Page(
            items=[row(u) for u in users],
            next_cursor=encode_cursor(users[-1].created_at, users[-1].id) if has_more else None,
        )

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundError("user")
        return user

    async def detail(self, user_id: uuid.UUID) -> AdminUserDetail:
        user = await self.get(user_id)
        stats = (await stats_for(self.session, [user.id])).get(user.id)
        suspensions = (
            await self.session.scalars(
                select(Suspension)
                .where(Suspension.user_id == user.id)
                .order_by(Suspension.starts_at.desc())
                .limit(20)
            )
        ).all()
        document = await self.session.scalar(
            select(IdentityDocument)
            .where(IdentityDocument.user_id == user.id)
            .order_by(IdentityDocument.created_at.desc())
            .limit(1)
        )
        license_ = await self.session.scalar(
            select(DriverLicense).where(DriverLicense.user_id == user.id)
        )
        active_bookings = await self.session.scalar(
            select(func.count()).where(
                Booking.passenger_id == user.id, Booking.status.in_(ACTIVE_STATUSES)
            )
        )
        upcoming_trips = await self.session.scalar(
            select(func.count()).where(
                Trip.driver_id == user.id,
                Trip.status == TripStatus.SCHEDULED,
                Trip.departs_at > utcnow(),
                Trip.deleted_at.is_(None),
            )
        )
        now = utcnow()
        return AdminUserDetail(
            **row(user).model_dump(),
            sex=user.sex,
            document_status=document.status if document else None,
            license_status=license_.status if license_ else None,
            license_expires_on=license_.expires_on if license_ else None,
            rating=stats.rating_avg if stats else None,
            rating_count=stats.rating_count if stats else 0,
            trips_as_driver=stats.trips_as_driver if stats else 0,
            trips_as_passenger=stats.trips_as_passenger if stats else 0,
            driver_cancellations=stats.driver_cancellations if stats else 0,
            passenger_no_shows=stats.passenger_no_shows if stats else 0,
            active_bookings=int(active_bookings or 0),
            upcoming_trips=int(upcoming_trips or 0),
            suspensions=[suspension_out(s) for s in suspensions],
            active_ban=next(
                (
                    suspension_out(s)
                    for s in suspensions
                    if s.kind == SuspensionKind.BOOKING_BAN
                    and s.starts_at <= now
                    and (s.ends_at is None or s.ends_at > now)
                ),
                None,
            ),
        )

    async def manageable(self, actor: Actor, user_id: uuid.UUID) -> User:
        user = await self.get(user_id)
        if user.id == actor.user.id:
            raise ForbiddenError("You cannot act on your own account")
        if user.role == UserRole.SUPERADMIN:
            raise ForbiddenError("The superadmin cannot be managed")
        if user.role == UserRole.ADMIN and actor.user.role != UserRole.SUPERADMIN:
            raise ForbiddenError("Only the superadmin manages administrators")
        return user

    async def suspend(
        self, actor: Actor, user_id: uuid.UUID, reason: str, days: int | None
    ) -> AdminUserDetail:
        """Suspension de cuenta: puede entrar y ver su estado, pero no usar la app. Con dias
        vuelve sola a activa al vencer; sin dias, hasta que la reactiven."""
        user = await self.manageable(actor, user_id)
        if user.status in (UserStatus.BLOCKED, UserStatus.SUSPENDED):
            raise AppError(
                "USER_STATUS_INVALID",
                "The account cannot be suspended now",
                409,
                {"status": user.status},
            )
        now = utcnow()
        before = {"status": user.status.value}
        user.status = UserStatus.SUSPENDED
        ends_at = now + timedelta(days=days) if days else None
        self.session.add(
            Suspension(
                user_id=user.id,
                kind=SuspensionKind.ACCOUNT,
                reason=reason,
                starts_at=now,
                ends_at=ends_at,
                created_by=actor.user.id,
            )
        )
        withdrawn = await withdraw_from_trips(self.session, user, reason)
        self.audit.record(
            actor,
            "user.suspend",
            "user",
            user.id,
            before,
            {"status": user.status.value, "reason": reason, "days": days, **withdrawn},
        )
        self.notifications.notify(
            user.id,
            Kind.ACCOUNT_SUSPENDED,
            {"reason": reason, "ends_at": ends_at.isoformat() if ends_at else None},
        )
        await self.session.commit()
        logger.info("user_suspended", days=days)
        return await self.detail(user.id)

    async def reinstate(
        self, actor: Actor, user_id: uuid.UUID, reason: str | None
    ) -> AdminUserDetail:
        user = await self.manageable(actor, user_id)
        if user.status not in (UserStatus.SUSPENDED, UserStatus.BLOCKED):
            raise AppError(
                "USER_STATUS_INVALID",
                "The account is not suspended or blocked",
                409,
                {"status": user.status},
            )
        now = utcnow()
        before = {"status": user.status.value}
        user.status = UserStatus.ACTIVE
        open_ = (
            await self.session.scalars(
                select(Suspension).where(
                    Suspension.user_id == user.id,
                    Suspension.kind == SuspensionKind.ACCOUNT,
                    or_(Suspension.ends_at.is_(None), Suspension.ends_at > now),
                )
            )
        ).all()
        for suspension in open_:
            suspension.ends_at = max(now, suspension.starts_at + timedelta(seconds=1))
        self.audit.record(
            actor,
            "user.reinstate",
            "user",
            user.id,
            before,
            {"status": user.status.value, "reason": reason},
        )
        self.notifications.notify(user.id, Kind.ACCOUNT_REINSTATED, {})
        await self.session.commit()
        return await self.detail(user.id)

    async def block(self, actor: Actor, user_id: uuid.UUID, reason: str) -> AdminUserDetail:
        """Definitivo: cierra todas sus sesiones y ya no puede entrar."""
        user = await self.manageable(actor, user_id)
        if user.status == UserStatus.BLOCKED:
            raise AppError("USER_STATUS_INVALID", "The account is already blocked", 409)
        before = {"status": user.status.value}
        user.status = UserStatus.BLOCKED
        await SessionRepository(self.session).revoke_all(user.id, utcnow())
        withdrawn = await withdraw_from_trips(self.session, user, reason)
        self.audit.record(
            actor,
            "user.block",
            "user",
            user.id,
            before,
            {"status": user.status.value, "reason": reason, **withdrawn},
        )
        await self.session.commit()
        return await self.detail(user.id)

    async def end_suspension(
        self, actor: Actor, suspension_id: uuid.UUID, reason: str | None
    ) -> AdminUserDetail:
        """Levanta una sancion de reservas (por ejemplo, un no-show mal marcado)."""
        suspension = await self.session.get(Suspension, suspension_id)
        if suspension is None or suspension.kind != SuspensionKind.BOOKING_BAN:
            raise NotFoundError("suspension")
        user = await self.manageable(actor, suspension.user_id)
        now = utcnow()
        if suspension.ends_at is not None and suspension.ends_at <= now:
            raise AppError("SUSPENSION_ENDED", "The suspension already ended", 409)
        before = {"ends_at": suspension.ends_at.isoformat() if suspension.ends_at else None}
        suspension.ends_at = max(now, suspension.starts_at + timedelta(seconds=1))
        self.audit.record(
            actor,
            "suspension.end",
            "suspension",
            suspension.id,
            before,
            {"ends_at": suspension.ends_at.isoformat(), "reason": reason},
        )
        self.notifications.notify(user.id, Kind.BOOKING_BAN_LIFTED, {})
        await self.session.commit()
        return await self.detail(user.id)


async def end_expired_account_suspensions(session: AsyncSession) -> int:
    """Cada 15 minutos: las cuentas suspendidas con todas sus suspensiones vencidas vuelven
    a activa (las indefinidas esperan a un administrador)."""
    now = utcnow()
    users = (await session.scalars(select(User).where(User.status == UserStatus.SUSPENDED))).all()
    restored = 0
    notifications = NotificationService(session)
    for user in users:
        pending = await session.scalar(
            select(func.count()).where(
                Suspension.user_id == user.id,
                Suspension.kind == SuspensionKind.ACCOUNT,
                or_(Suspension.ends_at.is_(None), Suspension.ends_at > now),
            )
        )
        if int(pending or 0) == 0:
            user.status = UserStatus.ACTIVE
            notifications.notify(user.id, Kind.ACCOUNT_REINSTATED, {})
            AuditService(session).record(
                None,
                "user.reinstate_auto",
                "user",
                user.id,
                {"status": "suspended"},
                {"status": "active"},
            )
            restored += 1
    await session.commit()
    return restored
