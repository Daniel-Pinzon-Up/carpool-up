"""Ofertas de cupo a la lista de espera (job offer_waitlist y al liberarse cupo).

Una oferta no aparta puestos: si el pasajero confirma se crea una solicitud que el
conductor aprueba como cualquier otra. Para no ofrecer mas de lo que hay, la suma de
puestos de las ofertas vigentes nunca supera el cupo libre.
"""

import uuid
from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import TripStatus, WaitlistStatus
from app.modules.bookings.queries import seats_left
from app.modules.notifications.service import Kind, NotificationService
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.waitlist.models import OPEN_STATUSES, WaitlistEntry

logger = structlog.get_logger("waitlist")


async def open_entries(session: AsyncSession, trip_id: uuid.UUID) -> list[WaitlistEntry]:
    query = (
        select(WaitlistEntry)
        .where(WaitlistEntry.trip_id == trip_id, WaitlistEntry.status.in_(OPEN_STATUSES))
        .order_by(WaitlistEntry.position)
    )
    return list((await session.scalars(query)).all())


async def offer_next(session: AsyncSession, trip: Trip) -> int:
    """Ofrece el cupo libre a los primeros de la fila a los que les alcanza. Sin commit."""
    now = utcnow()
    if trip.status != TripStatus.SCHEDULED or trip.deleted_at is not None or trip.departs_at <= now:
        return 0
    entries = await open_entries(session, trip.id)
    if not entries:
        return 0
    await session.flush()
    free = await seats_left(session, trip)
    free -= sum(e.seats for e in entries if e.status == WaitlistStatus.OFFERED)
    minutes = int(await SettingsService(session).get("waitlist_offer_minutes"))
    notifications = NotificationService(session)
    offered = 0
    for entry in entries:
        if entry.status != WaitlistStatus.WAITING or entry.seats > free:
            continue
        entry.status = WaitlistStatus.OFFERED
        entry.offered_at = now
        entry.offer_expires_at = min(now + timedelta(minutes=minutes), trip.departs_at)
        free -= entry.seats
        offered += 1
        notifications.notify(
            entry.passenger_id,
            Kind.WAITLIST_OFFER,
            {
                "trip_id": str(trip.id),
                "waitlist_id": str(entry.id),
                "expires_at": entry.offer_expires_at.isoformat(),
            },
        )
    return offered


async def close_waitlist(session: AsyncSession, trip_id: uuid.UUID) -> None:
    """El viaje ya no se puede reservar (cancelado o pico y placa): la fila vence."""
    for entry in await open_entries(session, trip_id):
        entry.status = WaitlistStatus.EXPIRED


async def run_waitlist(session: AsyncSession) -> dict[str, int]:
    """Cada minuto: vence ofertas sin respuesta y ofrece el cupo libre a los siguientes."""
    now = utcnow()
    expired_offers = list(
        (
            await session.scalars(
                select(WaitlistEntry).where(
                    WaitlistEntry.status == WaitlistStatus.OFFERED,
                    WaitlistEntry.offer_expires_at <= now,
                )
            )
        ).all()
    )
    notifications = NotificationService(session)
    for entry in expired_offers:
        entry.status = WaitlistStatus.EXPIRED
        notifications.notify(
            entry.passenger_id, Kind.WAITLIST_OFFER_EXPIRED, {"trip_id": str(entry.trip_id)}
        )
    await session.flush()

    trip_ids = (
        await session.scalars(
            select(WaitlistEntry.trip_id)
            .where(WaitlistEntry.status == WaitlistStatus.WAITING)
            .distinct()
        )
    ).all()
    offered = 0
    for trip_id in trip_ids:
        trip = await session.get(Trip, trip_id)
        if trip is None:
            continue
        if trip.status != TripStatus.SCHEDULED or trip.departs_at <= now:
            await close_waitlist(session, trip.id)
            continue
        offered += await offer_next(session, trip)
    await session.commit()
    logger.info("waitlist_run", expired=len(expired_offers), offered=offered)
    return {"expired": len(expired_offers), "offered": offered}
