"""Consulta de sanciones vigentes."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import SuspensionKind
from app.modules.suspensions.models import Suspension


async def active_suspension(
    session: AsyncSession, user_id: uuid.UUID, kind: SuspensionKind
) -> Suspension | None:
    """La sancion vigente que termina mas tarde (o la indefinida)."""
    now = utcnow()
    query = (
        select(Suspension)
        .where(
            Suspension.user_id == user_id,
            Suspension.kind == kind,
            Suspension.starts_at <= now,
            or_(Suspension.ends_at.is_(None), Suspension.ends_at > now),
        )
        .order_by(Suspension.ends_at.desc().nulls_first())
        .limit(1)
    )
    return await session.scalar(query)
