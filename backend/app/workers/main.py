from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.clock import local_today
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.email import OutgoingEmail, send_smtp
from app.core.logging import configure_logging
from app.modules.bookings.jobs import auto_cancel_late_driver, expire_pending
from app.modules.documents.revalidation import run_revalidation
from app.modules.series.service import finish_past_series
from app.modules.trips.service import recheck_pico_placa
from app.modules.waitlist.offers import run_waitlist

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


async def pico_placa_recheck(ctx: dict[str, Any]) -> dict[str, int]:
    """Diario: aplica pico y placa a los viajes futuros y cierra las series vencidas."""
    async with SessionLocal() as session:
        result = await recheck_pico_placa(session)
        finished = await finish_past_series(session, local_today())
    return {"cancelled": result.cancelled, "restored": result.restored, "finished": finished}


async def expire_pending_requests(ctx: dict[str, Any]) -> dict[str, int]:
    """Cada 5 minutos: vence solicitudes y suscripciones sin respuesta."""
    async with SessionLocal() as session:
        return await expire_pending(session)


async def auto_cancel_late(ctx: dict[str, Any]) -> int:
    """Cada minuto: cancela sin penalizacion las reservas de viajes que no iniciaron a tiempo."""
    async with SessionLocal() as session:
        return await auto_cancel_late_driver(session)


async def offer_waitlist(ctx: dict[str, Any]) -> dict[str, int]:
    """Cada minuto: vence ofertas de la lista de espera y ofrece el cupo libre."""
    async with SessionLocal() as session:
        return await run_waitlist(session)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(json_output=get_settings().environment != "development")
    logger.info("worker_started")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions: ClassVar[list[Any]] = [
        heartbeat,
        send_email,
        semester_revalidation,
        pico_placa_recheck,
        expire_pending_requests,
        auto_cancel_late,
        offer_waitlist,
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(heartbeat, minute={0, 15, 30, 45}, run_at_startup=True),
        # 10:05 UTC = 5:05 a. m. en Pamplona.
        cron(semester_revalidation, hour={10}, minute={5}, run_at_startup=True),
        # 10:15 UTC = 5:15 a. m. en Pamplona.
        cron(pico_placa_recheck, hour={10}, minute={15}, run_at_startup=True),
        cron(expire_pending_requests, minute=set(range(0, 60, 5))),
        cron(auto_cancel_late),
        cron(offer_waitlist),
    ]
    on_startup = startup
    max_tries = 5
