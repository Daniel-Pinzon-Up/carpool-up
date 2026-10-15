import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.core.auth import AdminActor, AdminOrSuper, SuperAdminActor
from app.core.deps import DbSession
from app.core.enums import ReviewStatus
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.modules.admin.accounts import AccountAdminService
from app.modules.admin.approvals import ApprovalService
from app.modules.admin.schemas import (
    AdminCreate,
    AdminUserOut,
    ApprovalCounts,
    ApprovalItem,
    ApprovalType,
    ApproveRequest,
    RejectRequest,
    RoleChange,
)

router = APIRouter(prefix="/admin", tags=["admin: approvals and accounts"])


@router.get("/approvals")
async def approval_queue(
    session: DbSession,
    _: AdminOrSuper,
    type: ApprovalType = "identity",
    status: ReviewStatus = ReviewStatus.PENDING,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> Page[ApprovalItem]:
    """Documentos de identidad o licencias por revisar, en orden de llegada."""
    return await ApprovalService(session).queue(type, status, limit, cursor)


@router.get("/approvals/counts")
async def approval_counts(session: DbSession, _: AdminOrSuper) -> ApprovalCounts:
    return await ApprovalService(session).counts()


@router.get("/approvals/{approval_id}")
async def approval_detail(
    approval_id: uuid.UUID, session: DbSession, _: AdminOrSuper
) -> ApprovalItem:
    return await ApprovalService(session).detail(approval_id)


@router.post("/approvals/{approval_id}/approve")
async def approve(
    approval_id: uuid.UUID, body: ApproveRequest, session: DbSession, actor: AdminActor
) -> ApprovalItem:
    """Aprueba. En documentos de identidad corrige el sexo y activa la cuenta pendiente."""
    return await ApprovalService(session).approve(approval_id, actor, body.sex)


@router.post("/approvals/{approval_id}/reject")
async def reject(
    approval_id: uuid.UUID, body: RejectRequest, session: DbSession, actor: AdminActor
) -> ApprovalItem:
    """Rechaza con motivo; el usuario lo ve y puede subir otro documento."""
    return await ApprovalService(session).reject(approval_id, actor, body.reason)


@router.get("/files/{approval_id}", response_class=FileResponse)
async def approval_file(
    approval_id: uuid.UUID, session: DbSession, _: AdminOrSuper
) -> FileResponse:
    """Archivo del documento de identidad o la licencia. Sin cache."""
    return await ApprovalService(session).file(approval_id)


@router.post("/admins", status_code=status.HTTP_201_CREATED)
async def create_admin(
    body: AdminCreate, session: DbSession, actor: SuperAdminActor
) -> AdminUserOut:
    """Crea un administrador. Su primer ingreso pide el codigo enviado al correo."""
    return await AccountAdminService(session).create_admin(body, actor)


@router.patch("/users/{user_id}/role")
async def change_role(
    user_id: uuid.UUID, body: RoleChange, session: DbSession, actor: SuperAdminActor
) -> AdminUserOut:
    return await AccountAdminService(session).change_role(user_id, body.role, actor)
