"""Codigos de un solo uso por correo: emision con espera minima y verificacion con intentos."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import AuthPurpose
from app.core.errors import AppError
from app.core.security import code_matches, hash_code, new_code
from app.modules.auth.models import AuthCode
from app.modules.auth.repository import CodeRepository
from app.modules.settings.service import SettingsService


class InvalidCodeError(AppError):
    """Un solo error para codigo equivocado, vencido, agotado o inexistente.

    Distinguirlos permitiria averiguar si un correo tiene cuenta.
    """

    def __init__(self) -> None:
        super().__init__("CODE_INVALID", "The code is wrong or expired", 400)


@dataclass(frozen=True)
class IssuedCode:
    code: str | None  # None si se respeto la espera y no se emitio uno nuevo
    resend_after_seconds: int


class CodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CodeRepository(session)
        self.settings = SettingsService(session)

    async def minutes(self) -> int:
        return int(await self.settings.get("auth_code_minutes"))

    async def _cooldown_left(self, user_id: uuid.UUID, purpose: AuthPurpose) -> int:
        cooldown = int(await self.settings.get("auth_code_resend_seconds"))
        latest = await self.repo.latest(user_id, purpose)
        if latest is None:
            return 0
        elapsed = (utcnow() - latest.created_at).total_seconds()
        return max(0, int(cooldown - elapsed))

    async def issue(
        self, user_id: uuid.UUID, purpose: AuthPurpose, *, strict_cooldown: bool = False
    ) -> IssuedCode:
        """Emite un codigo nuevo e invalida los anteriores del mismo proposito.

        Si se pide otro antes de la espera minima: con strict_cooldown se responde error;
        sin el, se conserva el codigo vigente y no se envia otro correo.
        """
        left = await self._cooldown_left(user_id, purpose)
        if left > 0:
            if strict_cooldown:
                raise AppError(
                    "CODE_RESEND_TOO_SOON",
                    "Wait before requesting another code",
                    429,
                    {"retry_after_seconds": left},
                )
            return IssuedCode(code=None, resend_after_seconds=left)
        now = utcnow()
        await self.repo.invalidate(user_id, purpose, now)
        code = new_code()
        self.repo.add(
            AuthCode(
                user_id=user_id,
                purpose=purpose,
                code_hash=hash_code(user_id, purpose, code),
                expires_at=now + timedelta(minutes=await self.minutes()),
                attempts=0,
            )
        )
        cooldown = int(await self.settings.get("auth_code_resend_seconds"))
        return IssuedCode(code=code, resend_after_seconds=cooldown)

    async def check(self, user_id: uuid.UUID, purpose: AuthPurpose, code: str) -> bool:
        """Marca el codigo como usado si coincide. Devuelve False si no sirve.

        No hace commit: quien llama confirma la transaccion, tambien en el caso fallido,
        para que el intento quede contado.
        """
        now = utcnow()
        active = await self.repo.active(user_id, purpose, now)
        if active is None:
            return False
        if code_matches(user_id, purpose, code, active.code_hash):
            active.used_at = now
            return True
        active.attempts += 1
        if active.attempts >= int(await self.settings.get("auth_code_max_attempts")):
            active.used_at = now  # agotado: no vuelve a servir
        return False
