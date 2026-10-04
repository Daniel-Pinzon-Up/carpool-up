"""Hora del sistema en un solo lugar para poder fijarla en las pruebas.

La base de datos guarda UTC; las fechas de calendario (semestres, pico y placa) se evaluan
en la hora local de Pamplona.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Bogota")


def utcnow() -> datetime:
    return datetime.now(UTC)


def local_today() -> date:
    return utcnow().astimezone(LOCAL_TZ).date()
