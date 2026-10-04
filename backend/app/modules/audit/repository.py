import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditFilters


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, entry: AuditLog) -> None:
        self.session.add(entry)

    async def list_all(
        self,
        filters: AuditFilters,
        limit: int,
        after: tuple[datetime, uuid.UUID] | None,
    ) -> list[AuditLog]:
        """Mas recientes primero. after es el ultimo (created_at, id) de la pagina anterior."""
        query = select(AuditLog)
        if filters.entity:
            query = query.where(AuditLog.entity == filters.entity)
        if filters.entity_id:
            query = query.where(AuditLog.entity_id == filters.entity_id)
        if filters.actor_id:
            query = query.where(AuditLog.actor_id == filters.actor_id)
        if filters.action:
            query = query.where(AuditLog.action == filters.action)
        if filters.since:
            query = query.where(AuditLog.created_at >= filters.since)
        if filters.until:
            query = query.where(AuditLog.created_at < filters.until)
        if after:
            created_at, row_id = after
            query = query.where(
                or_(
                    AuditLog.created_at < created_at,
                    and_(AuditLog.created_at == created_at, AuditLog.id < row_id),
                )
            )
        query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
        return list((await self.session.scalars(query)).all())
