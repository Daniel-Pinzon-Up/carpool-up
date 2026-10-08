"""Comandos de desarrollo para las personas de prueba sin buzon real."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import forget_unverified, mark_email_verified
from app.core.enums import UserRole, UserStatus
from app.modules.users.models import User
from tests.conftest import UserFactory


async def test_verify_email_moves_the_account_to_review_without_second_factor(
    db: AsyncSession, make_user: UserFactory
) -> None:
    user = await make_user(UserRole.PASSENGER, UserStatus.PENDING_EMAIL)
    user.two_factor_required = True
    user.failed_login_attempts = 4

    assert await mark_email_verified(db, user.email.upper()) == "pending_approval"
    assert user.two_factor_required is False
    assert user.failed_login_attempts == 0


async def test_verify_email_keeps_the_status_of_an_active_account(
    db: AsyncSession, make_user: UserFactory
) -> None:
    admin = await make_user(UserRole.ADMIN)
    admin.two_factor_required = True

    assert await mark_email_verified(db, admin.email) == "active"
    assert admin.two_factor_required is False


async def test_verify_email_rejects_an_unknown_address(db: AsyncSession) -> None:
    with pytest.raises(LookupError):
        await mark_email_verified(db, "nadie@unipamplona.edu.co")


async def test_forget_unverified_deletes_only_pending_email_accounts(
    db: AsyncSession, make_user: UserFactory
) -> None:
    pending = await make_user(UserRole.PASSENGER, UserStatus.PENDING_EMAIL)
    active = await make_user(UserRole.PASSENGER)

    await forget_unverified(db, pending.email)
    assert await db.scalar(select(User).where(User.email == pending.email)) is None

    with pytest.raises(PermissionError):
        await forget_unverified(db, active.email)
    assert await db.scalar(select(User).where(User.email == active.email)) is not None
