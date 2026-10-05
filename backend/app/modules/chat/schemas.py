import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.core.enums import ConversationKind
from app.modules.chat.models import MAX_MESSAGE_LENGTH

Body = Annotated[str, Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)]


class MessageIn(BaseModel):
    body: Body

    @field_validator("body")
    @classmethod
    def not_blank(cls, body: str) -> str:
        body = body.strip()
        if not body:
            raise ValueError("the message is empty")
        return body


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    body: str
    sent_at: datetime


class MemberOut(BaseModel):
    """Solo id, nombre y si es el conductor: nunca correo ni telefono."""

    id: uuid.UUID
    full_name: str
    is_driver: bool


class ConversationOut(BaseModel):
    id: uuid.UUID
    kind: ConversationKind
    trip_id: uuid.UUID | None
    series_id: uuid.UUID | None
    title: str = Field(description="Trayecto del viaje o de la serie")
    departs_at: datetime | None = Field(description="Salida del viaje (chat grupal y puntual)")
    counterpart: str | None = Field(description="Con quien es el chat directo")
    members: list[MemberOut]
    last_message: MessageOut | None
    unread: int
    closed: bool


class UnreadMessages(BaseModel):
    unread: int
    conversations: int
