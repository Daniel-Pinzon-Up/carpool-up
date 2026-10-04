import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SemesterName = Annotated[
    str, StringConstraints(min_length=3, max_length=20, pattern=r"^[0-9A-Za-z][0-9A-Za-z _-]*$")
]


class SemesterCreate(BaseModel):
    name: SemesterName
    starts_on: date
    ends_on: date
    revalidation_deadline: date | None = Field(
        default=None,
        description="Si se omite: starts_on mas el parametro revalidation_days.",
    )


class SemesterUpdate(BaseModel):
    name: SemesterName | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    revalidation_deadline: date | None = None


class SemesterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    starts_on: date
    ends_on: date
    revalidation_deadline: date
    created_at: datetime
    updated_at: datetime
