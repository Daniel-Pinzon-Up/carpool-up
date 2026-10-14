"""Jobs del ciclo del viaje (seccion 9): no realizados y recordatorios."""

from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, TripStatus
from app.modules.bookings.lifecycle import end_trip_bookings
from app.modules.notifications.service import Kind, NotificationService
from app.modules.settings.service import SettingsService
from app.modules.trips.lifecycle import riders
from app.modules.trips.models import Trip

logger = structlog.get_logger("trips")


async def mark_not_held(session: AsyncSession) -> int:
    """Cada 15 minutos: un viaje programado que nadie inicio trip_not_held_hours despues de
    la salida pasa a not_held y sus reservas activas vencen."""
    hours = int(await SettingsService(session).get("trip_not_held_hours"))
    trips = (
        await session.scalars(
            select(Trip).where(
                Trip.status == TripStatus.SCHEDULED,
                Trip.deleted_at.is_(None),
                Trip.departs_at < utcnow() - timedelta(hours=hours),
            )
        )
    ).all()
    notifications = NotificationService(session)
    for trip in trips:
        trip.status = TripStatus.NOT_HELD
        await end_trip_bookings(session, trip, BookingStatus.EXPIRED)
        notifications.notify(trip.driver_id, Kind.TRIP_NOT_HELD, {"trip_id": str(trip.id)})
    await session.commit()
    if trips:
        logger.info("trips_not_held", trips=len(trips))
    return len(trips)


async def send_trip_reminders(session: AsyncSession) -> int:
    """Cada 5 minutos: avisa una sola vez al conductor y a los pasajeros aceptados cuando
    faltan trip_reminder_minutes para salir."""
    minutes = int(await SettingsService(session).get("trip_reminder_minutes"))
    now = utcnow()
    trips = (
        await session.scalars(
            select(Trip).where(
                Trip.status == TripStatus.SCHEDULED,
                Trip.deleted_at.is_(None),
                Trip.reminded_at.is_(None),
                Trip.departs_at > now,
                Trip.departs_at <= now + timedelta(minutes=minutes),
            )
        )
    ).all()
    notifications = NotificationService(session)
    for trip in trips:
        payload = {"trip_id": str(trip.id), "minutes": minutes}
        notifications.notify(trip.driver_id, Kind.TRIP_REMINDER_DRIVER, payload)
        for booking in await riders(session, trip.id):
            notifications.notify(booking.passenger_id, Kind.TRIP_REMINDER, payload)
        trip.reminded_at = now
    await session.commit()
    return len(trips)
