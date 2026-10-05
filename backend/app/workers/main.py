from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.clock import local_today
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.email import OutgoingEmail, send_smtp
from app.core.logging import configure_logging
from app.modules.documents.revalidation import run_revalidation

logger = structlog.get_logger("worker")


async def heartbeat(ctx: dict[str, Any]) -> str:
    """Prueba de vida del worker."""
    logger.info("worker_heartbeat")
    return "ok"


async def send_email(ctx: dict[str, Any], email: dict[str, str]) -> None:
    """Envia un correo encolado por la API. ARQ reintenta si el SMTP falla."""
    await send_smtp(OutgoingEmail(**email))
    # Nunca se registra el destinatario ni el contenido (lleva codigos).
    logger.info("email_sent", subject=email["subject"])


async def semester_revalidation(ctx: dict[str, Any]) -> dict[str, int]:
    """Diario: vence documentos de semestres anteriores y aplica el plazo de revalidacion."""
    async with SessionLocal() as session:
        result = await run_revalidation(session, local_today())
    return {"expired": result.expired_documents, "downgraded": result.downgraded_users}


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(json_output=get_settings().environment != "development")
    logger.info("worker_started")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions: ClassVar[list[Any]] = [heartbeat, send_email, semester_revalidation]
    cron_jobs: ClassVar[list[Any]] = [
        cron(heartbeat, minute={0, 15, 30, 45}, run_at_startup=True),
        # 10:05 UTC = 5:05 a. m. en Pamplona.
        cron(semester_revalidation, hour={10}, minute={5}, run_at_startup=True),
    ]
    on_startup = startup
    max_tries = 5
