import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        user = await self.session.get(User, user_id)
        return user if user is not None and user.deleted_at is None else None

    async def by_email(self, email: str) -> User | None:
        """email es citext: la comparacion no distingue mayusculas."""
        return await self.session.scalar(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )

    async def email_exists(self, email: str) -> bool:
        """Incluye cuentas borradas: un correo no se reutiliza."""
        return await self.session.scalar(select(User.id).where(User.email == email)) is not None

    def add(self, user: User) -> None:
        self.session.add(user)
