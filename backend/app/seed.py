"""Datos semilla. Idempotente: se puede ejecutar varias veces.

El paso 1 agrega semestre actual, puntos de Pamplona, pico y placa, parametros y superadmin.
"""

import asyncio

import structlog
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging

logger = structlog.get_logger("seed")


async def main() -> None:
    configure_logging(json_output=get_settings().environment != "development")
    async with engine.begin() as conn:
        postgis = (await conn.execute(text("SELECT postgis_version()"))).scalar()
    logger.info("seed_done", postgis=postgis, note="sin datos semilla todavia")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
