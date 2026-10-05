from datetime import date

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.enums import DocKind, ReviewStatus, UserRole
from app.core.errors import AppError
from app.core.storage import StoredFile, delete_private_file, save_private_file
from app.modules.documents.models import DriverLicense, IdentityDocument
from app.modules.documents.repository import DocumentRepository, LicenseRepository
from app.modules.semesters.repository import SemesterRepository
from app.modules.settings.service import SettingsService
from app.modules.users.models import User

IDENTITY_FOLDER = "identity"


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DocumentRepository(session)

    async def store_file(self, upload: UploadFile) -> StoredFile:
        """Valida y guarda el archivo antes de tocar la base de datos."""
        max_mb = int(await SettingsService(self.session).get("max_upload_mb"))
        return await save_private_file(upload, IDENTITY_FOLDER, max_mb)

    async def attach(self, user: User, kind: DocKind, stored: StoredFile) -> IdentityDocument:
        """Registra el documento para revision. Si ya hay uno pendiente, lo reemplaza.

        El documento queda ligado al semestre vigente (o a ninguno si aun no hay semestre).
        No hace commit.
        """
        latest = await self.repo.latest(user.id)
        if latest is not None and latest.status == ReviewStatus.PENDING:
            old_path = latest.file_path
            latest.kind = kind
            latest.file_path = stored.path
            latest.content_type = stored.content_type
            await self.session.flush()
            delete_private_file(old_path)
            return latest
        semester = await SemesterRepository(self.session).containing(local_today())
        document = IdentityDocument(
            user_id=user.id,
            kind=kind,
            file_path=stored.path,
            content_type=stored.content_type,
            status=ReviewStatus.PENDING,
            semester_id=semester.id if semester else None,
        )
        self.repo.add(document)
        await self.session.flush()
        return document

    async def upload(self, user: User, kind: DocKind, upload: UploadFile) -> IdentityDocument:
        stored = await self.store_file(upload)
        try:
            document = await self.attach(user, kind, stored)
            await self.session.commit()
        except Exception:
            delete_private_file(stored.path)
            raise
        await self.session.refresh(document)
        return document

    async def latest(self, user: User) -> IdentityDocument | None:
        return await self.repo.latest(user.id)

    async def history(self, user: User) -> list[IdentityDocument]:
        return await self.repo.for_user(user.id)


LICENSE_FOLDER = "licenses"


class LicenseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LicenseRepository(session)

    async def get(self, user: User) -> DriverLicense | None:
        return await self.repo.for_user(user.id)

    async def upload(self, user: User, expires_on: date, upload: UploadFile) -> DriverLicense:
        """Sube o reemplaza la licencia. Siempre vuelve a revision."""
        if user.role != UserRole.DRIVER:
            raise AppError("LICENSE_DRIVERS_ONLY", "Only drivers upload a license", 403)
        if expires_on <= local_today():
            raise AppError("LICENSE_EXPIRED", "The license is already expired", 422)
        max_mb = int(await SettingsService(self.session).get("max_upload_mb"))
        stored = await save_private_file(upload, LICENSE_FOLDER, max_mb)
        current = await self.repo.for_user(user.id)
        old_path = current.file_path if current else None
        try:
            if current is None:
                current = DriverLicense(user_id=user.id)
                self.repo.add(current)
            current.file_path = stored.path
            current.content_type = stored.content_type
            current.expires_on = expires_on
            current.status = ReviewStatus.PENDING
            current.reviewed_by = None
            current.reviewed_at = None
            current.rejection_reason = None
            await self.session.commit()
        except Exception:
            delete_private_file(stored.path)
            raise
        if old_path:
            delete_private_file(old_path)
        await self.session.refresh(current)
        return current
