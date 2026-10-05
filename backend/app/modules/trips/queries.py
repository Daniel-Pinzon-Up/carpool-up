"""Consultas sobre viajes que usan otros modulos (sin depender de los servicios de viajes)."""

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import TripStatus
from app.modules.trips.models import Trip


async def vehicle_has_upcoming_trips(session: AsyncSession, vehicle_id: uuid.UUID) -> bool:
    """Viajes programados a futuro o en curso con este vehiculo."""
    query = select(Trip.id).where(
        Trip.vehicle_id == vehicle_id,
        Trip.deleted_at.is_(None),
        or_(
            Trip.status == TripStatus.IN_PROGRESS,
            and_(Trip.status == TripStatus.SCHEDULED, Trip.departs_at > utcnow()),
        ),
    )
    return await session.scalar(query.limit(1)) is not None
