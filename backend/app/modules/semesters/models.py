from datetime import date

from sqlalchemy import CheckConstraint, Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class Semester(UUIDPrimaryKey, Timestamps, Base):
    """Calendario academico. La migracion agrega una restriccion de exclusion contra solapes."""

    __tablename__ = "semesters"
    __table_args__ = (
        CheckConstraint("ends_on > starts_on", name="dates_order"),
        CheckConstraint(
            "revalidation_deadline BETWEEN starts_on AND ends_on", name="deadline_in_range"
        ),
    )

    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    revalidation_deadline: Mapped[date] = mapped_column(Date, nullable=False)
