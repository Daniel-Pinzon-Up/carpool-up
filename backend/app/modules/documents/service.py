"""Documentos que revisa un administrador: carnet o constancia y licencia de conduccion."""

from datetime import date

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.enums import IDENTITY_KINDS, DocKind, ReviewStatus, UserRole
from app.core.errors import AppError
from app.core.storage import StoredFile, delete_private_file, save_private_file
from app.modules.documents.models import Document
from app.modules.documents.repository import documents_of, latest_document
from app.modules.semesters.repository import SemesterRepository
from app.modules.settings.service import SettingsService
from app.modules.users.models import User

IDENTITY_FOLDER = "identity"
LICENSE_FOLDER = "licenses"


async def store_upload(session: AsyncSession, upload: UploadFile, folder: str) -> StoredFile:
    """Valida tipo y tamano y guarda el archivo antes de tocar la base de datos."""
    max_mb = int(await SettingsService(session).get("max_upload_mb"))
    return await save_private_file(upload, folder, max_mb)


class DocumentService:
    """Carnet estudiantil o constancia institucional."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store_file(self, upload: UploadFile) -> StoredFile:
        return await store_upload(self.session, upload, IDENTITY_FOLDER)

    async def attach(self, user: User, kind: DocKind, stored: StoredFile) -> Document:
        """Registra el documento para revision. Si ya hay uno pendiente, lo reemplaza.

        Queda ligado al semestre vigente (o a ninguno si aun no hay semestre). Sin commit.
        """
        latest = await latest_document(self.session, user.id, IDENTITY_KINDS)
        if latest is not None and latest.status == ReviewStatus.PENDING:
            old_path = latest.file_path
            latest.kind = kind
            latest.file_path = stored.path
            latest.content_type = stored.content_type
            await self.session.flush()
            delete_private_file(old_path)
            return latest
        semester = await SemesterRepository(self.session).containing(local_today())
        document = Document(
            user_id=user.id,
            kind=kind,
            file_path=stored.path,
            content_type=stored.content_type,
            status=ReviewStatus.PENDING,
            semester_id=semester.id if semester else None,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def upload(self, user: User, kind: DocKind, upload: UploadFile) -> Document:
        stored = await self.store_file(upload)
        try:
            document = await self.attach(user, kind, stored)
            await self.session.commit()
        except Exception:
            delete_private_file(stored.path)
            raise
        await self.session.refresh(document)
        return document

    async def latest(self, user: User) -> Document | None:
        return await latest_document(self.session, user.id, IDENTITY_KINDS)

    async def history(self, user: User) -> list[Document]:
        return await documents_of(self.session, user.id, IDENTITY_KINDS)


class LicenseService:
    """Licencia de conduccion: la necesita aprobada y vigente quien publica viajes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user: User) -> Document | None:
        return await latest_document(self.session, user.id, (DocKind.DRIVER_LICENSE,))

    async def upload(self, user: User, expires_on: date, upload: UploadFile) -> Document:
        """Sube una licencia nueva para revision; la anterior se borra."""
        if user.role != UserRole.DRIVER:
            raise AppError("LICENSE_DRIVERS_ONLY", "Only drivers upload a license", 403)
        if expires_on <= local_today():
            raise AppError("LICENSE_EXPIRED", "The license is already expired", 422)
        stored = await store_upload(self.session, upload, LICENSE_FOLDER)
        previous = await self.get(user)
        try:
            license_ = Document(
                user_id=user.id,
                kind=DocKind.DRIVER_LICENSE,
                file_path=stored.path,
                content_type=stored.content_type,
                expires_on=expires_on,
                status=ReviewStatus.PENDING,
            )
            self.session.add(license_)
            if previous is not None:
                await self.session.delete(previous)
            await self.session.commit()
        except Exception:
            delete_private_file(stored.path)
            raise
        if previous is not None:
            delete_private_file(previous.file_path)
        await self.session.refresh(license_)
        return license_
