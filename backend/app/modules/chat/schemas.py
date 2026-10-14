import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

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
    """Chat de un viaje: su id es el id del viaje."""

    id: uuid.UUID
    trip_id: uuid.UUID
    title: str = Field(description="Trayecto del viaje")
    departs_at: datetime
    members: list[MemberOut]
    last_message: MessageOut | None
    unread: int
    closed: bool = Field(description="El viaje termino o se cancelo: solo lectura")


class UnreadMessages(BaseModel):
    unread: int
    conversations: int
