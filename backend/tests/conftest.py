import json
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

# Configuracion de prueba antes de importar la app.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_STORAGE", "memory://")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core import realtime
from app.core.clock import local_today, utcnow
from app.core.config import get_settings
from app.core.db import get_session
from app.core.email import OutgoingEmail
from app.core.enums import (
    Language,
    LegalKind,
    PlaceKind,
    ReviewStatus,
    Sex,
    UserRole,
    UserStatus,
    VehicleType,
)
from app.core.geo import point
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.modules.auth.router import get_email_queue
from app.modules.documents.models import DriverLicense
from app.modules.legal.models import LegalDocument
from app.modules.places.models import Place
from app.modules.routing.osrm import Leg, RouteResult
from app.modules.routing.router import get_route_provider
from app.modules.safety import location
from app.modules.semesters.models import Semester
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

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


class Outbox:
    """Reemplaza la cola de correos (Redis/ARQ) en las pruebas."""

    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []

    async def enqueue(self, email: OutgoingEmail) -> None:
        self.sent.append(email)

    def last_code(self, to: str | None = None) -> str:
        emails = [e for e in self.sent if to is None or e.to == to]
        assert emails, "no se envio ningun correo"
        match = re.search(r"\b(\d{6})\b", emails[-1].text)
        assert match, "el correo no trae codigo"
        return match.group(1)


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


class EventLog:
    """Eventos en tiempo real publicados durante la prueba (en vez de Redis)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, data: str) -> None:
        self.published.append((channel, json.loads(data)))

    async def on(self, channel: str) -> list[dict[str, Any]]:
        await realtime.drain()
        return [payload for name, payload in self.published if name == channel]


@pytest.fixture(autouse=True)
def events() -> Iterator[EventLog]:
    log = EventLog()
    previous = realtime.set_publisher(log.publish)
    yield log
    realtime.set_publisher(previous)


class MemoryLocations:
    """Ubicaciones en vivo en memoria (en vez de Redis)."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ttl: int) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


@pytest.fixture(autouse=True)
def locations() -> Iterator[MemoryLocations]:
    store = MemoryLocations()
    previous = location.set_backend(store)
    yield store
    location.set_backend(previous)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Archivos en una carpeta temporal, cookie sin Secure (el cliente de prueba usa http)
    y contadores del limitador en cero para que una prueba no afecte a otra."""
    limiter.reset()
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "cookie_secure", False)


@pytest.fixture
async def api(db: AsyncSession, outbox: Outbox) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP cuya app usa la sesion transaccional de la prueba."""
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_email_queue] = lambda: outbox
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


@pytest.fixture
async def legal_docs(db: AsyncSession) -> list[LegalDocument]:
    """Terminos y politica de datos vigentes en espanol (requisito del registro)."""
    docs = [
        LegalDocument(
            kind=kind,
            version="1.0",
            language=Language.ES,
            body_markdown="Texto legal de prueba con la longitud minima exigida por el esquema.",
            published_at=utcnow(),
            is_current=True,
        )
        for kind in LegalKind
    ]
    db.add_all(docs)
    await db.flush()
    return docs


# --- Rutas sin OSRM ---------------------------------------------------------------------


class FakeProvider:
    """OSRM en memoria: cada tramo mide 2 km y dura 300 s."""

    def __init__(self) -> None:
        self.calls: list[list[tuple[float, float]]] = []

    async def route(self, points: list[tuple[float, float]]) -> RouteResult:
        self.calls.append(points)
        legs = [Leg(2000.0, 300.0) for _ in points[1:]]
        return RouteResult(
            coordinates=[[lon, lat] for lat, lon in points],
            distance_m=sum(leg.distance_m for leg in legs),
            duration_s=sum(leg.duration_s for leg in legs),
            legs=legs,
        )


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
async def routing_api(
    db: AsyncSession, outbox: Outbox, provider: FakeProvider
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_email_queue] = lambda: outbox
    app.dependency_overrides[get_route_provider] = lambda: provider
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# --- Conductores y lugares para viajes ---------------------------------------------------


@pytest.fixture
async def places(db: AsyncSession) -> list[Place]:
    rows = [
        Place(name="Ciudad Universitaria", kind=PlaceKind.CAMPUS, point=point(7.3870, -72.6495)),
        Place(name="Sede Casona", kind=PlaceKind.CAMPUS, point=point(7.3762, -72.6468)),
        Place(name="Terminal", kind=PlaceKind.LANDMARK, point=point(7.3712, -72.6512)),
    ]
    db.add_all(rows)
    await db.flush()
    return rows


async def make_driver(
    db: AsyncSession, make_user: UserFactory, sex: Sex = Sex.FEMALE, plate: str = "ABC123"
) -> tuple[User, Vehicle]:
    user = await make_user(UserRole.DRIVER, sex=sex)
    db.add(
        DriverLicense(
            user_id=user.id,
            file_path="licenses/x.pdf",
            content_type="application/pdf",
            expires_on=local_today() + timedelta(days=365),
            status=ReviewStatus.APPROVED,
        )
    )
    vehicle = Vehicle(
        owner_id=user.id,
        type=VehicleType.CAR,
        plate=plate,
        brand="Chevrolet",
        model="Spark",
        color="Gris",
        year=2018,
        capacity=5,
    )
    db.add(vehicle)
    await db.flush()
    return user, vehicle


@pytest.fixture
async def driver(db: AsyncSession, make_user: UserFactory) -> tuple[User, Vehicle]:
    return await make_driver(db, make_user)


@pytest.fixture
async def semester(db: AsyncSession) -> Semester:
    today = local_today()
    row = Semester(
        name="2026-T",
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=90),
        revalidation_deadline=today,
    )
    db.add(row)
    await db.flush()
    return row
