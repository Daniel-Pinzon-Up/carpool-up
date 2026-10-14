"""Cola de aprobacion, visor seguro de archivos, licencias, revalidacion y cuentas."""

import itertools
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.config import get_settings
from app.core.enums import DocKind, ReviewStatus, Sex, UserRole, UserStatus
from app.modules.audit.models import AuditLog
from app.modules.documents.models import Document
from app.modules.documents.revalidation import run_revalidation
from app.modules.notifications.models import Notification
from app.modules.semesters.models import Semester
from app.modules.users.models import User
from tests.conftest import API, UserFactory, auth

pytestmark = pytest.mark.integration

_SEQUENCE = itertools.count(1)

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"


def write_file(name: str, content: bytes = PDF) -> str:
    relative = f"identity/{name}"
    target = Path(get_settings().storage_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return relative


async def add_document(
    db: AsyncSession,
    user: User,
    status: ReviewStatus = ReviewStatus.PENDING,
    semester: Semester | None = None,
) -> Document:
    # Hora explicita: dentro de la transaccion de prueba now() es igual para todas las filas.
    submitted = datetime(2030, 1, 1, tzinfo=UTC) + timedelta(seconds=next(_SEQUENCE))
    document = Document(
        created_at=submitted,
        updated_at=submitted,
        user_id=user.id,
        kind=DocKind.STUDENT_CARD,
        file_path=write_file(f"{uuid.uuid4().hex}.pdf"),
        content_type="application/pdf",
        status=status,
        semester_id=semester.id if semester else None,
    )
    db.add(document)
    await db.flush()
    return document


async def add_semester(
    db: AsyncSession, name: str, start: date, end: date, deadline: date
) -> Semester:
    semester = Semester(name=name, starts_on=start, ends_on=end, revalidation_deadline=deadline)
    db.add(semester)
    await db.flush()
    return semester


async def current_semester(db: AsyncSession) -> Semester:
    today = local_today()
    return await add_semester(
        db,
        "Actual",
        today - timedelta(days=40),
        today + timedelta(days=80),
        today - timedelta(days=10),
    )


async def notifications_of(db: AsyncSession, user: User) -> list[str]:
    rows = await db.scalars(select(Notification.kind).where(Notification.user_id == user.id))
    return list(rows.all())


@pytest.fixture
async def admin(make_user: UserFactory) -> User:
    return await make_user(UserRole.ADMIN)


# --- Cola ------------------------------------------------------------------------------------


async def test_queue_is_fifo_and_hides_contact_data(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory, admin: User
) -> None:
    first = await make_user(status=UserStatus.PENDING_APPROVAL)
    second = await make_user(status=UserStatus.PENDING_APPROVAL, sex=Sex.MALE)
    doc1 = await add_document(db, first)
    doc2 = await add_document(db, second)

    page = (await api.get(f"{API}/admin/approvals", headers=auth(admin))).json()
    assert [item["id"] for item in page["items"]] == [str(doc1.id), str(doc2.id)]
    applicant = page["items"][1]["applicant"]
    assert applicant["sex"] == "male" and applicant["full_name"] == second.full_name
    assert "email" not in applicant

    counts = (await api.get(f"{API}/admin/approvals/counts", headers=auth(admin))).json()
    assert counts == {"identity": 2, "license": 0}


async def test_only_admins_reach_the_queue(api: AsyncClient, make_user: UserFactory) -> None:
    for role in (UserRole.PASSENGER, UserRole.DRIVER):
        response = await api.get(f"{API}/admin/approvals", headers=auth(await make_user(role)))
        assert response.status_code == 403


# --- Aprobar y rechazar ----------------------------------------------------------------------


async def test_approval_activates_account_and_can_fix_sex(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory, admin: User
) -> None:
    await current_semester(db)
    user = await make_user(status=UserStatus.PENDING_APPROVAL, sex=Sex.MALE)
    document = await add_document(db, user)

    response = await api.post(
        f"{API}/admin/approvals/{document.id}/approve", json={"sex": "female"}, headers=auth(admin)
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert response.json()["semester"] == "Actual"

    await db.refresh(user)
    await db.refresh(document)
    assert user.status == UserStatus.ACTIVE
    assert user.sex == Sex.FEMALE

    assert document.reviewed_by == admin.id
    assert await notifications_of(db, user) == ["document_approved"]

    audit = await db.scalar(select(AuditLog).where(AuditLog.entity_id == str(document.id)))
    assert audit is not None and audit.action == "identity_document.approve"
    assert audit.before["user_sex"] == "male" and audit.after["user_sex"] == "female"

    again = await api.post(
        f"{API}/admin/approvals/{document.id}/approve", json={}, headers=auth(admin)
    )
    assert again.status_code == 409
    assert again.json()["code"] == "APPROVAL_NOT_PENDING"


async def test_rejection_needs_reason_and_user_can_try_again(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory, admin: User
) -> None:
    user = await make_user(status=UserStatus.PENDING_APPROVAL)
    document = await add_document(db, user)

    short = await api.post(
        f"{API}/admin/approvals/{document.id}/reject", json={"reason": "no"}, headers=auth(admin)
    )
    assert short.status_code == 422

    response = await api.post(
        f"{API}/admin/approvals/{document.id}/reject",
        json={"reason": "La foto esta borrosa"},
        headers=auth(admin),
    )
    assert response.json()["status"] == "rejected"
    await db.refresh(user)
    assert user.status == UserStatus.PENDING_APPROVAL

    me = (await api.get(f"{API}/users/me", headers=auth(user))).json()
    assert me["document"]["status"] == "rejected"
    assert me["document"]["rejection_reason"] == "La foto esta borrosa"
    notice = await db.scalar(select(Notification).where(Notification.user_id == user.id))
    assert notice is not None and notice.payload == {"reason": "La foto esta borrosa"}

    retry = await api.post(
        f"{API}/users/me/documents",
        data={"kind": "student_card"},
        files={"document": ("carnet.pdf", PDF, "application/pdf")},
        headers=auth(user),
    )
    assert retry.status_code == 201
    queue = (await api.get(f"{API}/admin/approvals", headers=auth(admin))).json()
    assert [item["id"] for item in queue["items"]] == [retry.json()["id"]]


async def test_reviewers_cannot_review_themselves(
    api: AsyncClient, db: AsyncSession, admin: User
) -> None:
    document = await add_document(db, admin)
    response = await api.post(
        f"{API}/admin/approvals/{document.id}/approve", json={}, headers=auth(admin)
    )
    assert response.status_code == 403


# --- Archivos --------------------------------------------------------------------------------


async def test_files_are_private_and_not_cached(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory, admin: User
) -> None:
    owner = await make_user(status=UserStatus.PENDING_APPROVAL)
    stranger = await make_user()
    document = await add_document(db, owner)

    as_admin = await api.get(f"{API}/admin/files/{document.id}", headers=auth(admin))
    assert as_admin.status_code == 200
    assert as_admin.content == PDF
    assert as_admin.headers["content-type"] == "application/pdf"
    assert "no-store" in as_admin.headers["cache-control"]
    assert as_admin.headers["x-content-type-options"] == "nosniff"

    assert (
        await api.get(f"{API}/admin/files/{document.id}", headers=auth(stranger))
    ).status_code == 403
    assert (await api.get(f"{API}/admin/files/{document.id}")).status_code == 401

    own = await api.get(f"{API}/users/me/documents/{document.id}/file", headers=auth(owner))
    assert own.status_code == 200 and own.content == PDF
    foreign = await api.get(f"{API}/users/me/documents/{document.id}/file", headers=auth(stranger))
    assert foreign.status_code == 404


# --- Licencias -------------------------------------------------------------------------------


async def upload_license(api: AsyncClient, user: User, expires_on: date) -> dict[str, object]:
    response = await api.put(
        f"{API}/users/me/license",
        data={"expires_on": expires_on.isoformat()},
        files={"document": ("licencia.pdf", PDF, "application/pdf")},
        headers=auth(user),
    )
    return {"status_code": response.status_code, **response.json()}


async def test_driver_license_flow(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory, admin: User
) -> None:
    driver = await make_user(UserRole.DRIVER)
    me = (await api.get(f"{API}/users/me", headers=auth(driver))).json()
    assert me["license"] is None and me["can_publish"] is False

    future = local_today() + timedelta(days=365)
    uploaded = await upload_license(api, driver, future)
    assert uploaded["status_code"] == 200 and uploaded["status"] == "pending"

    queue = (
        await api.get(f"{API}/admin/approvals", params={"type": "license"}, headers=auth(admin))
    ).json()
    assert queue["items"][0]["license_expires_on"] == future.isoformat()
    license_id = queue["items"][0]["id"]

    approved = await api.post(
        f"{API}/admin/approvals/{license_id}/approve", json={}, headers=auth(admin)
    )
    assert approved.json()["status"] == "approved"
    me = (await api.get(f"{API}/users/me", headers=auth(driver))).json()
    assert me["license"]["status"] == "approved"
    assert me["publish_blockers"] == ["no_active_vehicle"]  # el paso 4 exige un vehiculo

    replaced = await upload_license(api, driver, future + timedelta(days=30))
    assert replaced["status"] == "pending" and replaced["id"] != license_id
    assert (await api.get(f"{API}/users/me", headers=auth(driver))).json()["can_publish"] is False


async def test_license_rules(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory, admin: User
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    response = await upload_license(api, passenger, local_today() + timedelta(days=30))
    assert response["status_code"] == 403 and response["code"] == "LICENSE_DRIVERS_ONLY"

    driver = await make_user(UserRole.DRIVER)
    expired = await upload_license(api, driver, local_today())
    assert expired["status_code"] == 422 and expired["code"] == "LICENSE_EXPIRED"

    await upload_license(api, driver, local_today() + timedelta(days=10))
    license_ = await db.scalar(
        select(Document).where(
            Document.user_id == driver.id, Document.kind == DocKind.DRIVER_LICENSE
        )
    )
    assert license_ is not None
    license_.expires_on = local_today() - timedelta(days=1)  # vencio mientras esperaba revision
    await db.flush()
    late = await api.post(
        f"{API}/admin/approvals/{license_.id}/approve", json={}, headers=auth(admin)
    )
    assert late.status_code == 422 and late.json()["code"] == "LICENSE_EXPIRED"


# --- Revalidacion semestral ------------------------------------------------------------------


async def test_semester_revalidation(db: AsyncSession, make_user: UserFactory) -> None:
    today = local_today()
    previous = await add_semester(
        db,
        "Anterior",
        today - timedelta(days=200),
        today - timedelta(days=60),
        today - timedelta(days=170),
    )
    current = await add_semester(
        db,
        "Vigente",
        today - timedelta(days=40),
        today + timedelta(days=80),
        today + timedelta(days=5),
    )
    stale = await make_user()
    stale_doc = await add_document(db, stale, ReviewStatus.APPROVED, previous)
    renewed = await make_user()
    await add_document(db, renewed, ReviewStatus.APPROVED, current)
    admin = await make_user(UserRole.ADMIN)

    before_deadline = await run_revalidation(db, today)
    assert (before_deadline.expired_documents, before_deadline.downgraded_users) == (1, 0)
    await db.refresh(stale_doc)
    await db.refresh(stale)
    assert stale_doc.status == ReviewStatus.EXPIRED
    assert stale.status == UserStatus.ACTIVE  # sigue activo hasta el plazo
    assert await notifications_of(db, stale) == ["document_expired"]

    after_deadline = await run_revalidation(db, current.revalidation_deadline + timedelta(days=1))
    assert (after_deadline.expired_documents, after_deadline.downgraded_users) == (0, 1)
    for user, expected in (
        (stale, UserStatus.PENDING_APPROVAL),
        (renewed, UserStatus.ACTIVE),
        (admin, UserStatus.ACTIVE),
    ):
        await db.refresh(user)
        assert user.status == expected

    again = await run_revalidation(db, current.revalidation_deadline + timedelta(days=1))
    assert (again.expired_documents, again.downgraded_users) == (0, 0)


async def test_revalidation_without_current_semester_does_nothing(
    db: AsyncSession, make_user: UserFactory
) -> None:
    user = await make_user()
    document = await add_document(db, user, ReviewStatus.APPROVED)
    result = await run_revalidation(db, date(1999, 1, 1))
    assert (result.expired_documents, result.downgraded_users) == (0, 0)
    await db.refresh(document)
    assert document.status == ReviewStatus.APPROVED


# --- Administradores y roles -----------------------------------------------------------------


async def test_superadmin_creates_admins(
    api: AsyncClient, su_headers: dict[str, str], admin: User
) -> None:
    body = {
        "email": "nuevo.admin@unipamplona.edu.co",
        "full_name": "Ana Admin",
        "sex": "female",
        "password": "clave-inicial-123",
    }
    created = await api.post(f"{API}/admin/admins", json=body, headers=su_headers)
    assert created.status_code == 201
    assert created.json()["role"] == "admin" and created.json()["status"] == "active"

    duplicate = await api.post(f"{API}/admin/admins", json=body, headers=su_headers)
    assert duplicate.json()["code"] == "EMAIL_TAKEN"
    outside = await api.post(
        f"{API}/admin/admins", json={**body, "email": "x@gmail.com"}, headers=su_headers
    )
    assert outside.json()["code"] == "EMAIL_NOT_INSTITUTIONAL"
    by_admin = await api.post(
        f"{API}/admin/admins",
        json={**body, "email": "otro@unipamplona.edu.co"},
        headers=auth(admin),
    )
    assert by_admin.status_code == 403

    login = await api.post(
        f"{API}/auth/login", json={"email": body["email"], "password": body["password"]}
    )
    assert login.json()["result"] == "two_factor_required"


async def test_role_changes_are_restricted_and_audited(
    api: AsyncClient,
    db: AsyncSession,
    make_user: UserFactory,
    superadmin: User,
    su_headers: dict[str, str],
    admin: User,
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    changed = await api.patch(
        f"{API}/admin/users/{passenger.id}/role", json={"role": "driver"}, headers=su_headers
    )
    assert changed.json()["role"] == "driver"
    assert await notifications_of(db, passenger) == ["role_changed"]
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "user.role_change"))
    assert (
        audit is not None
        and audit.before == {"role": "passenger"}
        and audit.after == {"role": "driver"}
    )

    own = await api.patch(
        f"{API}/admin/users/{superadmin.id}/role", json={"role": "admin"}, headers=su_headers
    )
    assert own.status_code == 403
    promote = await api.patch(
        f"{API}/admin/users/{passenger.id}/role", json={"role": "superadmin"}, headers=su_headers
    )
    assert promote.status_code == 422
    by_admin = await api.patch(
        f"{API}/admin/users/{passenger.id}/role", json={"role": "passenger"}, headers=auth(admin)
    )
    assert by_admin.status_code == 403


# --- Notificaciones --------------------------------------------------------------------------


async def test_notification_inbox(
    api: AsyncClient, db: AsyncSession, make_user: UserFactory
) -> None:
    owner = await make_user()
    other = await make_user()
    for kind in ("document_approved", "role_changed"):
        db.add(Notification(user_id=owner.id, kind=kind, payload={}))
    await db.flush()

    inbox = (await api.get(f"{API}/notifications", headers=auth(owner))).json()
    assert [item["kind"] for item in inbox["items"]] == ["role_changed", "document_approved"]
    assert (await api.get(f"{API}/notifications/unread-count", headers=auth(owner))).json() == {
        "unread": 2
    }

    first_id = inbox["items"][0]["id"]
    assert (
        await api.post(f"{API}/notifications/{first_id}/read", headers=auth(other))
    ).status_code == 404
    assert (
        await api.post(f"{API}/notifications/{first_id}/read", headers=auth(owner))
    ).status_code == 204
    unread = (
        await api.get(f"{API}/notifications", params={"unread_only": True}, headers=auth(owner))
    ).json()
    assert len(unread["items"]) == 1
    assert (await api.post(f"{API}/notifications/read-all", headers=auth(owner))).json() == {
        "marked": 1
    }
    assert (await api.get(f"{API}/notifications/unread-count", headers=auth(owner))).json() == {
        "unread": 0
    }
