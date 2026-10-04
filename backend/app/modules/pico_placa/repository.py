import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VehicleType
from app.modules.pico_placa.models import PicoPlacaRule


class PicoPlacaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[PicoPlacaRule]:
        query = select(PicoPlacaRule).order_by(
            PicoPlacaRule.vehicle_type, PicoPlacaRule.weekday, PicoPlacaRule.valid_from
        )
        return list((await self.session.scalars(query)).all())

    async def get(self, rule_id: uuid.UUID) -> PicoPlacaRule | None:
        return await self.session.get(PicoPlacaRule, rule_id)

    async def active_between(
        self, vehicle_type: VehicleType, start: date, end: date
    ) -> list[PicoPlacaRule]:
        """Reglas activas del tipo de vehiculo cuya vigencia toca el rango [start, end]."""
        query = select(PicoPlacaRule).where(
            PicoPlacaRule.vehicle_type == vehicle_type,
            PicoPlacaRule.is_active.is_(True),
            PicoPlacaRule.valid_from <= end,
            or_(PicoPlacaRule.valid_to.is_(None), PicoPlacaRule.valid_to >= start),
        )
        return list((await self.session.scalars(query)).all())

    def add(self, rule: PicoPlacaRule) -> None:
        self.session.add(rule)

    async def delete(self, rule: PicoPlacaRule) -> None:
        await self.session.delete(rule)
