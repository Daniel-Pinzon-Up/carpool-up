from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditEntryOut, AuditFilters
from app.modules.users.models import User


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AuditRepository(session)

    def record(
        self,
        actor: Actor | None,
        action: str,
        entity: str,
        entity_id: object | None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        """Agrega la entrada a la transaccion en curso; se confirma junto con el cambio auditado."""
        self.repo.add(
            AuditLog(
                actor_id=actor.user.id if actor else None,
                ip=actor.ip if actor else None,
                action=action,
                entity=entity,
                entity_id=str(entity_id) if entity_id is not None else None,
                before=before,
                after=after,
            )
        )

    async def list_all(
        self, filters: AuditFilters, limit: int, cursor: str | None
    ) -> Page[AuditEntryOut]:
        after = decode_cursor(cursor) if cursor else None
        rows = await self.repo.list_all(filters, limit + 1, after)
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
        # Nombre de quien actuo (nulo para los jobs automaticos).
        actor_ids = {r.actor_id for r in rows if r.actor_id is not None}
        names = (
            dict(
                (
                    await self.repo.session.execute(
                        select(User.id, User.full_name).where(User.id.in_(actor_ids))
                    )
                ).all()
            )
            if actor_ids
            else {}
        )
        items = [
            AuditEntryOut.model_validate(r).model_copy(
                update={"actor_name": names.get(r.actor_id) if r.actor_id else None}
            )
            for r in rows
        ]
        return Page(items=items, next_cursor=next_cursor)
