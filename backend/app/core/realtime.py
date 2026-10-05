"""Eventos en tiempo real (seccion 9).

Los servicios encolan eventos en la sesion de base de datos con emit(); se publican en Redis
solo cuando la transaccion se confirma, para que nadie reciba un aviso de algo que se
deshizo. Cada conexion WebSocket escucha los canales que le corresponden, en cualquier
proceso de la API (Redis pub/sub los difunde).

Canales: user:{id} (avisos y altas en conversaciones) y conv:{id} (mensajes y "escribiendo").
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from app.core.redis import redis_client

logger = structlog.get_logger("realtime")

PENDING_KEY = "realtime_pending"

Publisher = Callable[[str, str], Awaitable[Any]]


def user_channel(user_id: uuid.UUID | str) -> str:
    return f"user:{user_id}"


def conversation_channel(conversation_id: uuid.UUID | str) -> str:
    return f"conv:{conversation_id}"


async def _redis_publish(channel: str, data: str) -> None:
    await redis_client.publish(channel, data)


_publisher: Publisher = _redis_publish
# Referencias a las tareas en curso para que el recolector no las cancele.
_tasks: set[asyncio.Task[None]] = set()


def set_publisher(publisher: Publisher) -> Publisher:
    """Reemplaza el destino de los eventos (las pruebas los guardan en memoria)."""
    global _publisher
    previous, _publisher = _publisher, publisher
    return previous


def encode(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"))


async def publish_now(channel: str, payload: dict[str, Any]) -> None:
    """Sin pasar por la base de datos (por ejemplo "escribiendo")."""
    await _safe_publish(channel, encode(payload))


def emit(session: AsyncSession, channel: str, payload: dict[str, Any]) -> None:
    """Encola el evento; se publica al confirmar la transaccion y se descarta si se revierte."""
    sync = session.sync_session
    if not sync.in_transaction():
        # Sin transaccion un rollback no avisa: se abre (sin tocar la base) para que la cola
        # quede ligada a ella.
        sync.begin()
    sync.info.setdefault(PENDING_KEY, []).append((channel, encode(payload)))


async def _safe_publish(channel: str, data: str) -> None:
    try:
        await _publisher(channel, data)
    except Exception:
        logger.warning("realtime_publish_failed", channel=channel.split(":")[0])


@event.listens_for(Session, "after_commit")
def _publish_pending(session: Session) -> None:
    pending: list[tuple[str, str]] = session.info.pop(PENDING_KEY, [])
    if not pending:
        return
    loop = asyncio.get_running_loop()
    for channel, data in pending:
        task = loop.create_task(_safe_publish(channel, data))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


@event.listens_for(Session, "after_soft_rollback")
def _drop_pending(session: Session, previous_transaction: SessionTransaction) -> None:
    """Toda reversion de la transaccion externa descarta los eventos, aunque no hubiera
    alcanzado a ejecutar SQL. Un savepoint revertido (add_unique) no los toca."""
    if not previous_transaction.nested:
        session.info.pop(PENDING_KEY, None)


async def drain() -> None:
    """Espera a que salgan los eventos publicados (pruebas y jobs que terminan)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
