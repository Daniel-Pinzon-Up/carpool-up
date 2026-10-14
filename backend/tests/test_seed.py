"""Datos semilla: lo que deja make up en una base nueva, y que repetirlo no duplica nada."""

from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed
from app.core.enums import Sex, UserRole
from app.modules.pico_placa.models import PicoPlacaRule
from app.modules.places.models import Place
from app.modules.semesters.models import Semester
from app.modules.settings.models import SystemSetting
from app.modules.users.models import User


async def run_all(db: AsyncSession) -> None:
    await seed.seed_settings(db)
    await seed.seed_superadmin(db)
    start = await seed.seed_semester(db)
    await seed.seed_places(db)
    await seed.seed_pico_placa(db, start)


async def total(db: AsyncSession, model: type) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def test_seed_fills_a_new_database_and_is_idempotent(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: SimpleNamespace(
            superadmin_email="Superadmin.Semilla@unipamplona.edu.co",
            superadmin_password=SecretStr("una-clave-larga-de-prueba"),
            superadmin_name="Superadmin Semilla",
            superadmin_sex=Sex.FEMALE,
        ),
    )
    await run_all(db)
    first = {
        model: await total(db, model)
        for model in (
            SystemSetting,
            Semester,
            Place,
            PicoPlacaRule,
            User,
        )
    }
    assert first[Semester] == 1
    assert first[Place] == len(seed.SAMPLE_PLACES)
    assert first[PicoPlacaRule] == 2 * len(seed.SAMPLE_PICO_PLACA)
    assert first[SystemSetting] > 25

    admin = await db.scalar(select(User).where(User.role == UserRole.SUPERADMIN))
    assert admin is not None
    assert admin.email == "superadmin.semilla@unipamplona.edu.co"
    assert admin.two_factor_required

    await run_all(db)
    for model, count in first.items():
        assert await total(db, model) == count, model.__name__


async def test_seed_skips_superadmin_without_credentials(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: SimpleNamespace(superadmin_email="", superadmin_password=None),
    )
    await seed.seed_superadmin(db)
    assert await db.scalar(select(User).where(User.role == UserRole.SUPERADMIN)) is None
