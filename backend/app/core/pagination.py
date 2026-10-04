"""Paginacion por cursor sobre (created_at, id), estable aunque lleguen filas nuevas."""

import base64
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.errors import AppError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_at, row_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(created_at), uuid.UUID(row_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("INVALID_CURSOR", "Invalid pagination cursor", 400) from exc
