import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Authorship, Base, Timestamps, UUIDPrimaryKey, pg_enum
from app.core.enums import VehicleType


class Vehicle(UUIDPrimaryKey, Timestamps, Authorship, Base):
    """Vehiculo de un conductor. El borrado es logico: viajes pasados lo siguen referenciando."""

    __tablename__ = "vehicles"
    __table_args__ = (
        # Una placa solo puede estar registrada una vez entre los vehiculos no borrados.
        Index(
            "uq_vehicles_plate_alive",
            "plate",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "(type = 'car' AND capacity BETWEEN 2 AND 8) OR (type = 'motorcycle' AND capacity = 2)",
            name="capacity_by_type",
        ),
        CheckConstraint("plate = upper(plate)", name="plate_uppercase"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[VehicleType] = mapped_column(pg_enum(VehicleType, "vehicle_type"), nullable=False)
    plate: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    luggage_space: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    photo_path: Mapped[str | None] = mapped_column(Text)
    photo_content_type: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
