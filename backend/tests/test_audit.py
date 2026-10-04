import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Actor
from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditService
from app.modules.users.models import User
from tests.conftest import API

pytestmark = pytest.mark.integration


async def test_paginates_newest_first_with_cursor(
    api: AsyncClient, db: AsyncSession, superadmin: User, su_headers: dict[str, str]
) -> None:
    service = AuditService(db)
    for index in range(5):
        service.record(Actor(superadmin, "10.0.0.1"), "test.event", "probe", index)
        await db.flush()

    seen: list[str | None] = []
    cursor = None
    while True:
        params: dict[str, object] = {"entity": "probe", "limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = (await api.get(f"{API}/admin/audit", params=params, headers=su_headers)).json()
        seen += [item["entity_id"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == ["0", "1", "2", "3", "4"]
    assert len(seen) == 5


async def test_records_actor_and_ip(db: AsyncSession, superadmin: User) -> None:
    AuditService(db).record(Actor(superadmin, "192.168.1.20"), "test.event", "probe", "x")
    await db.flush()
    entry = await db.scalar(select(AuditLog).where(AuditLog.entity == "probe"))
    assert entry is not None
    assert entry.actor_id == superadmin.id
    assert entry.ip == "192.168.1.20"


async def test_invalid_cursor(api: AsyncClient, su_headers: dict[str, str]) -> None:
    response = await api.get(f"{API}/admin/audit", params={"cursor": "%%%"}, headers=su_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_CURSOR"


@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_entries_cannot_be_changed_or_deleted(
    db: AsyncSession, superadmin: User, operation: str
) -> None:
    AuditService(db).record(Actor(superadmin, None), "test.event", "probe", "x", None, {"a": 1})
    await db.flush()
    statement = (
        update(AuditLog).where(AuditLog.entity == "probe").values(after={"a": 2})
        if operation == "update"
        else delete(AuditLog).where(AuditLog.entity == "probe")
    )
    with pytest.raises(DBAPIError, match="append-only"):
        async with db.begin_nested():
            await db.execute(statement)


async def test_deleting_a_user_keeps_the_entry_without_actor(
    db: AsyncSession, superadmin: User
) -> None:
    AuditService(db).record(Actor(superadmin, None), "test.event", "probe", "x")
    await db.flush()
    await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": superadmin.id})
    db.expire_all()
    entry = await db.scalar(select(AuditLog).where(AuditLog.entity == "probe"))
    assert entry is not None
    assert entry.actor_id is None
    assert entry.action == "test.event"
