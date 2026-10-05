"""Ciclo del viaje (seccion 7.6): iniciar, abordaje, no-show y finalizar.

Iniciar habilita la ubicacion en vivo y el enlace compartido; finalizar emite los tickets
de quienes abordaron, cierra los chats del viaje y deja lista la calificacion (paso 11).
"""

import uuid
from datetime import timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import BookingStatus, CancelRequestStatus, SuspensionKind, TripStatus
from app.core.errors import AppError, NotFoundError
from app.core.realtime import emit, user_channel
from app.modules.bookings.lifecycle import settle_pending_cancellation
from app.modules.bookings.models import HOLDING_STATUSES, Booking
from app.modules.chat.membership import close_trip_chats, leave_trip_chat
from app.modules.notifications.service import Kind, NotificationService
from app.modules.pico_placa.service import PicoPlacaService
from app.modules.safety.location import forget_location, location_channel
from app.modules.safety.models import ShareLink
from app.modules.settings.service import SettingsService
from app.modules.suspensions.models import Suspension
from app.modules.suspensions.service import active_suspension
from app.modules.tickets.service import issue_ticket
from app.modules.trips.models import Trip
from app.modules.trips.planning import local_date
from app.modules.users.models import User

logger = structlog.get_logger("trips")


async def riders(session: AsyncSession, trip_id: uuid.UUID) -> list[Booking]:
    """Reservas que viajan: aceptadas (o con cancelacion tardia pendiente)."""
    rows = await session.scalars(
        select(Booking)
        .where(Booking.trip_id == trip_id, Booking.status.in_(HOLDING_STATUSES))
        .order_by(Booking.pickup_eta)
    )
    return list(rows.all())


def announce(session: AsyncSession, trip: Trip, people: list[uuid.UUID], kind: str) -> None:
    """trip.started / trip.finished por el canal de cada participante: sus conexiones
    empiezan o dejan de escuchar la ubicacion del viaje."""
    for person in {trip.driver_id, *people}:
        emit(session, user_channel(person), {"type": kind, "trip_id": str(trip.id)})


class TripLifecycle:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)
        self.notifications = NotificationService(session)

    async def own_trip(self, driver: User, trip_id: uuid.UUID) -> Trip:
        trip = await self.session.get(Trip, trip_id)
        if trip is None or trip.deleted_at is not None or trip.driver_id != driver.id:
            raise NotFoundError("trip")
        return trip

    async def start(self, driver: User, trip_id: uuid.UUID) -> Trip:
        """Desde trip_start_lead_minutes antes de la hora y nunca en pico y placa."""
        trip = await self.own_trip(driver, trip_id)
        if trip.status != TripStatus.SCHEDULED:
            raise AppError(
                "TRIP_NOT_STARTABLE", "Only scheduled trips can start", 409, {"status": trip.status}
            )
        now = utcnow()
        lead = int(await self.settings.get("trip_start_lead_minutes"))
        if now < trip.departs_at - timedelta(minutes=lead):
            raise AppError(
                "TRIP_START_TOO_EARLY",
                "It is too early to start this trip",
                409,
                {
                    "lead_minutes": lead,
                    "opens_at": (trip.departs_at - timedelta(minutes=lead)).isoformat(),
                },
            )
        late = int(await self.settings.get("trip_not_held_hours"))
        if now > trip.departs_at + timedelta(hours=late):
            raise AppError("TRIP_START_TOO_LATE", "The trip time has passed", 409)
        vehicle = trip.vehicle
        if await PicoPlacaService(self.session).is_restricted(
            vehicle.type, vehicle.plate, local_date(trip.departs_at)
        ):
            raise AppError("PICO_PLACA_RESTRICTED", "The vehicle has pico y placa today", 409)

        trip.status = TripStatus.IN_PROGRESS
        trip.started_at = now
        # Las solicitudes sin respuesta vencen al iniciar el viaje.
        pending = await self.session.scalars(
            select(Booking).where(
                Booking.trip_id == trip.id, Booking.status == BookingStatus.REQUESTED
            )
        )
        for booking in pending.all():
            booking.status = BookingStatus.EXPIRED
            self.notifications.notify(
                booking.passenger_id,
                Kind.BOOKING_EXPIRED,
                {"trip_id": str(trip.id), "booking_id": str(booking.id)},
            )
        passengers = [b.passenger_id for b in await riders(self.session, trip.id)]
        for passenger in passengers:
            self.notifications.notify(passenger, Kind.TRIP_STARTED, {"trip_id": str(trip.id)})
        announce(self.session, trip, passengers, "trip.started")
        await self.session.commit()
        logger.info("trip_started", passengers=len(passengers))
        return trip

    # --- Abordaje -------------------------------------------------------------------------

    async def rider(self, driver: User, booking_id: uuid.UUID) -> Booking:
        booking = await self.session.get(Booking, booking_id)
        if booking is None or booking.trip.driver_id != driver.id:
            raise NotFoundError("booking")
        if booking.trip.status != TripStatus.IN_PROGRESS:
            raise AppError("TRIP_NOT_IN_PROGRESS", "Start the trip first", 409)
        if booking.status not in HOLDING_STATUSES or booking.boarded_at is not None:
            raise AppError(
                "BOOKING_NOT_BOARDABLE",
                "This passenger cannot be marked",
                409,
                {"status": booking.status},
            )
        return booking

    async def board(self, driver: User, booking_id: uuid.UUID) -> Booking:
        booking = await self.rider(driver, booking_id)
        booking.boarded_at = utcnow()
        if booking.status == BookingStatus.CANCEL_REQUESTED:
            # Si viaja, la cancelacion tardia que habia pedido queda sin efecto.
            await settle_pending_cancellation(
                self.session, booking, CancelRequestStatus.REJECTED, driver.id
            )
            booking.status = BookingStatus.ACCEPTED
        await self.session.commit()
        return booking

    async def no_show(self, driver: User, booking_id: uuid.UUID) -> Booking:
        """Desde la hora de salida mas no_show_wait_minutes. Con no_show_limit no-shows en
        no_show_window_days se suspenden las reservas no_show_ban_days dias."""
        booking = await self.rider(driver, booking_id)
        now = utcnow()
        wait = int(await self.settings.get("no_show_wait_minutes"))
        if now < booking.trip.departs_at + timedelta(minutes=wait):
            raise AppError(
                "NO_SHOW_TOO_EARLY",
                "Wait a little longer before marking a no-show",
                409,
                {"wait_minutes": wait},
            )
        if booking.status == BookingStatus.CANCEL_REQUESTED:
            await settle_pending_cancellation(
                self.session, booking, CancelRequestStatus.REJECTED, driver.id
            )
        booking.status = BookingStatus.NO_SHOW
        booking.no_show_at = now
        await leave_trip_chat(self.session, booking)
        self.notifications.notify(
            booking.passenger_id,
            Kind.PASSENGER_NO_SHOW,
            {"trip_id": str(booking.trip_id), "booking_id": str(booking.id)},
        )
        await self.session.flush()
        await self.sanction(booking.passenger_id)
        await self.session.commit()
        return booking

    async def sanction(self, passenger_id: uuid.UUID) -> Suspension | None:
        limit = int(await self.settings.get("no_show_limit"))
        days = int(await self.settings.get("no_show_window_days"))
        ban_days = int(await self.settings.get("no_show_ban_days"))
        moment = utcnow()
        count = await self.session.scalar(
            select(func.count()).where(
                Booking.passenger_id == passenger_id,
                Booking.status == BookingStatus.NO_SHOW,
                Booking.no_show_at >= moment - timedelta(days=days),
            )
        )
        if int(count or 0) < limit:
            return None
        if await active_suspension(self.session, passenger_id, SuspensionKind.BOOKING_BAN):
            return None
        suspension = Suspension(
            user_id=passenger_id,
            kind=SuspensionKind.BOOKING_BAN,
            reason="no_show_limit",
            starts_at=moment,
            ends_at=moment + timedelta(days=ban_days),
            created_by=None,
        )
        self.session.add(suspension)
        self.notifications.notify(
            passenger_id,
            Kind.BOOKING_SUSPENDED,
            {
                "ends_at": suspension.ends_at.isoformat() if suspension.ends_at else None,
                "days": ban_days,
            },
        )
        logger.info("booking_ban_applied", days=ban_days)
        return suspension

    # --- Finalizar --------------------------------------------------------------------------

    async def finish(self, driver: User, trip_id: uuid.UUID) -> Trip:
        """Todos los pasajeros deben quedar marcados (abordo o no-show) antes de finalizar."""
        trip = await self.own_trip(driver, trip_id)
        if trip.status != TripStatus.IN_PROGRESS:
            raise AppError("TRIP_NOT_IN_PROGRESS", "The trip is not in progress", 409)
        bookings = await riders(self.session, trip.id)
        unmarked = [b for b in bookings if b.boarded_at is None]
        if unmarked:
            raise AppError(
                "PASSENGERS_UNMARKED",
                "Mark every passenger as boarded or no-show first",
                409,
                {"passengers": [b.passenger.full_name for b in unmarked]},
            )
        now = utcnow()
        trip.status = TripStatus.COMPLETED
        trip.finished_at = now
        for booking in bookings:
            booking.status = BookingStatus.COMPLETED
            ticket = await issue_ticket(self.session, booking)
            self.notifications.notify(
                booking.passenger_id,
                Kind.TRIP_FINISHED,
                {"trip_id": str(trip.id), "ticket_code": ticket.code},
            )
        await close_trip_chats(self.session, trip)
        extra = int(await self.settings.get("share_link_extra_minutes"))
        links = await self.session.scalars(select(ShareLink).where(ShareLink.trip_id == trip.id))
        for link in links.all():
            link.expires_at = min(link.expires_at, now + timedelta(minutes=extra))
        announce(self.session, trip, [b.passenger_id for b in bookings], "trip.finished")
        emit(
            self.session,
            location_channel(trip.id),
            {"type": "trip.finished", "trip_id": str(trip.id)},
        )
        await self.session.commit()
        await forget_location(trip.id)
        logger.info("trip_finished", passengers=len(bookings))
        return trip
