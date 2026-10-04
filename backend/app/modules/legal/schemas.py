import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.enums import Language, LegalKind

Version = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+(\.\d+)?$", max_length=20)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=50, max_length=200_000)]


class LegalPublish(BaseModel):
    kind: LegalKind
    version: Version
    language: Language
    body_markdown: Body


class LegalDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: LegalKind
    version: str
    language: Language
    body_markdown: str
    published_at: datetime
    is_current: bool


class LegalAccept(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
