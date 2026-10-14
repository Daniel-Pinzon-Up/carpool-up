from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import UserRole
from app.core.errors import AppError
from app.modules.documents.service import DocumentService, LicenseService
from app.modules.users.models import User
from app.modules.users.schemas import DocumentSummary, LicenseSummary, MeOut, MeUpdate
from app.modules.vehicles.eligibility import publishing_blockers


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def me(self, user: User) -> MeOut:
        document = await DocumentService(self.session).latest(user)
        license_ = (
            await LicenseService(self.session).get(user) if user.role == UserRole.DRIVER else None
        )
        blockers = (
            await publishing_blockers(self.session, user) if user.role == UserRole.DRIVER else []
        )
        return MeOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            sex=user.sex,
            program=user.program,
            role=user.role,
            status=user.status,
            payment_note=user.payment_note if user.role == UserRole.DRIVER else None,
            last_login_at=user.last_login_at,
            document=DocumentSummary.model_validate(document) if document else None,
            license=LicenseSummary.model_validate(license_) if license_ else None,
            can_publish=user.role == UserRole.DRIVER and not blockers,
            publish_blockers=blockers,
            booking_ban_until=(
                user.booking_ban_until
                if user.booking_ban_until and user.booking_ban_until > utcnow()
                else None
            ),
        )

    async def update_me(self, user: User, data: MeUpdate) -> MeOut:
        changes = data.model_dump(exclude_unset=True)
        if "payment_note" in changes and user.role != UserRole.DRIVER:
            raise AppError("PAYMENT_NOTE_DRIVERS_ONLY", "Only drivers can set a payment note", 403)
        for field, value in changes.items():
            if field == "payment_note":
                user.payment_note = value or None  # vacio o nulo borra la nota
            elif value is not None:
                setattr(user, field, value)
        await self.session.commit()
        await self.session.refresh(user)
        return await self.me(user)
