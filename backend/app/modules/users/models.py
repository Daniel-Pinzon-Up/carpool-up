from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import Sex, UserRole, UserStatus


class User(UUIDPrimaryKey, Timestamps, Base):
    """Persona registrada. Un solo rol por usuario.

    Las sanciones viven en la misma fila: suspended_until (cuenta suspendida, nulo = hasta que
    un administrador la reactive) y booking_ban_until (reservas suspendidas por ausencias).
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    sex: Mapped[Sex] = mapped_column(pg_enum(Sex, "sex"), nullable=False)
    program: Mapped[str | None] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.PENDING_EMAIL
    )
    avatar_path: Mapped[str | None] = mapped_column(Text)
    payment_note: Mapped[str | None] = mapped_column(Text)
    two_factor_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    booking_ban_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # sin datos personales
        return f"User(id={self.id}, role={self.role}, status={self.status})"
