"""Utilidades de desarrollo.

    python -m app.cli token <correo>   emite un token de acceso para probar la API a mano
    python -m app.cli e2e-users        crea o renueva las cuentas de las pruebas E2E

e2e-users deja cuatro cuentas activas (pasajero, conductor, administrador y superadmin) con
los terminos vigentes aceptados y sin segundo factor, todas con una contrasena aleatoria nueva
en cada ejecucion. Imprime JSON con los correos y la contrasena para que las pruebas lo lean
de un archivo ignorado por git; nunca se escribe en el repositorio.

Estos comandos se niegan a correr en produccion.
"""

import asyncio
import json
import secrets
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.enums import Language, Sex, UserRole, UserStatus
from app.core.security import create_access_token, hash_password
from app.models_registry import import_all_models
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


def main(argv: list[str]) -> int:
    if get_settings().is_production:
        print("Este comando no esta disponible en produccion.", file=sys.stderr)
        return 2
    if len(argv) == 2 and argv[0] == "token":
        return asyncio.run(issue_token(argv[1]))
    if argv == ["e2e-users"]:
        return asyncio.run(e2e_users())
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
