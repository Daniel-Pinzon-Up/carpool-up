import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base


class UserStats(Authorship, Base):
    """Resumen calculado de cada usuario (seccion 5.3) para no recalcular en cada consulta.

    Se recalcula desde las tablas de origen al cerrar un viaje, al marcar un no-show, al
    cancelar un viaje del conductor y al recibir una calificacion.
    """

    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rating_avg: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trips_as_driver: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trips_as_passenger: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    driver_cancellations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passenger_no_shows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Promedio por criterio: {"punctuality": 4.5, ...}
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
