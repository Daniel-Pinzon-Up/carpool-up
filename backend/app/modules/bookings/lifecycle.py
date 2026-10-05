"""Efectos de los cambios de un viaje sobre sus reservas (seccion 7.2 y 7.5.1).

Lo usan viajes, series, pico y placa y los jobs. Ninguna funcion hace commit.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, CancelRequestStatus
from app.modules.bookings.matching import apply_meeting, meeting_points
from app.modules.bookings.models import HOLDING_STATUSES, Booking
from app.modules.bookings.queries import active_bookings
from app.modules.cancellations.models import CancellationRequest
from app.modules.chat.membership import close_trip_chats
from app.modules.notifications.service import Kind, NotificationService
from app.modules.search.service import Point
from app.modules.settings.service import SettingsService
from app.modules.trips.models import Trip
from app.modules.waitlist.offers import close_waitlist

# Estado final de las reservas activas segun el motivo, con el aviso al pasajero.
END_KINDS = {
    BookingStatus.CANCELLED_BY_DRIVER: Kind.BOOKING_CANCELLED_BY_DRIVER,
    BookingStatus.AUTO_CANCELLED_PICO_PLACA: Kind.BOOKING_PICO_PLACA_CANCELLED,
    BookingStatus.AUTO_CANCELLED_LATE: Kind.BOOKING_AUTO_CANCELLED_LATE,
    # Viaje no realizado: nadie lo inicio a tiempo.
    BookingStatus.EXPIRED: Kind.BOOKING_EXPIRED,
}


async def settle_pending_cancellation(
    session: AsyncSession,
    booking: Booking,
    status: CancelRequestStatus,
    by: uuid.UUID | None = None,
) -> CancellationRequest | None:
    request = await session.scalar(
        select(CancellationRequest).where(
            CancellationRequest.booking_id == booking.id,
            CancellationRequest.status == CancelRequestStatus.PENDING,
        )
    )
    if request is not None:
        request.status = status
        request.resolved_at = utcnow()
        request.resolved_by = by
    return request


async def end_trip_bookings(
    session: AsyncSession, trip: Trip, status: BookingStatus, reason: str | None = None
) -> int:
    """Termina las reservas activas del viaje y cierra su lista de espera.

    Las solicitudes sin aceptar tambien terminan con el mismo estado, y una cancelacion
    tardia pendiente se da por aceptada (el pasajero ya no viaja).
    """
    now = utcnow()
    notifications = NotificationService(session)
    bookings = await active_bookings(session, trip.id)
    for booking in bookings:
        if booking.status == BookingStatus.CANCEL_REQUESTED:
            await settle_pending_cancellation(session, booking, CancelRequestStatus.ACCEPTED)
        booking.status = status
        booking.cancelled_at = now
        booking.cancel_reason = reason
        notifications.notify(
            booking.passenger_id,
            END_KINDS[status],
            {"trip_id": str(trip.id), "booking_id": str(booking.id), "reason": reason},
        )
    await close_waitlist(session, trip.id)
    await close_trip_chats(session, trip)
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
