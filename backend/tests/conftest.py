import os
from collections.abc import AsyncIterator, Awaitable, Callable

# Configuracion de prueba antes de importar la app.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_STORAGE", "memory://")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.db import get_session
from app.core.enums import Sex, UserRole, UserStatus
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.modules.users.models import User

API = "/api/v1"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Cliente sin base de datos para pruebas de humo."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Pruebas de integracion: PostgreSQL con PostGIS real (base carpool_test ya migrada).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(get_settings().database_url)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def db(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sesion dentro de una transaccion que se revierte al terminar la prueba.

    Los commit del codigo bajo prueba se convierten en savepoints.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def api(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP cuya app usa la sesion transaccional de la prueba."""
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


UserFactory = Callable[..., Awaitable[User]]


@pytest.fixture
def make_user(db: AsyncSession) -> UserFactory:
    counter = 0

    async def factory(
        role: UserRole = UserRole.PASSENGER,
        status: UserStatus = UserStatus.ACTIVE,
        sex: Sex = Sex.FEMALE,
    ) -> User:
        nonlocal counter
        counter += 1
        user = User(
            email=f"{role.value}{counter}@unipamplona.edu.co",
            password_hash=hash_password("clave-de-prueba-123"),
            full_name=f"Usuario {role.value} {counter}",
            sex=sex,
            role=role,
            status=status,
        )
        db.add(user)
        await db.flush()
        return user

    return factory


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
async def superadmin(make_user: UserFactory) -> User:
    return await make_user(UserRole.SUPERADMIN)


@pytest.fixture
def su_headers(superadmin: User) -> dict[str, str]:
    return auth(superadmin)
