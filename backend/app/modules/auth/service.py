"""Registro, ingreso con 2FA condicional, sesiones con refresh rotativo y recuperacion."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.db import set_actor
from app.core.email import EmailQueue, code_email
from app.core.enums import AuthPurpose, UserStatus
from app.core.errors import AppError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    build_refresh_token,
    create_access_token,
    create_challenge_token,
    decode_challenge_token,
    hash_password,
    hash_secret,
    new_refresh_secret,
    parse_refresh_token,
    secrets_match,
    verify_password,
)
from app.core.storage import delete_private_file
from app.modules.auth.codes import CodeService, InvalidCodeError
from app.modules.auth.models import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.auth.schemas import AuthResult, LoginRequest, RegisterForm, SessionOut
from app.modules.documents.service import DocumentService
from app.modules.settings.service import SettingsService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

logger = structlog.get_logger("auth")

CHALLENGE_RESULTS = {
    AuthPurpose.EMAIL_VERIFICATION: "email_verification_required",
    AuthPurpose.TWO_FACTOR: "two_factor_required",
    AuthPurpose.PASSWORD_RESET: "password_reset_code_sent",
}


@dataclass(frozen=True)
class ClientInfo:
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True)
class Authenticated:
    result: AuthResult
    refresh_token: str


class InvalidCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__("INVALID_CREDENTIALS", "Email or password is incorrect", 401)


class RefreshInvalidError(AppError):
    def __init__(self, code: str = "REFRESH_INVALID") -> None:
        super().__init__(code, "The session is no longer valid", 401)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:2]}{'*' * max(3, len(local) - 2)}@{domain}"


def device_label_from(user_agent: str | None) -> str:
    """Etiqueta legible del dispositivo a partir del User-Agent."""
    ua = (user_agent or "").lower()
    browser = next(
        (
            name
            for key, name in [
                ("edg/", "Edge"),
                ("opr/", "Opera"),
                ("firefox", "Firefox"),
                ("chrome", "Chrome"),
                ("safari", "Safari"),
            ]
            if key in ua
        ),
        "Navegador",
    )
    system = next(
        (
            name
            for key, name in [
                ("android", "Android"),
                ("iphone", "iPhone"),
                ("ipad", "iPad"),
                ("windows", "Windows"),
                ("mac os", "macOS"),
                ("linux", "Linux"),
            ]
            if key in ua
        ),
        "",
    )
    return f"{browser} en {system}" if system else browser


class AuthService:
    def __init__(self, session: AsyncSession, emails: EmailQueue, client: ClientInfo) -> None:
        self.session = session
        self.emails = emails
        self.client = client
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)
        self.codes = CodeService(session)
        self.settings = SettingsService(session)

    # --- Utilidades ------------------------------------------------------------------------

    async def _check_password_policy(self, password: str, email: str) -> None:
        minimum = int(await self.settings.get("password_min_length"))
        if len(password) < minimum:
            raise AppError(
                "PASSWORD_TOO_SHORT", "Password is too short", 422, {"min_length": minimum}
            )
        if password.lower() == email.lower() or password.lower() == email.split("@")[0].lower():
            raise AppError("PASSWORD_TOO_WEAK", "Password must not match the email", 422)

    async def _send_code(self, user: User, purpose: AuthPurpose, code: str) -> None:
        minutes = await self.codes.minutes()
        try:
            await self.emails.enqueue(
                code_email(user.email, user.full_name, purpose, code, minutes)
            )
        except Exception:  # el usuario puede pedir reenvio; no se pierde el registro
            logger.exception("email_enqueue_failed", purpose=purpose.value)

    async def _challenge(
        self, user: User, purpose: AuthPurpose, *, strict_cooldown: bool = False
    ) -> AuthResult:
        """Emite (o reutiliza) un codigo y devuelve el desafio. Hace commit y luego encola."""
        issued = await self.codes.issue(user.id, purpose, strict_cooldown=strict_cooldown)
        await self.session.commit()
        if issued.code is not None:
            await self._send_code(user, purpose, issued.code)
        return AuthResult(
            result=CHALLENGE_RESULTS[purpose],
            challenge_id=create_challenge_token(user.id, purpose, await self.codes.minutes()),
            email_hint=mask_email(user.email),
            resend_after_seconds=issued.resend_after_seconds,
        )

    async def _open_session(self, user: User, device_label: str | None) -> Authenticated:
        set_actor(self.session, user.id)
        now = utcnow()
        secret = new_refresh_secret()
        user_session = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            refresh_token_hash=hash_secret(secret),
            device_label=device_label or device_label_from(self.client.user_agent),
            ip=self.client.ip,
            user_agent=(self.client.user_agent or "")[:300] or None,
            expires_at=now + timedelta(days=get_settings().refresh_token_days),
            last_seen_at=now,
        )
        self.sessions.add(user_session)
        user.last_login_at = now
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.session.commit()
        await self.session.refresh(user)
        return Authenticated(
            result=await self._authenticated_result(user, user_session.id),
            refresh_token=build_refresh_token(user_session.id, secret),
        )

    async def _authenticated_result(self, user: User, session_id: uuid.UUID) -> AuthResult:
        return AuthResult(
            result="authenticated",
            access_token=create_access_token(user.id, user.role, session_id),
            expires_in=get_settings().access_token_minutes * 60,
            user=await UserService(self.session).me(user),
        )

    async def _user_for_challenge(self, challenge_id: str, purpose: AuthPurpose) -> User:
        challenge = decode_challenge_token(challenge_id, purpose)
        if challenge is None:
            raise AppError("CHALLENGE_EXPIRED", "Start again to receive a new code", 400)
        user = await self.users.get(challenge.user_id)
        if user is None:
            raise InvalidCodeError()
        return user

    # --- Registro --------------------------------------------------------------------------

    async def register(self, form: RegisterForm, document: UploadFile) -> AuthResult:
        email = form.email.lower()
        suffix = get_settings().allowed_email_suffix.lower()
        if not email.endswith(suffix):
            raise AppError(
                "EMAIL_NOT_INSTITUTIONAL", "Use your institutional email", 422, {"suffix": suffix}
            )
        if not (form.accept_terms and form.accept_data_policy):
            raise AppError("TERMS_NOT_ACCEPTED", "Terms and data policy must be accepted", 422)
        await self._check_password_policy(form.password, email)
        if await self.users.email_exists(email):
            raise AppError("EMAIL_TAKEN", "There is already an account with this email", 409)

        documents = DocumentService(self.session)
        stored = await documents.store_file(document)
        try:
            user = User(
                email=email,
                password_hash=hash_password(form.password),
                full_name=form.full_name,
                sex=form.sex,
                program=form.program,
                role=form.role,
                status=UserStatus.PENDING_EMAIL,
                two_factor_required=True,
                terms_accepted_at=utcnow(),
            )
            self.users.add(user)
            await self.session.flush()
            set_actor(self.session, user.id)
            await documents.attach(user, form.doc_kind, stored)
            result = await self._challenge(user, AuthPurpose.EMAIL_VERIFICATION)
        except Exception:
            await self.session.rollback()
            delete_private_file(stored.path)
            raise
        logger.info("user_registered", user_id=str(user.id), role=user.role.value)
        return result

    # --- Ingreso ---------------------------------------------------------------------------

    async def login(self, data: LoginRequest) -> AuthResult | Authenticated:
        user = await self.users.by_email(data.email.lower())
        if user is None:
            verify_password(data.password, DUMMY_PASSWORD_HASH)  # mismo tiempo de respuesta
            raise InvalidCredentialsError()

        now = utcnow()
        if user.locked_until is not None and user.locked_until > now:
            raise AppError(
                "ACCOUNT_LOCKED",
                "Too many failed attempts",
                429,
                {"retry_after_seconds": int((user.locked_until - now).total_seconds()) + 1},
            )

        if not verify_password(data.password, user.password_hash):
            user.failed_login_attempts += 1
            max_attempts = int(await self.settings.get("login_max_attempts"))
            locked = user.failed_login_attempts >= max_attempts
            if locked:
                minutes = int(await self.settings.get("login_lockout_minutes"))
                user.locked_until = now + timedelta(minutes=minutes)
                user.failed_login_attempts = 0
            await self.session.commit()
            logger.info("login_failed", user_id=str(user.id), locked=locked)
            if locked:
                raise AppError(
                    "ACCOUNT_LOCKED",
                    "Too many failed attempts",
                    429,
                    {"retry_after_seconds": minutes * 60},
                )
            raise InvalidCredentialsError()

        if user.status == UserStatus.BLOCKED:
            raise AppError("ACCOUNT_BLOCKED", "This account is blocked", 403)
        user.failed_login_attempts = 0
        user.locked_until = None
        if user.status == UserStatus.PENDING_EMAIL:
            return await self._challenge(user, AuthPurpose.EMAIL_VERIFICATION)
        if user.two_factor_required:
            return await self._challenge(user, AuthPurpose.TWO_FACTOR)
        return await self._open_session(user, data.device_label)

    async def _verify(self, challenge_id: str, purpose: AuthPurpose, code: str) -> User:
        user = await self._user_for_challenge(challenge_id, purpose)
        valid = await self.codes.check(user.id, purpose, code)
        if not valid:
            await self.session.commit()  # el intento fallido queda contado
            raise InvalidCodeError()
        set_actor(self.session, user.id)
        return user

    async def verify_email(
        self, challenge_id: str, code: str, device_label: str | None
    ) -> Authenticated:
        """Confirmar el correo cuenta como el segundo factor del primer ingreso."""
        user = await self._verify(challenge_id, AuthPurpose.EMAIL_VERIFICATION, code)
        if user.status == UserStatus.PENDING_EMAIL:
            user.status = UserStatus.PENDING_APPROVAL
        user.two_factor_required = False
        return await self._open_session(user, device_label)

    async def verify_two_factor(
        self, challenge_id: str, code: str, device_label: str | None
    ) -> Authenticated:
        user = await self._verify(challenge_id, AuthPurpose.TWO_FACTOR, code)
        if user.status == UserStatus.BLOCKED:
            raise AppError("ACCOUNT_BLOCKED", "This account is blocked", 403)
        user.two_factor_required = False
        return await self._open_session(user, device_label)

    async def resend(self, challenge_id: str) -> int:
        """Reenvia el codigo del desafio. Sirve para los tres propositos."""
        for purpose in AuthPurpose:
            challenge = decode_challenge_token(challenge_id, purpose)
            if challenge is not None:
                break
        else:
            raise AppError("CHALLENGE_EXPIRED", "Start again to receive a new code", 400)
        user = await self.users.get(challenge.user_id)
        if user is None:  # desafio de un correo sin cuenta (recuperacion): misma respuesta
            return int(await self.settings.get("auth_code_resend_seconds"))
        result = await self._challenge(user, challenge.purpose, strict_cooldown=True)
        return result.resend_after_seconds or 0

    # --- Sesiones --------------------------------------------------------------------------

    async def refresh(self, refresh_token: str | None) -> Authenticated:
        """Rota el refresh token. Presentar uno ya usado revoca todas las sesiones."""
        parsed = parse_refresh_token(refresh_token or "")
        if parsed is None:
            raise RefreshInvalidError()
        session_id, secret = parsed
        user_session = await self.sessions.get(session_id)
        now = utcnow()
        if (
            user_session is None
            or user_session.revoked_at is not None
            or user_session.expires_at <= now
        ):
            raise RefreshInvalidError()
        if not secrets_match(secret, user_session.refresh_token_hash):
            revoked = await self.sessions.revoke_all(user_session.user_id, now)
            await self.session.commit()
            logger.warning(
                "refresh_token_reuse", user_id=str(user_session.user_id), revoked=revoked
            )
            raise RefreshInvalidError("REFRESH_REUSED")
        set_actor(self.session, user_session.user_id)
        user = await self.users.get(user_session.user_id)
        if user is None or user.status == UserStatus.BLOCKED:
            user_session.revoked_at = now
            await self.session.commit()
            raise RefreshInvalidError()
        new_secret = new_refresh_secret()
        user_session.refresh_token_hash = hash_secret(new_secret)
        user_session.last_seen_at = now
        user_session.expires_at = now + timedelta(days=get_settings().refresh_token_days)
        await self.session.commit()
        return Authenticated(
            result=await self._authenticated_result(user, user_session.id),
            refresh_token=build_refresh_token(user_session.id, new_secret),
        )

    async def logout(self, refresh_token: str | None) -> None:
        parsed = parse_refresh_token(refresh_token or "")
        if parsed is None:
            return
        user_session = await self.sessions.get(parsed[0])
        if (
            user_session is not None
            and user_session.revoked_at is None
            and secrets_match(parsed[1], user_session.refresh_token_hash)
        ):
            user_session.revoked_at = utcnow()
            await self.session.commit()

    async def logout_others(self, user: User, current_session: uuid.UUID | None) -> int:
        revoked = await self.sessions.revoke_all(user.id, utcnow(), keep=current_session)
        await self.session.commit()
        return revoked

    async def list_sessions(
        self, user: User, current_session: uuid.UUID | None
    ) -> list[SessionOut]:
        return [
            SessionOut(
                id=s.id,
                device_label=s.device_label,
                ip=s.ip,
                created_at=s.created_at,
                last_seen_at=s.last_seen_at,
                current=s.id == current_session,
            )
            for s in await self.sessions.active_for_user(user.id, utcnow())
        ]

    # --- Recuperacion ----------------------------------------------------------------------

    async def forgot_password(self, email: str) -> AuthResult:
        """Misma respuesta exista o no la cuenta, para no revelar correos registrados."""
        user = await self.users.by_email(email.lower())
        minutes = await self.codes.minutes()
        if user is None or user.status == UserStatus.BLOCKED:
            return AuthResult(
                result="password_reset_code_sent",
                challenge_id=create_challenge_token(
                    uuid.uuid4(), AuthPurpose.PASSWORD_RESET, minutes
                ),
                email_hint=mask_email(email.lower()),
                resend_after_seconds=int(await self.settings.get("auth_code_resend_seconds")),
            )
        return await self._challenge(user, AuthPurpose.PASSWORD_RESET)

    async def reset_password(self, challenge_id: str, code: str, new_password: str) -> None:
        """Cambia la clave, revoca todas las sesiones y vuelve a exigir el segundo factor."""
        challenge = decode_challenge_token(challenge_id, AuthPurpose.PASSWORD_RESET)
        if challenge is None:
            raise AppError("CHALLENGE_EXPIRED", "Start again to receive a new code", 400)
        user = await self.users.get(challenge.user_id)
        if user is None:
            raise InvalidCodeError()
        await self._check_password_policy(new_password, user.email)
        if not await self.codes.check(user.id, AuthPurpose.PASSWORD_RESET, code):
            await self.session.commit()
            raise InvalidCodeError()
        set_actor(self.session, user.id)
        now = utcnow()
        user.password_hash = hash_password(new_password)
        user.two_factor_required = True
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.sessions.revoke_all(user.id, now)
        await self.session.commit()
        logger.info("password_reset", user_id=str(user.id))
