from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Index, SmallInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import VehicleType


class PicoPlacaRule(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Restriccion por dia de la semana (0 = lunes) segun el ultimo digito numerico de la placa."""

    __tablename__ = "pico_placa_rules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint(
            "cardinality(restricted_digits) > 0 "
            "AND restricted_digits <@ ARRAY[0,1,2,3,4,5,6,7,8,9]::smallint[]",
            name="digits_range",
        ),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="validity_order"),
        Index("ix_pico_placa_lookup", "vehicle_type", "weekday", "is_active"),
    )

    vehicle_type: Mapped[VehicleType] = mapped_column(
        pg_enum(VehicleType, "vehicle_type"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    restricted_digits: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
