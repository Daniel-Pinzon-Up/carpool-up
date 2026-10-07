"""Configuracion: en produccion el servidor no arranca con claves de ejemplo."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SAFE = {
    "environment": "production",
    "secret_key": "q8Zr2Lw9Xc4Vb7Nm1Kp5Hs3Jd6Fg0Ta-Ue",
    "database_url": "postgresql+asyncpg://carpool:Otra-Clave-Segura-41@db:5432/carpool",
    "superadmin_password": "Una-Frase-Larga-Del-Superadmin",
    "cookie_secure": True,
}


def make(**overrides: object) -> Settings:
    return Settings(_env_file=None, **{**SAFE, **overrides})  # type: ignore[arg-type]


def test_safe_production_settings_are_accepted() -> None:
    assert make().is_production


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"secret_key": "cambia-esta-clave-por-una-larga-y-aleatoria"}, "SECRET_KEY"),
        ({"secret_key": "dev-insecure-key-change-me-0123456789"}, "SECRET_KEY"),
        ({"secret_key": "a" * 40}, "SECRET_KEY"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"superadmin_password": "cambia-esta-clave"}, "SUPERADMIN_PASSWORD"),
        (
            {"database_url": "postgresql+asyncpg://carpool:carpool_dev_password@db:5432/carpool"},
            "DATABASE_URL",
        ),
    ],
)
def test_production_refuses_example_secrets(override: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        make(**override)


def test_development_keeps_working_with_the_example_values() -> None:
    settings = make(
        environment="development", secret_key="cambia-esta-clave-por-una-larga-y-aleatoria"
    )
    assert not settings.is_production
