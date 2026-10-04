"""Pico y placa. Este servicio es la unica fuente de verdad sobre restricciones por placa."""

import uuid
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.enums import VehicleType
from app.core.errors import AppError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.pico_placa.models import PicoPlacaRule
from app.modules.pico_placa.repository import PicoPlacaRepository
from app.modules.pico_placa.schemas import (
    PicoPlacaRuleCreate,
    PicoPlacaRuleOut,
    PicoPlacaRuleUpdate,
)

ENTITY = "pico_placa_rule"


def last_digit(plate: str) -> int | None:
    """Ultimo digito numerico de la placa. Las placas de moto terminan en letra (ABC12D -> 2)."""
    for char in reversed(plate.strip()):
        if char.isdigit():
            return int(char)
    return None


def _applies(rule: PicoPlacaRule, day: date, digit: int) -> bool:
    return (
        rule.weekday == day.weekday()
        and rule.valid_from <= day
        and (rule.valid_to is None or rule.valid_to >= day)
        and digit in rule.restricted_digits
    )


def restricted_days(rules: Iterable[PicoPlacaRule], days: Iterable[date], digit: int) -> set[date]:
    rule_list = list(rules)
    return {day for day in days if any(_applies(rule, day, digit) for rule in rule_list)}


def _snapshot(rule: PicoPlacaRule) -> dict[str, Any]:
    return PicoPlacaRuleOut.model_validate(rule).model_dump(mode="json")


class PicoPlacaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PicoPlacaRepository(session)
        self.audit = AuditService(session)

    async def is_restricted(self, vehicle_type: VehicleType, plate: str, day: date) -> bool:
        return day in await self.restricted_dates(vehicle_type, plate, day, day)

    async def restricted_dates(
        self, vehicle_type: VehicleType, plate: str, start: date, end: date
    ) -> set[date]:
        """Fechas del rango [start, end] en que la placa no puede circular."""
        digit = last_digit(plate)
        if digit is None or end < start:
            return set()
        rules = await self.repo.active_between(vehicle_type, start, end)
        days = (start + timedelta(days=offset) for offset in range((end - start).days + 1))
        return restricted_days(rules, days, digit)

    async def list_all(self) -> list[PicoPlacaRule]:
        return await self.repo.list_all()

    async def _get(self, rule_id: uuid.UUID) -> PicoPlacaRule:
        rule = await self.repo.get(rule_id)
        if rule is None:
            raise NotFoundError(ENTITY)
        return rule

    async def create(self, data: PicoPlacaRuleCreate, actor: Actor) -> PicoPlacaRule:
        rule = PicoPlacaRule(**data.model_dump())
        self.repo.add(rule)
        await self.session.flush()
        self.audit.record(actor, "pico_placa.create", ENTITY, rule.id, None, _snapshot(rule))
        await self.session.commit()
        return rule

    async def update(
        self, rule_id: uuid.UUID, data: PicoPlacaRuleUpdate, actor: Actor
    ) -> PicoPlacaRule:
        rule = await self._get(rule_id)
        before = _snapshot(rule)
        changes = data.model_dump(exclude_unset=True)
        # valid_to puede volver a nulo (vigencia indefinida); los demas campos no.
        for field, value in changes.items():
            if value is not None or field == "valid_to":
                setattr(rule, field, value)
        if rule.valid_to is not None and rule.valid_to < rule.valid_from:
            raise AppError(
                "PICO_PLACA_INVALID_DATES", "valid_to must not be before valid_from", 422
            )
        self.audit.record(actor, "pico_placa.update", ENTITY, rule.id, before, _snapshot(rule))
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def delete(self, rule_id: uuid.UUID, actor: Actor) -> None:
        rule = await self._get(rule_id)
        self.audit.record(actor, "pico_placa.delete", ENTITY, rule.id, _snapshot(rule), None)
        await self.repo.delete(rule)
        await self.session.commit()
