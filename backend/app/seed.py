"""Datos semilla. Idempotente: crea lo que falte y nunca sobrescribe datos existentes.

Carga parametros por defecto, superadmin inicial, semestre actual, puntos de ejemplo de
Pamplona, reglas de ejemplo de pico y placa y la version inicial de los documentos legales.
"""

import asyncio
from datetime import date, timedelta
from pathlib import Path

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.enums import Language, LegalKind, PlaceKind, UserRole, UserStatus, VehicleType
from app.core.geo import point
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.modules.legal.models import LegalDocument
from app.modules.legal.schemas import LegalPublish
from app.modules.legal.service import LegalService
from app.modules.pico_placa.models import PicoPlacaRule
from app.modules.places.models import Place
from app.modules.routing.models import TrafficFactor
from app.modules.semesters.models import Semester
from app.modules.semesters.repository import SemesterRepository
from app.modules.settings.service import SettingsService
from app.modules.users.models import User

logger = structlog.get_logger("seed")
SEED_DATA = Path(__file__).parent / "seed_data"

# Coordenadas APROXIMADAS alrededor del centro de Pamplona (7.3756 N, -72.6475 O).
# El equipo debe reemplazarlas por las reales desde el panel del superadmin.
SAMPLE_PLACES: list[tuple[str, PlaceKind, float, float]] = [
    ("Ciudad Universitaria (campus principal)", PlaceKind.CAMPUS, 7.3870, -72.6495),
    ("Sede Casona", PlaceKind.CAMPUS, 7.3762, -72.6468),
    ("Parque Principal Agueda Gallardo", PlaceKind.LANDMARK, 7.3756, -72.6475),
    ("Terminal de Transportes", PlaceKind.LANDMARK, 7.3712, -72.6512),
    ("Barrio El Carmen", PlaceKind.SECTOR, 7.3792, -72.6440),
    ("Barrio Cariongo", PlaceKind.SECTOR, 7.3705, -72.6433),
    ("Barrio Chapinero", PlaceKind.SECTOR, 7.3820, -72.6520),
]

# Reglas de EJEMPLO (lunes a viernes, dos digitos por dia). Ajustar al decreto vigente.
SAMPLE_PICO_PLACA: list[tuple[int, list[int]]] = [
    (0, [0, 1]),
    (1, [2, 3]),
    (2, [4, 5]),
    (3, [6, 7]),
    (4, [8, 9]),
]


def semester_for(day: date) -> tuple[str, date, date]:
    """Semestre academico tipico. Fechas de referencia: el superadmin las ajusta."""
    if day.month <= 6:
        return f"{day.year}-1", date(day.year, 2, 1), date(day.year, 6, 30)
    return f"{day.year}-2", date(day.year, 8, 1), date(day.year, 12, 15)


async def seed_settings(session: AsyncSession) -> None:
    created = await SettingsService(session).ensure_defaults()
    await session.commit()
    logger.info("seed_settings", created=created)


async def seed_superadmin(session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.superadmin_email or not settings.superadmin_password:
        logger.warning(
            "seed_superadmin_skipped", reason="SUPERADMIN_EMAIL o SUPERADMIN_PASSWORD vacios"
        )
        return
    exists = await session.scalar(select(User).where(User.email == settings.superadmin_email))
    if exists is not None:
        logger.info("seed_superadmin", created=False)
        return
    session.add(
        User(
            email=settings.superadmin_email.lower(),
            password_hash=hash_password(settings.superadmin_password.get_secret_value()),
            full_name=settings.superadmin_name,
            sex=settings.superadmin_sex,
            role=UserRole.SUPERADMIN,
            status=UserStatus.ACTIVE,
            two_factor_required=True,
        )
    )
    await session.commit()
    logger.info("seed_superadmin", created=True)


async def seed_semester(session: AsyncSession) -> date:
    today = local_today()
    current = await SemesterRepository(session).containing(today)
    if current is not None:
        logger.info("seed_semester", created=False, name=current.name)
        return current.starts_on
    name, starts_on, ends_on = semester_for(today)
    if await session.scalar(select(Semester).where(Semester.name == name)):
        logger.warning("seed_semester_skipped", reason="existe con otras fechas", name=name)
        return starts_on
    days = await SettingsService(session).get("revalidation_days")
    deadline = min(starts_on + timedelta(days=days), ends_on)
    session.add(
        Semester(name=name, starts_on=starts_on, ends_on=ends_on, revalidation_deadline=deadline)
    )
    await session.commit()
    logger.info(
        "seed_semester", created=True, name=name, today_inside=starts_on <= today <= ends_on
    )
    return starts_on


async def seed_places(session: AsyncSession) -> None:
    created = 0
    for name, kind, lat, lon in SAMPLE_PLACES:
        found = await session.scalar(select(Place).where(Place.name == name, Place.kind == kind))
        if found is None:
            session.add(Place(name=name, kind=kind, point=point(lat, lon)))
            created += 1
    await session.commit()
    logger.info("seed_places", created=created)


async def seed_pico_placa(session: AsyncSession, valid_from: date) -> None:
    if await session.scalar(select(func.count()).select_from(PicoPlacaRule)):
        logger.info("seed_pico_placa", created=0)
        return
    for vehicle_type in VehicleType:
        for weekday, digits in SAMPLE_PICO_PLACA:
            session.add(
                PicoPlacaRule(
                    vehicle_type=vehicle_type,
                    weekday=weekday,
                    restricted_digits=digits,
                    valid_from=valid_from,
                )
            )
    await session.commit()
    logger.info("seed_pico_placa", created=len(VehicleType) * len(SAMPLE_PICO_PLACA))


async def seed_traffic_factors(session: AsyncSession) -> None:
    """Factor 1.0 en cada franja: la ETA es la de OSRM hasta que haya viajes reales."""
    existing = {
        (group, hour)
        for group, hour in (
            await session.execute(select(TrafficFactor.weekday_group, TrafficFactor.hour))
        ).all()
    }
    created = 0
    for group in ("weekday", "saturday", "sunday"):
        for hour in range(24):
            if (group, hour) not in existing:
                session.add(TrafficFactor(weekday_group=group, hour=hour, factor=1.0, samples=0))
                created += 1
    await session.commit()
    logger.info("seed_traffic_factors", created=created)


async def seed_legal(session: AsyncSession) -> None:
    sources = {LegalKind.TERMS: "terms_es.md", LegalKind.DATA_POLICY: "data_policy_es.md"}
    for kind, filename in sources.items():
        current = await session.scalar(
            select(LegalDocument).where(
                LegalDocument.kind == kind,
                LegalDocument.language == Language.ES,
                LegalDocument.is_current.is_(True),
            )
        )
        if current is not None:
            continue
        body = (SEED_DATA / filename).read_text(encoding="utf-8")
        await LegalService(session).publish(
            LegalPublish(kind=kind, version="1.0", language=Language.ES, body_markdown=body),
            actor=None,
        )
        logger.info("seed_legal", kind=kind, version="1.0")


async def run() -> None:
    async with SessionLocal() as session:
        await seed_settings(session)
        await seed_superadmin(session)
        semester_start = await seed_semester(session)
        await seed_places(session)
        await seed_pico_placa(session, semester_start)
        await seed_legal(session)
        await seed_traffic_factors(session)


async def main() -> None:
    configure_logging(json_output=get_settings().environment != "development")
    try:
        await run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
