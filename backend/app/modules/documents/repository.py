import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import DriverLicense, IdentityDocument


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest(self, user_id: uuid.UUID) -> IdentityDocument | None:
        query = (
            select(IdentityDocument)
            .where(IdentityDocument.user_id == user_id)
            .order_by(desc(IdentityDocument.created_at), desc(IdentityDocument.id))
            .limit(1)
        )
        return await self.session.scalar(query)

    async def for_user(self, user_id: uuid.UUID) -> list[IdentityDocument]:
        query = (
            select(IdentityDocument)
            .where(IdentityDocument.user_id == user_id)
            .order_by(desc(IdentityDocument.created_at))
        )
        return list((await self.session.scalars(query)).all())

    def add(self, document: IdentityDocument) -> None:
        self.session.add(document)


class LicenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_user(self, user_id: uuid.UUID) -> DriverLicense | None:
        return await self.session.scalar(
            select(DriverLicense).where(DriverLicense.user_id == user_id)
        )

    def add(self, license_: DriverLicense) -> None:
        self.session.add(license_)
