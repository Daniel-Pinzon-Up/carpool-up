import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import Actor, CurrentUser, client_ip
from app.core.deps import DbSession
from app.core.enums import DocKind
from app.core.errors import NotFoundError
from app.core.storage import private_file_response
from app.modules.documents.service import DocumentService, LicenseService
from app.modules.users.deletion import AccountDeletion
from app.modules.users.schemas import (
    AccountDeleteRequest,
    DocumentSummary,
    LicenseSummary,
    MeOut,
    MeUpdate,
)
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


@router.post(
    "/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        409: {"description": "ACCOUNT_DELETE_NOT_ALLOWED o ACCOUNT_DELETE_TRIP_IN_PROGRESS"},
        422: {"description": "PASSWORD_INCORRECT"},
    },
)
async def delete_me(
    body: AccountDeleteRequest, user: CurrentUser, request: Request, session: DbSession
) -> None:
    """Elimina la cuenta propia: anonimiza los datos personales, borra documentos y contactos,
    retira a la persona de sus viajes futuros y cierra todas sus sesiones. No se puede deshacer.
    """
    await AccountDeletion(session).delete(Actor(user=user, ip=client_ip(request)), body.password)


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
    """Sube un documento de identidad nuevo. Si hay uno pendiente de revision, lo reemplaza."""
    return DocumentSummary.model_validate(
        await DocumentService(session).upload(user, kind, document)
    )


@router.get("/documents/{document_id}/file", response_class=FileResponse)
async def own_document_file(
    document_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> FileResponse:
    """El dueno puede ver lo que subio."""
    documents = await DocumentService(session).history(user)
    document = next((d for d in documents if d.id == document_id), None)
    if document is None:
        raise NotFoundError("document")
    return private_file_response(document.file_path, document.content_type)


@router.get("/license")
async def get_license(user: CurrentUser, session: DbSession) -> LicenseSummary | None:
    license_ = await LicenseService(session).get(user)
    return LicenseSummary.model_validate(license_) if license_ else None


@router.put("/license")
async def upload_license(
    user: CurrentUser,
    session: DbSession,
    expires_on: Annotated[date, Form(description="Fecha de vencimiento de la licencia")],
    document: Annotated[UploadFile, File(description="JPG, PNG, WebP o PDF")],
) -> LicenseSummary:
    """Sube o reemplaza la licencia de conduccion. Queda pendiente de aprobacion."""
    return LicenseSummary.model_validate(
        await LicenseService(session).upload(user, expires_on, document)
    )


@router.get("/license/file", response_class=FileResponse)
async def own_license_file(user: CurrentUser, session: DbSession) -> FileResponse:
    license_ = await LicenseService(session).get(user)
    if license_ is None:
        raise NotFoundError("license")
    return private_file_response(license_.file_path, license_.content_type)
