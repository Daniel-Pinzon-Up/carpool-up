"""Jobs del ciclo del viaje (seccion 9): no realizados, recordatorios y factores de trafico."""

import statistics
from collections import defaultdict
from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import LOCAL_TZ, utcnow
from app.core.enums import BookingStatus, TripStatus
from app.modules.bookings.lifecycle import end_trip_bookings
from app.modules.notifications.service import Kind, NotificationService
from app.modules.routing.models import TrafficFactor
from app.modules.routing.service import weekday_group
from app.modules.settings.service import SettingsService
from app.modules.trips.lifecycle import riders
from app.modules.trips.models import Trip

logger = structlog.get_logger("trips")

# Ventana de viajes completados que alimenta los factores y sus limites.
TRAFFIC_WINDOW_DAYS = 56
FACTOR_MIN, FACTOR_MAX = 0.5, 3.0


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


async def recompute_traffic_factors(session: AsyncSession) -> dict[str, int]:
    """Semanal: factor de cada franja (grupo de dias y hora local de salida) = mediana de
    duracion real / duracion de OSRM de los viajes completados de las ultimas 8 semanas.
    Solo cambia las franjas con traffic_factor_min_samples viajes o mas."""
    min_samples = int(await SettingsService(session).get("traffic_factor_min_samples"))
    rows = (
        await session.execute(
            select(Trip.departs_at, Trip.started_at, Trip.finished_at, Trip.osrm_duration_s).where(
                Trip.status == TripStatus.COMPLETED,
                Trip.finished_at >= utcnow() - timedelta(days=TRAFFIC_WINDOW_DAYS),
                Trip.started_at.is_not(None),
                Trip.osrm_duration_s > 0,
            )
        )
    ).all()
    ratios: dict[tuple[str, int], list[float]] = defaultdict(list)
    for departs_at, started_at, finished_at, osrm in rows:
        if started_at is None or finished_at is None or not osrm:
            continue  # Filtrados en la consulta; aqui para el tipado.
        real = (finished_at - started_at).total_seconds()
        if real <= 0:
            continue
        local = departs_at.astimezone(LOCAL_TZ)
        ratios[(weekday_group(departs_at), local.hour)].append(real / osrm)

    updated = 0
    for (group, hour), values in ratios.items():
        if len(values) < min_samples:
            continue
        factor = round(min(FACTOR_MAX, max(FACTOR_MIN, statistics.median(values))), 2)
        row = await session.scalar(
            select(TrafficFactor).where(
                TrafficFactor.weekday_group == group, TrafficFactor.hour == hour
            )
        )
        if row is None:
            session.add(
                TrafficFactor(weekday_group=group, hour=hour, factor=factor, samples=len(values))
            )
        else:
            row.factor = factor
            row.samples = len(values)
        updated += 1
    await session.commit()
    logger.info("traffic_factors_recomputed", trips=len(rows), slots=updated)
    return {"trips": len(rows), "slots": updated}
