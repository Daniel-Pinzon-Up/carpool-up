import uuid
from datetime import datetime

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuthPurpose
from app.modules.auth.models import AuthCode, UserSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, session_id: uuid.UUID) -> UserSession | None:
        return await self.session.get(UserSession, session_id)

    async def active_for_user(self, user_id: uuid.UUID, now: datetime) -> list[UserSession]:
        query = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(desc(UserSession.last_seen_at))
        )
        return list((await self.session.scalars(query)).all())

    async def revoke_all(
        self, user_id: uuid.UUID, now: datetime, keep: uuid.UUID | None = None
    ) -> int:
        query = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if keep is not None:
            query = query.where(UserSession.id != keep)
        result = await self.session.execute(query)
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def add(self, user_session: UserSession) -> None:
        self.session.add(user_session)


class CodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest(self, user_id: uuid.UUID, purpose: AuthPurpose) -> AuthCode | None:
        query = (
            select(AuthCode)
            .where(AuthCode.user_id == user_id, AuthCode.purpose == purpose)
            .order_by(desc(AuthCode.created_at))
            .limit(1)
        )
        return await self.session.scalar(query)

    async def active(
        self, user_id: uuid.UUID, purpose: AuthPurpose, now: datetime
    ) -> AuthCode | None:
        query = (
            select(AuthCode)
            .where(
                AuthCode.user_id == user_id,
                AuthCode.purpose == purpose,
                AuthCode.used_at.is_(None),
                AuthCode.expires_at > now,
            )
            .order_by(desc(AuthCode.created_at))
            .limit(1)
            .with_for_update()
        )
        return await self.session.scalar(query)

    async def invalidate(self, user_id: uuid.UUID, purpose: AuthPurpose, now: datetime) -> None:
        await self.session.execute(
            update(AuthCode)
            .where(
                AuthCode.user_id == user_id,
                AuthCode.purpose == purpose,
                AuthCode.used_at.is_(None),
            )
            .values(used_at=now)
        )

    def add(self, code: AuthCode) -> None:
        self.session.add(code)
