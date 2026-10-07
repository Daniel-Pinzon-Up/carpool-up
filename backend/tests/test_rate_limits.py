"""Limites de peticiones: la renovacion de sesion se cuenta por sesion, no por IP."""

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import UserRole
from app.core.security import build_refresh_token, hash_secret, new_refresh_secret
from app.modules.auth.models import UserSession
from app.modules.auth.router import REFRESH_COOKIE
from app.modules.users.models import User
from tests.conftest import API, UserFactory


async def session_cookie(db: AsyncSession, user: User) -> str:
    secret = new_refresh_secret()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_secret(secret),
        device_label="Prueba",
        expires_at=utcnow() + timedelta(days=1),
        last_seen_at=utcnow(),
    )
    db.add(session)
    await db.flush()
    return build_refresh_token(session.id, secret)


async def refresh(api: AsyncClient, cookie: str) -> tuple[int, str]:
    api.cookies.clear()
    api.cookies.set(REFRESH_COOKIE, cookie)
    response = await api.post(f"{API}/auth/refresh")
    return response.status_code, response.cookies.get(REFRESH_COOKIE) or cookie


async def test_refresh_limit_counts_each_session_not_the_shared_ip(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    """En el campus muchas personas salen por la misma IP: una no debe agotar el cupo de otra."""
    first = await session_cookie(db, await make_user(UserRole.PASSENGER))
    second = await session_cookie(db, await make_user(UserRole.PASSENGER))

    for _ in range(30):
        status, first = await refresh(api, first)
        assert status == 200
    status, _ = await refresh(api, first)
    assert status == 429

    status, _ = await refresh(api, second)
    assert status == 200
