from typing import Any

from fastapi import APIRouter

from app.core.auth import SuperAdmin, SuperAdminActor
from app.core.config import get_settings
from app.core.deps import DbSession
from app.modules.settings.schemas import SettingOut, SettingUpdate
from app.modules.settings.service import SettingsService

router = APIRouter(prefix="/meta/settings", tags=["meta"])
admin_router = APIRouter(prefix="/admin/settings", tags=["admin: settings"])


@router.get("/public")
async def public_settings(session: DbSession) -> dict[str, Any]:
    """Parametros vigentes que la interfaz necesita para explicar reglas y validar formularios."""
    values = await SettingsService(session).public_values()
    # Configuracion de entorno que la interfaz necesita para validar el registro.
    values["allowed_email_suffix"] = get_settings().allowed_email_suffix
    return values


@admin_router.get("")
async def list_settings(session: DbSession, _: SuperAdmin) -> list[SettingOut]:
    return await SettingsService(session).list_all()


@admin_router.patch("/{key}")
async def update_setting(
    key: str, body: SettingUpdate, session: DbSession, actor: SuperAdminActor
) -> SettingOut:
    """Cambia un parametro. Se valida contra su tipo y queda en la auditoria."""
    return await SettingsService(session).update(key, body.value, actor)
