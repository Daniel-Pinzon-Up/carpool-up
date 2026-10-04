import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SettingOut(BaseModel):
    key: str
    value: Any
    description: str
    updated_at: datetime | None
    updated_by: uuid.UUID | None


class SettingUpdate(BaseModel):
    value: Any
