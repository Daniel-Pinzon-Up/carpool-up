from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.core.errors import AppError
from app.modules.audit.service import AuditService
from app.modules.settings.definitions import DEFINITIONS, ServiceArea, SettingDefinition
from app.modules.settings.models import SystemSetting
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import SettingOut


def _definition(key: str) -> SettingDefinition:
    definition = DEFINITIONS.get(key)
    if definition is None:
        raise AppError("SETTING_UNKNOWN", "Unknown setting", 404, {"key": key})
    return definition


def _validate(definition: SettingDefinition, value: Any) -> Any:
    """Valida y devuelve el valor normalizado en forma JSON."""
    try:
        # strict: evita que true se acepte como 1 o "2" como 2.
        parsed = definition.adapter.validate_python(value, strict=True)
    except ValidationError as exc:
        errors = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        raise AppError(
            "SETTING_INVALID",
            "Invalid setting value",
            422,
            {"key": definition.key, "errors": errors},
        ) from exc
    return definition.adapter.dump_python(parsed, mode="json")


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SettingsRepository(session)

    async def get(self, key: str) -> Any:
        """Valor vigente. Si la fila aun no existe se usa el valor inicial del catalogo."""
        definition = _definition(key)
        row = await self.repo.get(key)
        return row.value if row else definition.default

    async def service_area(self) -> ServiceArea:
        return ServiceArea.model_validate(await self.get("service_area"))

    async def list_all(self) -> list[SettingOut]:
        rows = await self.repo.all()
        result = []
        for key, definition in DEFINITIONS.items():
            row = rows.get(key)
            result.append(
                SettingOut(
                    key=key,
                    value=row.value if row else definition.default,
                    description=definition.description,
                    updated_at=row.updated_at if row else None,
                    updated_by=row.updated_by if row else None,
                )
            )
        return result

    async def public_values(self) -> dict[str, Any]:
        """Ningun parametro es secreto: la interfaz los usa para explicar y prevenir errores."""
        return {item.key: item.value for item in await self.list_all()}

    async def update(self, key: str, value: Any, actor: Actor) -> SettingOut:
        definition = _definition(key)
        normalized = _validate(definition, value)
        row = await self.repo.get(key)
        before = row.value if row else definition.default
        if row is None:
            row = SystemSetting(key=key, value=normalized, updated_by=actor.user.id)
            self.repo.add(row)
        else:
            row.value = normalized
            row.updated_by = actor.user.id
        AuditService(self.session).record(
            actor, "setting.update", "system_setting", key, {"value": before}, {"value": normalized}
        )
        await self.session.commit()
        await self.session.refresh(row)
        return SettingOut(
            key=key,
            value=row.value,
            description=definition.description,
            updated_at=row.updated_at,
            updated_by=row.updated_by,
        )

    async def ensure_defaults(self) -> int:
        """Crea las claves que falten con su valor inicial; no toca las existentes."""
        existing = await self.repo.all()
        created = 0
        for key, definition in DEFINITIONS.items():
            if key not in existing:
                self.repo.add(
                    SystemSetting(key=key, value=_validate(definition, definition.default))
                )
                created += 1
        return created
