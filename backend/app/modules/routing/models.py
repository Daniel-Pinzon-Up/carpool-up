from sqlalchemy import CheckConstraint, Integer, Numeric, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey


class TrafficFactor(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Correccion de la duracion de OSRM por franja (seccion 5.4).

    ETA mostrada = duracion de OSRM * factor. Un job semanal (paso 10) lo recalcula con la
    mediana de duracion real / duracion estimada de los viajes completados.
    """

    __tablename__ = "traffic_factors"
    __table_args__ = (
        UniqueConstraint("weekday_group", "hour", name="uq_traffic_factors_slot"),
        CheckConstraint("weekday_group IN ('weekday', 'saturday', 'sunday')", name="group_values"),
        CheckConstraint("hour BETWEEN 0 AND 23", name="hour_range"),
        CheckConstraint("factor BETWEEN 0.5 AND 3.0", name="factor_range"),
    )

    weekday_group: Mapped[str] = mapped_column(Text, nullable=False)
    hour: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    factor: Mapped[float] = mapped_column(
        Numeric(4, 2, asdecimal=False), nullable=False, default=1.0
    )
    samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
