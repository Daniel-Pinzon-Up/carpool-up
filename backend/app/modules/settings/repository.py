from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import SystemSetting


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def all(self) -> dict[str, SystemSetting]:
        rows = await self.session.scalars(select(SystemSetting))
        return {row.key: row for row in rows}

    async def get(self, key: str) -> SystemSetting | None:
        return await self.session.get(SystemSetting, key)

    def add(self, setting: SystemSetting) -> None:
        self.session.add(setting)
