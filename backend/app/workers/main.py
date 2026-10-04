from typing import Any

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = structlog.get_logger("worker")


async def heartbeat(ctx: dict[str, Any]) -> str:
    """Prueba de vida del worker. Los jobs de negocio se agregan en sus pasos."""
    logger.info("worker_heartbeat")
    return "ok"


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(json_output=get_settings().environment != "development")
    logger.info("worker_started")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [heartbeat]
    cron_jobs = [cron(heartbeat, minute={0, 15, 30, 45}, run_at_startup=True)]
    on_startup = startup
