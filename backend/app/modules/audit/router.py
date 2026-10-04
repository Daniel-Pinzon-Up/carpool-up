from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import SuperAdmin
from app.core.deps import DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.modules.audit.schemas import AuditEntryOut, AuditFilters
from app.modules.audit.service import AuditService

admin_router = APIRouter(prefix="/admin/audit", tags=["admin: audit"])


@admin_router.get("")
async def list_audit(
    session: DbSession,
    _: SuperAdmin,
    filters: Annotated[AuditFilters, Depends()],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[AuditEntryOut]:
    """Auditoria completa, mas reciente primero. Solo superadmin."""
    return await AuditService(session).list_all(filters, limit, cursor)
