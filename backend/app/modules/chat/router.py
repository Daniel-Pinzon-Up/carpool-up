import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.core.auth import ActiveUser
from app.core.deps import DbSession
from app.core.rate_limit import limiter
from app.modules.chat.schemas import ConversationOut, MessageIn, MessageOut, UnreadMessages
from app.modules.chat.service import HISTORY_LIMIT, ChatService

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.get("")
async def list_conversations(user: ActiveUser, session: DbSession) -> list[ConversationOut]:
    """Chats del usuario: uno por cada viaje en el que participa."""
    return await ChatService(session).list_for(user)


@router.get("/unread")
async def unread_messages(user: ActiveUser, session: DbSession) -> UnreadMessages:
    return await ChatService(session).unread_total(user)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, user: ActiveUser, session: DbSession
) -> ConversationOut:
    return await ChatService(session).get(user, conversation_id)


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    user: ActiveUser,
    session: DbSession,
    before: uuid.UUID | None = None,
    after: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = HISTORY_LIMIT,
) -> list[MessageOut]:
    """Historial en orden cronologico. before pagina hacia atras; after trae lo nuevo desde
    el ultimo mensaje visto (al reconectar el WebSocket)."""
    return await ChatService(session).history(
        user, conversation_id, before=before, after=after, limit=limit
    )


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "CONVERSATION_CLOSED"}},
)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: MessageIn,
    user: ActiveUser,
    session: DbSession,
) -> MessageOut:
    """Respaldo HTTP del envio (el cliente usa chat.send por WebSocket cuando esta conectado)."""
    return await ChatService(session).send(user, conversation_id, body.body)


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(conversation_id: uuid.UUID, user: ActiveUser, session: DbSession) -> None:
    await ChatService(session).mark_read(user, conversation_id)
