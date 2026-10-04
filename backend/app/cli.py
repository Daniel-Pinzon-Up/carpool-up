"""Utilidades de desarrollo.

    python -m app.cli token <correo>   emite un token de acceso para probar la API a mano

El login real llega en el paso 2. Este comando se niega a correr en produccion.
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.security import create_access_token
from app.modules.users.models import User


async def issue_token(email: str) -> int:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
    await engine.dispose()
    if user is None:
        print(f"No existe un usuario con el correo {email}", file=sys.stderr)
        return 1
    print(create_access_token(user.id, user.role))
    return 0


def main(argv: list[str]) -> int:
    if get_settings().is_production:
        print("Este comando no esta disponible en produccion.", file=sys.stderr)
        return 2
    if len(argv) != 2 or argv[0] != "token":
        print(__doc__, file=sys.stderr)
        return 2
    return asyncio.run(issue_token(argv[1]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
