from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Cookie, Depends, File, Form, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from slowapi.util import get_remote_address

from app.core.auth import Claims, CurrentUser, client_ip
from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.email import ArqEmailQueue, EmailQueue
from app.core.enums import DocKind, Language, Sex, UserRole
from app.core.rate_limit import limiter
from app.core.security import parse_refresh_token
from app.modules.auth.schemas import (
    AuthResult,
    CodeVerifyRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterForm,
    ResendRequest,
    ResendResult,
    ResetPasswordRequest,
    RevokedSessions,
    SessionOut,
)
from app.modules.auth.service import Authenticated, AuthService, ClientInfo

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "cp_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


async def get_email_queue(request: Request) -> EmailQueue:
    """Cola de correos sobre Redis (ARQ). Las pruebas la reemplazan por una bandeja en memoria."""
    pool = getattr(request.app.state, "arq", None)
    if pool is None:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        request.app.state.arq = pool
    return ArqEmailQueue(pool)


def get_auth_service(
    request: Request, session: DbSession, emails: Annotated[EmailQueue, Depends(get_email_queue)]
) -> AuthService:
    info = ClientInfo(ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    return AuthService(session, emails, info)


Auth = Annotated[AuthService, Depends(get_auth_service)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def finish(response: Response, outcome: AuthResult | Authenticated) -> AuthResult:
    if isinstance(outcome, Authenticated):
        set_refresh_cookie(response, outcome.refresh_token)
        return outcome.result
    return outcome


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    auth: Auth,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    full_name: Annotated[str, Form()],
    sex: Annotated[Sex, Form()],
    role: Annotated[UserRole, Form(description="passenger o driver")],
    doc_kind: Annotated[DocKind, Form()],
    accept_terms: Annotated[bool, Form()],
    accept_data_policy: Annotated[bool, Form()],
    document: Annotated[
        UploadFile, File(description="Documento de identidad: JPG, PNG, WebP, PDF")
    ],
    program: Annotated[str | None, Form()] = None,
    preferred_language: Annotated[Language, Form()] = Language.ES,
) -> AuthResult:
    """Crea la cuenta en pending_email y envia el codigo de verificacion al correo."""
    try:
        form = RegisterForm(
            email=email,
            password=password,
            full_name=full_name,
            sex=sex,
            role=role,
            doc_kind=doc_kind,
            accept_terms=accept_terms,
            accept_data_policy=accept_data_policy,
            program=program or None,
            preferred_language=preferred_language,
        )
    except ValidationError as exc:
        # Mismo formato que los errores de validacion del resto de la API.
        raise RequestValidationError(
            [{**error, "loc": ("body", *error["loc"])} for error in exc.errors()]
        ) from exc
    return await auth.register(form, document)


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response, body: LoginRequest, auth: Auth) -> AuthResult:
    """Contrasena. Puede pedir verificar el correo o el segundo factor antes de abrir sesion."""
    return finish(response, await auth.login(body))


@router.post("/verify-email")
@limiter.limit("10/minute")
async def verify_email(
    request: Request, response: Response, body: CodeVerifyRequest, auth: Auth
) -> AuthResult:
    outcome = await auth.verify_email(body.challenge_id, body.code, body.device_label)
    return finish(response, outcome)


@router.post("/2fa/verify")
@limiter.limit("10/minute")
async def verify_two_factor(
    request: Request, response: Response, body: CodeVerifyRequest, auth: Auth
) -> AuthResult:
    outcome = await auth.verify_two_factor(body.challenge_id, body.code, body.device_label)
    return finish(response, outcome)


@router.post("/codes/resend")
@limiter.limit("5/minute")
async def resend_code(request: Request, body: ResendRequest, auth: Auth) -> ResendResult:
    return ResendResult(resend_after_seconds=await auth.resend(body.challenge_id))


def refresh_key(request: Request) -> str:
    """Limite por sesion: en el campus muchas personas comparten una IP publica. Sin una cookie
    con forma valida cuenta la IP (y el tope por IP de abajo frena a quien invente sesiones)."""
    parsed = parse_refresh_token(request.cookies.get(REFRESH_COOKIE) or "")
    return f"session:{parsed[0]}" if parsed else get_remote_address(request)


@router.post("/refresh")
@limiter.limit("300/minute")
@limiter.limit("30/minute", key_func=refresh_key)
async def refresh(
    request: Request, response: Response, auth: Auth, token: RefreshCookie = None
) -> AuthResult:
    """Renueva el token de acceso con la cookie HttpOnly y la rota."""
    try:
        outcome = await auth.refresh(token)
    except Exception:
        clear_refresh_cookie(response)
        raise
    return finish(response, outcome)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, auth: Auth, token: RefreshCookie = None) -> None:
    await auth.logout(token)
    clear_refresh_cookie(response)


@router.post("/logout-others")
async def logout_others(user: CurrentUser, claims: Claims, auth: Auth) -> RevokedSessions:
    """Cierra todas las sesiones salvo la actual."""
    return RevokedSessions(revoked=await auth.logout_others(user, claims.session_id))


@router.get("/sessions")
async def list_sessions(user: CurrentUser, claims: Claims, auth: Auth) -> list[SessionOut]:
    return await auth.list_sessions(user, claims.session_id)


@router.post("/password/forgot")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, auth: Auth) -> AuthResult:
    """Responde igual exista o no la cuenta."""
    return await auth.forgot_password(body.email)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def reset_password(request: Request, body: ResetPasswordRequest, auth: Auth) -> None:
    """Cambia la contrasena con el codigo y cierra todas las sesiones."""
    await auth.reset_password(body.challenge_id, body.code, body.new_password)
