"""Jobs de reservas: vencimientos y retraso del conductor (seccion 9)."""

from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, TripStatus
from app.modules.bookings.lifecycle import end_trip_bookings
from app.modules.bookings.models import Booking
from app.modules.notifications.service import Kind, NotificationService
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip

logger = structlog.get_logger("bookings")


async def expire_pending(session: AsyncSession) -> dict[str, int]:
    """Cada 5 minutos.

    - Solicitudes sin respuesta a tiempo pasan a expired.
    - Cancelaciones tardias que el conductor no decidio antes de salir se rechazan: la
      reserva sigue aceptada (el abordaje o no-show lo decide el conductor en el viaje).
    """
    now = utcnow()
    notifications = NotificationService(session)

    bookings = (
        await session.scalars(
            select(Booking).where(
                Booking.status == BookingStatus.REQUESTED, Booking.expires_at <= now
            )
        )
    ).all()
    for booking in bookings:
        booking.status = BookingStatus.EXPIRED
        notifications.notify(
            booking.passenger_id,
            Kind.BOOKING_EXPIRED,
            {"trip_id": str(booking.trip_id), "booking_id": str(booking.id)},
        )

    stale = (
        await session.scalars(
            select(Booking)
            .join(Trip, Trip.id == Booking.trip_id)
            .where(Booking.status == BookingStatus.CANCEL_REQUESTED, Trip.departs_at <= now)
        )
    ).all()
    for booking in stale:
        booking.status = BookingStatus.ACCEPTED
        booking.cancel_reason = None
        notifications.notify(
            booking.passenger_id,
            Kind.CANCELLATION_REJECTED,
            {"trip_id": str(booking.trip_id), "booking_id": str(booking.id)},
        )

    await session.commit()
    result = {"bookings": len(bookings), "cancellations": len(stale)}
    logger.info("pending_expired", **result)
    return result


async def auto_cancel_late_driver(session: AsyncSession) -> int:
    """Cada minuto: si pasaron driver_late_minutes desde la hora y el viaje no inicio, las
    reservas activas pasan a auto_cancelled_late (sin penalizacion) y se avisa."""
    minutes = int(await SettingsService(session).get("driver_late_minutes"))
    limit = utcnow() - timedelta(minutes=minutes)
    trips = (
        await session.scalars(
            select(Trip).where(
                Trip.status == TripStatus.SCHEDULED,
                Trip.deleted_at.is_(None),
                Trip.departs_at <= limit,
                Trip.id.in_(
                    select(Booking.trip_id).where(
                        Booking.status.in_(
                            (
                                BookingStatus.REQUESTED,
                                BookingStatus.ACCEPTED,
                                BookingStatus.CANCEL_REQUESTED,
                            )
                        )
                    )
                ),
            )
        )
    ).all()
    total = 0
    for trip in trips:
        total += await end_trip_bookings(session, trip, BookingStatus.AUTO_CANCELLED_LATE)
    await session.commit()
    if total:
        logger.info("late_driver_cancelled", trips=len(trips), bookings=total)
    return total
