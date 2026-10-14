"""Efectos de los cambios de un viaje sobre sus reservas (seccion 7.2 y 7.5.1).

Lo usan viajes, pico y placa, la administracion y los jobs. Ninguna funcion hace commit.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus
from app.modules.bookings.matching import apply_meeting, meeting_points
from app.modules.bookings.models import HOLDING_STATUSES
from app.modules.bookings.queries import active_bookings
from app.modules.notifications.service import Kind, NotificationService
from app.modules.search.service import Point
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip

# Estado final de las reservas activas segun el motivo, con el aviso al pasajero.
END_KINDS = {
    BookingStatus.CANCELLED_BY_DRIVER: Kind.BOOKING_CANCELLED_BY_DRIVER,
    BookingStatus.AUTO_CANCELLED_PICO_PLACA: Kind.BOOKING_PICO_PLACA_CANCELLED,
    BookingStatus.AUTO_CANCELLED_LATE: Kind.BOOKING_AUTO_CANCELLED_LATE,
    # Viaje no realizado: nadie lo inicio a tiempo.
    BookingStatus.EXPIRED: Kind.BOOKING_EXPIRED,
}


async def end_trip_bookings(
    session: AsyncSession, trip: Trip, status: BookingStatus, reason: str | None = None
) -> int:
    """Termina las reservas activas del viaje (las solicitudes sin aceptar tambien, y una
    cancelacion tardia pendiente queda resuelta: el pasajero ya no viaja). El chat del viaje
    queda cerrado porque el viaje ya no esta programado ni en curso."""
    now = utcnow()
    notifications = NotificationService(session)
    bookings = await active_bookings(session, trip.id)
    for booking in bookings:
        booking.status = status
        booking.cancelled_at = now
        booking.cancel_reason = reason
        notifications.notify(
            booking.passenger_id,
            END_KINDS[status],
            {"trip_id": str(trip.id), "booking_id": str(booking.id), "reason": reason},
        )
    return len(bookings)


async def trip_changed(session: AsyncSession, trip: Trip) -> int:
    """El conductor cambio hora, ruta o vehiculo: se recalcula el punto de encuentro de cada
    reserva activa, los aceptados pueden cancelar sin penalizacion y todos reciben aviso."""
    await session.flush()
    radius = int(await SettingsService(session).get("search_radius_meters"))
    notifications = NotificationService(session)
    bookings = await active_bookings(session, trip.id)
    for booking in bookings:
        meeting = await meeting_points(
            session,
            trip,
            Point(booking.pickup_place.lat, booking.pickup_place.lon),
            Point(booking.dropoff_place.lat, booking.dropoff_place.lon),
            radius,
        )
        apply_meeting(booking, meeting)
        if booking.status in HOLDING_STATUSES:
            booking.penalty_free = True
        else:
            booking.expires_at = min(booking.expires_at, trip.departs_at)
        notifications.notify(
            booking.passenger_id,
            Kind.TRIP_CHANGED,
            {"trip_id": str(trip.id), "booking_id": str(booking.id)},
        )
    return len(bookings)
