"""Utilidades de desarrollo.

    python -m app.cli token <correo>   emite un token de acceso para probar la API a mano
    python -m app.cli e2e-users        crea o renueva las cuentas de las pruebas E2E
    python -m app.cli email-test <correo>   envia un correo de prueba con la configuracion SMTP
    python -m app.cli verify-email <correo> da por verificado el correo de una cuenta ficticia
    python -m app.cli forget-unverified <correo>  borra un registro que nunca verifico su correo

e2e-users deja cuatro cuentas activas (pasajero, conductor, administrador y superadmin) con
los terminos vigentes aceptados y sin segundo factor, todas con una contrasena aleatoria nueva
en cada ejecucion. Imprime JSON con los correos y la contrasena para que las pruebas lo lean
de un archivo ignorado por git; nunca se escribe en el repositorio.

verify-email sirve para las personas de prueba sin buzon real: hace lo mismo que escribir el
codigo (pasa de pending_email a pending_approval y quita el segundo factor), y la cuenta sigue
el camino normal: un administrador aprueba su documento desde el panel. forget-unverified borra
solo cuentas en pending_email (sin viajes ni historial) para repetir un registro desde cero.

token y e2e-users se niegan a correr en produccion; email-test tambien sirve alli para
comprobar el servidor de correo antes de abrir el registro.
"""

import asyncio
import json
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.email import OutgoingEmail, send_smtp
from app.core.enums import Language, Sex, UserRole, UserStatus
from app.core.security import create_access_token, hash_password
from app.core.storage import delete_private_file
from app.models_registry import import_all_models
from app.modules.documents.models import DriverLicense, IdentityDocument
from app.modules.legal.service import LegalService
from app.modules.users.models import User

E2E_USERS: list[tuple[UserRole, str, str, Sex]] = [
    (UserRole.PASSENGER, "e2e.pasajero@unipamplona.edu.co", "Pasajera E2E", Sex.FEMALE),
    (UserRole.DRIVER, "e2e.conductor@unipamplona.edu.co", "Conductor E2E", Sex.MALE),
    (UserRole.ADMIN, "e2e.admin@unipamplona.edu.co", "Administradora E2E", Sex.FEMALE),
    (UserRole.SUPERADMIN, "e2e.superadmin@unipamplona.edu.co", "Superadmin E2E", Sex.MALE),
]


async def issue_token(email: str) -> int:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
    await engine.dispose()
    if user is None:
        print(f"No existe un usuario con el correo {email}", file=sys.stderr)
        return 1
    print(create_access_token(user.id, user.role))
    return 0


async def mark_email_verified(session: AsyncSession, email: str) -> str:
    """Lo mismo que verificar el codigo, sin buzon. Devuelve el estado resultante."""
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        raise LookupError(f"No existe un usuario con el correo {email}")
    if user.status == UserStatus.PENDING_EMAIL:
        user.status = UserStatus.PENDING_APPROVAL
    user.two_factor_required = False
    user.failed_login_attempts = 0
    user.locked_until = None
    await session.flush()
    return user.status.value


async def forget_unverified(session: AsyncSession, email: str) -> None:
    """Borra una cuenta que nunca verifico su correo, con sus archivos privados."""
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        raise LookupError(f"No existe un usuario con el correo {email}")
    if user.status != UserStatus.PENDING_EMAIL:
        raise PermissionError(
            f"{email} ya verifico su correo ({user.status.value}): no se borra. "
            "Para quitarla, que la persona elimine su cuenta desde el perfil."
        )
    paths = list(
        await session.scalars(
            select(IdentityDocument.file_path).where(IdentityDocument.user_id == user.id)
        )
    )
    paths += await session.scalars(
        select(DriverLicense.file_path).where(DriverLicense.user_id == user.id)
    )
    for path in paths:
        delete_private_file(path)
    await session.delete(user)
    await session.flush()


async def run_on_user(action: str, email: str) -> int:
    import_all_models()
    try:
        async with SessionLocal() as session:
            if action == "verify-email":
                status = await mark_email_verified(session, email)
                message = f"{email}: correo verificado, estado {status}, sin segundo factor."
            else:
                await forget_unverified(session, email)
                message = (
                    f"{email}: registro sin verificar borrado. Ya se puede registrar de nuevo."
                )
            await session.commit()
    except (LookupError, PermissionError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print(message)
    return 0


async def e2e_users() -> int:
    import_all_models()
    password = secrets.token_urlsafe(18)
    accounts: dict[str, str] = {}
    async with SessionLocal() as session:
        legal = LegalService(session)
        for role, email, name, sex in E2E_USERS:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, full_name=name, sex=sex, role=role, password_hash="")
                session.add(user)
            user.password_hash = hash_password(password)
            user.role = role
            user.status = UserStatus.ACTIVE
            user.two_factor_required = False
            user.failed_login_attempts = 0
            user.locked_until = None
            user.preferred_language = Language.ES
            await session.flush()
            legal.record_acceptance(user.id, await legal.pending_for(user), None)
            accounts[role.value] = email
        await session.commit()
    await engine.dispose()
    print(json.dumps({"password": password, "accounts": accounts}))
    return 0


async def email_test(to: str) -> int:
    settings = get_settings()
    server = f"{settings.smtp_host}:{settings.smtp_port}"
    try:
        await send_smtp(
            OutgoingEmail(
                to=to,
                subject="Carpool UP: correo de prueba",
                text="Si lees esto, el envío de correos de Carpool UP funciona.",
                html="<p>Si lees esto, el envío de correos de Carpool UP funciona.</p>",
            )
        )
    except Exception as error:  # la causa ayuda a corregir SMTP_*
        print(f"No se pudo enviar por {server}: {error!r}", file=sys.stderr)
        return 1
    print(f"Enviado por {server}. Revisa la bandeja de entrada y la de spam.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "email-test":
        return asyncio.run(email_test(argv[1]))
    if get_settings().is_production:
        print("Este comando no esta disponible en produccion.", file=sys.stderr)
        return 2
    if len(argv) == 2 and argv[0] == "token":
        return asyncio.run(issue_token(argv[1]))
    if len(argv) == 2 and argv[0] in ("verify-email", "forget-unverified"):
        return asyncio.run(run_on_user(argv[0], argv[1]))
    if argv == ["e2e-users"]:
        return asyncio.run(e2e_users())
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
