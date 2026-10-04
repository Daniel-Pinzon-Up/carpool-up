import uuid

from fastapi import APIRouter, status

from app.core.auth import SuperAdmin, SuperAdminActor
from app.core.deps import DbSession
from app.modules.semesters.schemas import SemesterCreate, SemesterOut, SemesterUpdate
from app.modules.semesters.service import SemesterService

router = APIRouter(prefix="/meta/semesters", tags=["meta"])
admin_router = APIRouter(prefix="/admin/semesters", tags=["admin: semesters"])


@router.get("/current", responses={404: {"description": "NO_CURRENT_SEMESTER"}})
async def current_semester(session: DbSession) -> SemesterOut:
    """Semestre que contiene la fecha de hoy en Pamplona."""
    return SemesterOut.model_validate(await SemesterService(session).current())


@admin_router.get("")
async def list_semesters(session: DbSession, _: SuperAdmin) -> list[SemesterOut]:
    return [SemesterOut.model_validate(s) for s in await SemesterService(session).list_all()]


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def create_semester(
    body: SemesterCreate, session: DbSession, actor: SuperAdminActor
) -> SemesterOut:
    return SemesterOut.model_validate(await SemesterService(session).create(body, actor))


@admin_router.patch("/{semester_id}")
async def update_semester(
    semester_id: uuid.UUID, body: SemesterUpdate, session: DbSession, actor: SuperAdminActor
) -> SemesterOut:
    return SemesterOut.model_validate(
        await SemesterService(session).update(semester_id, body, actor)
    )


@admin_router.delete("/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_semester(
    semester_id: uuid.UUID, session: DbSession, actor: SuperAdminActor
) -> None:
    await SemesterService(session).delete(semester_id, actor)
