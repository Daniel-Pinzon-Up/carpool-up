"""Recordatorio de calificaciones antes de que cierre el plazo (job close_rating_window)."""

from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import TripStatus
from app.modules.notifications.service import Kind, NotificationService
from app.modules.ratings.models import Rating
from app.modules.ratings.service import riders_of
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip

logger = structlog.get_logger("ratings")

# Cuanto antes del cierre se envia el ultimo aviso.
REMINDER_BEFORE = timedelta(days=1)


async def remind_pending_ratings(session: AsyncSession) -> int:
    """Diario: a quien aun no califico en un viaje cuyo plazo cierra en menos de un dia le
    llega un ultimo aviso (una sola vez por viaje). El plazo se calcula desde finished_at:
    no hay nada que cerrar, al vencer simplemente ya no se acepta."""
    window = timedelta(days=int(await SettingsService(session).get("rating_window_days")))
    now = utcnow()
    trips = (
        await session.scalars(
            select(Trip).where(
                Trip.status == TripStatus.COMPLETED,
                Trip.rating_reminded_at.is_(None),
                Trip.finished_at <= now - window + REMINDER_BEFORE,
                Trip.finished_at > now - window,
            )
        )
    ).all()
    notifications = NotificationService(session)
    sent = 0
    for trip in trips:
        riders = await riders_of(session, trip.id)
        authored = {
            (author, target)
            for author, target in (
                await session.execute(
                    select(Rating.author_id, Rating.target_id).where(Rating.trip_id == trip.id)
                )
            ).all()
        }
        late = {b.passenger_id for b in riders if (b.passenger_id, trip.driver_id) not in authored}
        if any((trip.driver_id, b.passenger_id) not in authored for b in riders):
            late.add(trip.driver_id)
        for user_id in late:
            notifications.notify(user_id, Kind.RATING_REMINDER, {"trip_id": str(trip.id)})
            sent += 1
        trip.rating_reminded_at = now
    await session.commit()
    if sent:
        logger.info("rating_reminders", trips=len(trips), sent=sent)
    return sent
