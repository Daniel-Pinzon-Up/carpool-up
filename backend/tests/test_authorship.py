"""Autoria: created_by y updated_by se llenan solos con quien hace el cambio."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.db import set_actor
from app.core.enums import SuspensionKind, UserRole
from app.modules.audit.models import AuditLog
from app.modules.documents.models import IdentityDocument
from app.modules.legal.models import LegalDocument
from app.modules.notifications.models import Notification
from app.modules.semesters.models import Semester
from app.modules.settings.models import SystemSetting
from app.modules.suspensions.models import Suspension
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import API, UserFactory, auth
from tests.test_auth import EMAIL, register
from tests.test_vehicles import CAR

pytestmark = pytest.mark.integration


async def test_creator_and_editor_are_the_signed_in_user(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    driver = await make_user(UserRole.DRIVER)
    response = await api.post(f"{API}/vehicles", json=CAR, headers=auth(driver))
    assert response.status_code == 201, response.text
    vehicle = await db.get(Vehicle, response.json()["id"])
    assert vehicle is not None
    assert vehicle.created_by == driver.id
    assert vehicle.updated_by == driver.id


async def test_editing_keeps_the_creator_and_records_the_last_editor(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    first = await make_user(UserRole.SUPERADMIN)
    second = await make_user(UserRole.SUPERADMIN)
    url = f"{API}/admin/settings/cancel_free_hours"
    assert (await api.patch(url, json={"value": 3}, headers=auth(first))).status_code == 200
    assert (await api.patch(url, json={"value": 4}, headers=auth(second))).status_code == 200

    setting = await db.get(SystemSetting, "cancel_free_hours")
    assert setting is not None
    await db.refresh(setting)
    assert setting.created_by == first.id
    assert setting.updated_by == second.id

    entries = (
        await db.scalars(select(AuditLog).where(AuditLog.entity_id == "cancel_free_hours"))
    ).all()
    assert {entry.actor_id for entry in entries} == {first.id, second.id}


async def test_bulk_updates_record_the_editor(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    user = await make_user()
    db.add_all([Notification(user_id=user.id, kind="trip_reminder") for _ in range(2)])
    await db.flush()

    response = await api.post(f"{API}/notifications/read-all", headers=auth(user))
    assert response.json() == {"marked": 2}
    rows = (await db.scalars(select(Notification).where(Notification.user_id == user.id))).all()
    for row in rows:
        await db.refresh(row)
        assert row.created_by is None  # lo creo el sistema
        assert row.updated_by == user.id


async def test_self_registration_has_no_creator_but_its_document_does(
    api: AsyncClient, db: AsyncSession, legal_docs: list[LegalDocument]
) -> None:
    assert (await register(api)).status_code == 201
    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None and user.created_by is None
    document = await db.scalar(select(IdentityDocument).where(IdentityDocument.user_id == user.id))
    assert document is not None and document.created_by == user.id


async def test_system_changes_have_no_author(db: AsyncSession) -> None:
    semester = Semester(
        name="2027-1",
        starts_on=date(2027, 2, 1),
        ends_on=date(2027, 6, 30),
        revalidation_deadline=date(2027, 3, 3),
    )
    db.add(semester)
    await db.flush()
    assert semester.created_by is None and semester.updated_by is None


async def test_automatic_suspensions_keep_an_empty_creator(
    db: AsyncSession, make_user: UserFactory
) -> None:
    """La sancion por ausencias la causa el conductor al marcar el no-show, pero es automatica:
    created_by nulo es lo que la distingue de una impuesta por un administrador."""
    driver = await make_user(UserRole.DRIVER)
    passenger = await make_user()
    set_actor(db, driver.id)
    try:
        ban = Suspension(
            user_id=passenger.id,
            kind=SuspensionKind.BOOKING_BAN,
            reason="3 ausencias",
            starts_at=utcnow(),
            ends_at=utcnow() + timedelta(days=7),
        )
        db.add(ban)
        await db.flush()
    finally:
        set_actor(db, None)
    assert ban.created_by is None
    assert ban.updated_by == driver.id
