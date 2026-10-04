from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.auth import CurrentUser
from app.core.deps import DbSession
from app.core.enums import DocKind
from app.modules.documents.service import DocumentService
from app.modules.users.schemas import DocumentSummary, MeOut, MeUpdate
from app.modules.users.service import UserService

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("")
async def get_me(user: CurrentUser, session: DbSession) -> MeOut:
    """Perfil propio, estado del documento y versiones legales pendientes de aceptar.

    Disponible tambien para cuentas pendientes o suspendidas: asi ven su estado.
    """
    return await UserService(session).me(user)


@router.patch("")
async def update_me(body: MeUpdate, user: CurrentUser, session: DbSession) -> MeOut:
    return await UserService(session).update_me(user, body)


@router.get("/documents")
async def list_documents(user: CurrentUser, session: DbSession) -> list[DocumentSummary]:
    documents = await DocumentService(session).history(user)
    return [DocumentSummary.model_validate(d) for d in documents]


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: CurrentUser,
    session: DbSession,
    kind: Annotated[DocKind, Form()],
    document: Annotated[UploadFile, File(description="JPG, PNG, WebP o PDF")],
) -> DocumentSummary:
    """Sube un carnet o constancia nuevo. Si hay uno pendiente de revision, lo reemplaza."""
    return DocumentSummary.model_validate(
        await DocumentService(session).upload(user, kind, document)
    )
