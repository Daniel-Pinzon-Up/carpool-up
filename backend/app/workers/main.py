from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.email import OutgoingEmail, send_smtp
from app.core.logging import configure_logging

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


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(json_output=get_settings().environment != "development")
    logger.info("worker_started")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions: ClassVar[list[Any]] = [heartbeat, send_email]
    cron_jobs: ClassVar[list[Any]] = [cron(heartbeat, minute={0, 15, 30, 45}, run_at_startup=True)]
    on_startup = startup
    max_tries = 5
