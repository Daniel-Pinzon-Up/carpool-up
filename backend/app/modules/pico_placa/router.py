import uuid

from fastapi import APIRouter, status

from app.core.auth import SuperAdmin, SuperAdminActor
from app.core.deps import DbSession
from app.modules.pico_placa.schemas import (
    PicoPlacaRuleCreate,
    PicoPlacaRuleOut,
    PicoPlacaRuleUpdate,
)
from app.modules.pico_placa.service import PicoPlacaService

admin_router = APIRouter(prefix="/admin/pico-placa", tags=["admin: pico y placa"])


@admin_router.get("")
async def list_rules(session: DbSession, _: SuperAdmin) -> list[PicoPlacaRuleOut]:
    return [PicoPlacaRuleOut.model_validate(r) for r in await PicoPlacaService(session).list_all()]


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: PicoPlacaRuleCreate, session: DbSession, actor: SuperAdminActor
) -> PicoPlacaRuleOut:
    return PicoPlacaRuleOut.model_validate(await PicoPlacaService(session).create(body, actor))


@admin_router.patch("/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID, body: PicoPlacaRuleUpdate, session: DbSession, actor: SuperAdminActor
) -> PicoPlacaRuleOut:
    rule = await PicoPlacaService(session).update(rule_id, body, actor)
    return PicoPlacaRuleOut.model_validate(rule)


@admin_router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, session: DbSession, actor: SuperAdminActor) -> None:
    await PicoPlacaService(session).delete(rule_id, actor)
