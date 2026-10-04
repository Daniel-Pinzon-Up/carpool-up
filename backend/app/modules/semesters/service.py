import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.clock import local_today
from app.core.errors import AppError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.semesters.models import Semester
from app.modules.semesters.repository import SemesterRepository
from app.modules.semesters.schemas import SemesterCreate, SemesterOut, SemesterUpdate
from app.modules.settings.service import SettingsService

ENTITY = "semester"


def _snapshot(semester: Semester) -> dict[str, Any]:
    return SemesterOut.model_validate(semester).model_dump(
        mode="json", exclude={"created_at", "updated_at"}
    )


def _check_dates(starts_on: date, ends_on: date, deadline: date) -> None:
    if ends_on <= starts_on:
        raise AppError("SEMESTER_INVALID_DATES", "ends_on must be after starts_on", 422)
    if not starts_on <= deadline <= ends_on:
        raise AppError(
            "SEMESTER_INVALID_DATES", "revalidation_deadline must fall inside the semester", 422
        )


class SemesterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SemesterRepository(session)
        self.audit = AuditService(session)

    async def list_all(self) -> list[Semester]:
        return await self.repo.list_all()

    async def current(self) -> Semester:
        semester = await self.repo.containing(local_today())
        if semester is None:
            raise AppError("NO_CURRENT_SEMESTER", "There is no semester for today", 404)
        return semester

    async def _get(self, semester_id: uuid.UUID) -> Semester:
        semester = await self.repo.get(semester_id)
        if semester is None:
            raise NotFoundError(ENTITY)
        return semester

    async def _check_conflicts(
        self, name: str, starts_on: date, ends_on: date, exclude_id: uuid.UUID | None = None
    ) -> None:
        same_name = await self.repo.by_name(name)
        if same_name is not None and same_name.id != exclude_id:
            raise AppError("SEMESTER_NAME_TAKEN", "Semester name already exists", 409)
        other = await self.repo.overlapping(starts_on, ends_on, exclude_id)
        if other is not None:
            raise AppError(
                "SEMESTER_OVERLAP", "Semesters cannot overlap", 409, {"conflicts_with": other.name}
            )

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            # Respaldo ante carreras: decide la restriccion de exclusion de la base.
            await self.session.rollback()
            raise AppError("SEMESTER_OVERLAP", "Semesters cannot overlap", 409) from exc

    async def create(self, data: SemesterCreate, actor: Actor) -> Semester:
        deadline = data.revalidation_deadline
        if deadline is None:
            days = await SettingsService(self.session).get("revalidation_days")
            deadline = min(data.starts_on + timedelta(days=days), data.ends_on)
        _check_dates(data.starts_on, data.ends_on, deadline)
        await self._check_conflicts(data.name, data.starts_on, data.ends_on)
        semester = Semester(
            name=data.name,
            starts_on=data.starts_on,
            ends_on=data.ends_on,
            revalidation_deadline=deadline,
        )
        self.repo.add(semester)
        await self.session.flush()
        self.audit.record(actor, "semester.create", ENTITY, semester.id, None, _snapshot(semester))
        await self._commit()
        return semester

    async def update(self, semester_id: uuid.UUID, data: SemesterUpdate, actor: Actor) -> Semester:
        semester = await self._get(semester_id)
        before = _snapshot(semester)
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        name = changes.get("name", semester.name)
        starts_on = changes.get("starts_on", semester.starts_on)
        ends_on = changes.get("ends_on", semester.ends_on)
        deadline = changes.get("revalidation_deadline", semester.revalidation_deadline)
        _check_dates(starts_on, ends_on, deadline)
        await self._check_conflicts(name, starts_on, ends_on, exclude_id=semester.id)
        semester.name = name
        semester.starts_on = starts_on
        semester.ends_on = ends_on
        semester.revalidation_deadline = deadline
        self.audit.record(
            actor, "semester.update", ENTITY, semester.id, before, _snapshot(semester)
        )
        await self._commit()
        await self.session.refresh(semester)
        return semester

    async def delete(self, semester_id: uuid.UUID, actor: Actor) -> None:
        semester = await self._get(semester_id)
        self.audit.record(actor, "semester.delete", ENTITY, semester.id, _snapshot(semester), None)
        await self.repo.delete(semester)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(
                "SEMESTER_IN_USE", "Semester is referenced by other records", 409
            ) from exc
