from typing import Any

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps


class SystemSetting(Timestamps, Authorship, Base):
    """Parametro global de negocio. La clave es natural y estable, por eso es la PK."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
