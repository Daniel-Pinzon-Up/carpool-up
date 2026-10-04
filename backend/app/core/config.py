from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.enums import Sex


class Settings(BaseSettings):
    """Configuracion de infraestructura leida del entorno.

    Las reglas de negocio configurables no viven aqui: estan en la tabla system_settings.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    project_name: str = "carpool"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://carpool:carpool@localhost:5432/carpool"
    redis_url: str = "redis://localhost:6379/0"

    # HS256 requiere al menos 32 bytes de clave (RFC 7518).
    secret_key: str = Field(default="dev-insecure-key-change-me-0123456789", min_length=32)
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:4200"]
    cookie_secure: bool = True

    allowed_email_suffix: str = ".edu.co"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-responder@carpool.local"

    storage_dir: str = "./storage"
    osrm_url: str = "http://localhost:5000"

    superadmin_email: str | None = None
    superadmin_password: SecretStr | None = None
    superadmin_name: str = "Superadministrador"
    superadmin_sex: Sex = Sex.FEMALE

    rate_limit_default: str = "120/minute"
    rate_limit_storage: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
