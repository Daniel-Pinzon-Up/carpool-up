from fastapi import APIRouter, Request, status

from app.core.auth import CurrentUser, SuperAdmin, SuperAdminActor, client_ip
from app.core.deps import DbSession
from app.core.enums import Language
from app.modules.legal.schemas import LegalAccept, LegalDocumentOut, LegalPublish
from app.modules.legal.service import LegalService

router = APIRouter(prefix="/legal", tags=["legal"])
admin_router = APIRouter(prefix="/admin/legal", tags=["admin: legal"])


@router.get("/current")
async def current_documents(
    session: DbSession, language: Language = Language.ES
) -> list[LegalDocumentOut]:
    """Terminos y politica de datos vigentes. Publico: se muestran antes del registro."""
    docs = await LegalService(session).current(language)
    return [LegalDocumentOut.model_validate(d) for d in docs]


@router.post("/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_documents(
    body: LegalAccept, request: Request, user: CurrentUser, session: DbSession
) -> None:
    """Acepta versiones vigentes nuevas (cuando cambian los terminos tras el registro)."""
    await LegalService(session).accept(user, body.document_ids, client_ip(request))


@admin_router.get("")
async def list_documents(session: DbSession, _: SuperAdmin) -> list[LegalDocumentOut]:
    return [LegalDocumentOut.model_validate(d) for d in await LegalService(session).list_all()]


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def publish_document(
    body: LegalPublish, session: DbSession, actor: SuperAdminActor
) -> LegalDocumentOut:
    """Publica una version nueva. Los usuarios deberan aceptarla (paso 2)."""
    return LegalDocumentOut.model_validate(await LegalService(session).publish(body, actor))
