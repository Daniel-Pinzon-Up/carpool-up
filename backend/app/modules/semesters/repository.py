import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.semesters.models import Semester


class SemesterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Semester]:
        return list(
            (await self.session.scalars(select(Semester).order_by(Semester.starts_on))).all()
        )

    async def get(self, semester_id: uuid.UUID) -> Semester | None:
        return await self.session.get(Semester, semester_id)

    async def containing(self, day: date) -> Semester | None:
        query = select(Semester).where(Semester.starts_on <= day, Semester.ends_on >= day)
        return await self.session.scalar(query)

    async def overlapping(
        self, starts_on: date, ends_on: date, exclude_id: uuid.UUID | None = None
    ) -> Semester | None:
        query = select(Semester).where(Semester.starts_on <= ends_on, Semester.ends_on >= starts_on)
        if exclude_id is not None:
            query = query.where(Semester.id != exclude_id)
        return await self.session.scalar(query.limit(1))

    async def by_name(self, name: str) -> Semester | None:
        return await self.session.scalar(select(Semester).where(Semester.name == name))

    def add(self, semester: Semester) -> None:
        self.session.add(semester)

    async def delete(self, semester: Semester) -> None:
        await self.session.delete(semester)
