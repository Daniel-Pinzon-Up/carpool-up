"""Registro, verificacion de correo, login con 2FA condicional, sesiones y recuperacion."""

import io
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.enums import AuthPurpose, UserRole, UserStatus
from app.core.security import create_challenge_token
from app.modules.auth import codes as codes_module
from app.modules.documents.models import IdentityDocument
from app.modules.legal.models import LegalDocument, TermsAcceptance
from app.modules.users.models import User
from tests.conftest import API, Outbox, UserFactory, auth

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("legal_docs")]

EMAIL = "laura.prueba@unipamplona.edu.co"
PASSWORD = "clave-segura-123"


def jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), "navy").save(out, format="JPEG")
    return out.getvalue()


def form(**overrides: Any) -> dict[str, Any]:
    base = {
        "email": EMAIL,
        "password": PASSWORD,
        "full_name": "Laura Prueba",
        "sex": "female",
        "program": "Ingenieria de Sistemas",
        "role": "passenger",
        "doc_kind": "identity_document",
        "preferred_language": "es",
        "accept_terms": "true",
        "accept_data_policy": "true",
    }
    base.update(overrides)
    return base


async def register(
    api: AsyncClient, file: tuple[str, bytes, str] | None = None, **overrides: Any
) -> Response:
    document = file or ("carnet.jpg", jpeg(), "image/jpeg")
    return await api.post(
        f"{API}/auth/register", data=form(**overrides), files={"document": document}
    )


async def register_and_verify(api: AsyncClient, outbox: Outbox) -> dict[str, Any]:
    challenge = (await register(api)).json()["challenge_id"]
    response = await api.post(
        f"{API}/auth/verify-email",
        json={"challenge_id": challenge, "code": outbox.last_code(EMAIL)},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


async def activate(db: AsyncSession, email: str = EMAIL) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.status = UserStatus.ACTIVE
    await db.flush()
    return user


# --- Registro ---------------------------------------------------------------------------------


async def test_register_creates_pending_account_document_and_acceptances(
    api: AsyncClient, db: AsyncSession, outbox: Outbox, legal_docs: list[LegalDocument]
) -> None:
    response = await register(api, email="Laura.Prueba@UniPamplona.edu.co")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["result"] == "email_verification_required"
    assert body["email_hint"] == "la**********@unipamplona.edu.co"
    assert body["challenge_id"]
    assert body["access_token"] is None

    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    assert user.status == UserStatus.PENDING_EMAIL
    assert user.two_factor_required is True
    assert user.password_hash.startswith("$argon2id$")

    document = await db.scalar(select(IdentityDocument).where(IdentityDocument.user_id == user.id))
    assert document is not None and document.status == "pending"
    assert document.kind == "identity_document"
    accepted = await db.scalars(
        select(TermsAcceptance.legal_document_id).where(TermsAcceptance.user_id == user.id)
    )
    assert set(accepted.all()) == {doc.id for doc in legal_docs}

    assert len(outbox.sent) == 1
    assert outbox.sent[0].subject == "Verifica tu correo"
    assert len(outbox.last_code(EMAIL)) == 6


@pytest.mark.parametrize(
    ("overrides", "status", "code"),
    [
        ({"email": "laura@gmail.com"}, 422, "EMAIL_NOT_INSTITUTIONAL"),
        ({"password": "corta"}, 422, "PASSWORD_TOO_SHORT"),
        ({"password": "laura.prueba"}, 422, "PASSWORD_TOO_WEAK"),
        ({"accept_terms": "false"}, 422, "TERMS_NOT_ACCEPTED"),
        ({"accept_data_policy": "false"}, 422, "TERMS_NOT_ACCEPTED"),
        ({"role": "admin"}, 422, "VALIDATION_ERROR"),
        ({"sex": "otro"}, 422, "VALIDATION_ERROR"),
        ({"email": "no-es-correo"}, 422, "VALIDATION_ERROR"),
    ],
)
async def test_register_validations(
    api: AsyncClient, db: AsyncSession, overrides: dict[str, str], status: int, code: str
) -> None:
    response = await register(api, **overrides)
    assert response.status_code == status, response.text
    assert response.json()["code"] == code
    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_register_rejects_duplicate_email(api: AsyncClient) -> None:
    assert (await register(api)).status_code == 201
    response = await register(api, email=EMAIL.upper())
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN"


async def test_register_rejects_files_by_real_content(api: AsyncClient, db: AsyncSession) -> None:
    disguised = ("carnet.jpg", b"MZ\x90\x00 esto es un ejecutable", "image/jpeg")
    response = await register(api, file=disguised)
    assert response.status_code == 415
    assert response.json()["code"] == "FILE_TYPE_NOT_ALLOWED"
    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_register_rejects_large_files(api: AsyncClient, su_headers: dict[str, str]) -> None:
    await api.patch(f"{API}/admin/settings/max_upload_mb", json={"value": 1}, headers=su_headers)
    big = ("carnet.pdf", b"%PDF-1.7\n" + b"0" * (1024 * 1024 + 10), "application/pdf")
    response = await register(api, file=big)
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


async def test_register_needs_published_terms(api: AsyncClient, db: AsyncSession) -> None:
    for doc in await db.scalars(select(LegalDocument)):
        doc.is_current = False
    await db.flush()
    response = await register(api)
    assert response.status_code == 503
    assert response.json()["code"] == "LEGAL_DOCUMENTS_UNAVAILABLE"


# --- Verificacion de correo -------------------------------------------------------------------


async def test_verify_email_opens_session_and_moves_to_pending_approval(
    api: AsyncClient, db: AsyncSession, outbox: Outbox
) -> None:
    challenge = (await register(api)).json()["challenge_id"]
    wrong = await api.post(
        f"{API}/auth/verify-email", json={"challenge_id": challenge, "code": "000000"}
    )
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "CODE_INVALID"

    response = await api.post(
        f"{API}/auth/verify-email",
        json={"challenge_id": challenge, "code": outbox.last_code(EMAIL)},
    )
    body = response.json()
    assert body["result"] == "authenticated"
    assert body["access_token"]
    assert body["expires_in"] == 15 * 60
    assert body["user"]["status"] == "pending_approval"
    assert body["user"]["email"] == EMAIL
    cookie = response.headers["set-cookie"]
    assert "cp_refresh=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie
    assert "samesite=lax" in cookie.lower()

    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None and user.two_factor_required is False

    reused = await api.post(
        f"{API}/auth/verify-email",
        json={"challenge_id": challenge, "code": outbox.last_code(EMAIL)},
    )
    assert reused.json()["code"] == "CODE_INVALID"


async def test_code_dies_after_max_attempts(api: AsyncClient, outbox: Outbox) -> None:
    challenge = (await register(api)).json()["challenge_id"]
    for _ in range(5):
        await api.post(
            f"{API}/auth/verify-email", json={"challenge_id": challenge, "code": "000000"}
        )
    response = await api.post(
        f"{API}/auth/verify-email",
        json={"challenge_id": challenge, "code": outbox.last_code(EMAIL)},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "CODE_INVALID"


async def test_codes_expire(
    api: AsyncClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    challenge = (await register(api)).json()["challenge_id"]
    later = utcnow() + timedelta(minutes=11)
    monkeypatch.setattr(codes_module, "utcnow", lambda: later)
    response = await api.post(
        f"{API}/auth/verify-email",
        json={"challenge_id": challenge, "code": outbox.last_code(EMAIL)},
    )
    assert response.json()["code"] == "CODE_INVALID"


async def test_tampered_or_wrong_purpose_challenge(api: AsyncClient, db: AsyncSession) -> None:
    await register(api)
    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    wrong_purpose = create_challenge_token(user.id, AuthPurpose.PASSWORD_RESET, 10)
    for challenge in ("basura", wrong_purpose):
        response = await api.post(
            f"{API}/auth/verify-email", json={"challenge_id": challenge, "code": "123456"}
        )
        assert response.status_code == 400
        assert response.json()["code"] == "CHALLENGE_EXPIRED"


async def test_resend_respects_cooldown_and_replaces_code(
    api: AsyncClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    challenge = (await register(api)).json()["challenge_id"]
    first_code = outbox.last_code(EMAIL)
    too_soon = await api.post(f"{API}/auth/codes/resend", json={"challenge_id": challenge})
    assert too_soon.status_code == 429
    assert too_soon.json()["code"] == "CODE_RESEND_TOO_SOON"
    assert too_soon.json()["details"]["retry_after_seconds"] > 0

    later = utcnow() + timedelta(seconds=61)
    monkeypatch.setattr(codes_module, "utcnow", lambda: later)
    resent = await api.post(f"{API}/auth/codes/resend", json={"challenge_id": challenge})
    assert resent.status_code == 200
    assert len(outbox.sent) == 2
    monkeypatch.undo()

    old = await api.post(
        f"{API}/auth/verify-email", json={"challenge_id": challenge, "code": first_code}
    )
    assert old.json()["code"] == "CODE_INVALID"  # el codigo anterior queda invalidado


# --- Login ------------------------------------------------------------------------------------


async def test_login_wrong_password_and_unknown_email_look_the_same(
    api: AsyncClient, outbox: Outbox
) -> None:
    await register_and_verify(api, outbox)
    wrong = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": "equivocada-123"})
    unknown = await api.post(
        f"{API}/auth/login",
        json={"email": "nadie@unipamplona.edu.co", "password": "equivocada-123"},
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["code"] == "INVALID_CREDENTIALS"


async def test_lockout_after_five_failures(api: AsyncClient, outbox: Outbox) -> None:
    await register_and_verify(api, outbox)
    codes = []
    for _ in range(5):
        response = await api.post(
            f"{API}/auth/login", json={"email": EMAIL, "password": "mala-clave-000"}
        )
        codes.append(response.json()["code"])
    assert codes == ["INVALID_CREDENTIALS"] * 4 + ["ACCOUNT_LOCKED"]

    even_correct = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert even_correct.status_code == 429
    assert even_correct.json()["code"] == "ACCOUNT_LOCKED"
    assert even_correct.json()["details"]["retry_after_seconds"] > 0


async def test_unverified_account_gets_email_challenge_on_login(
    api: AsyncClient, outbox: Outbox
) -> None:
    await register(api)
    response = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["result"] == "email_verification_required"
    assert len(outbox.sent) == 1  # dentro de la espera minima no se envia otro correo


async def test_login_without_second_factor_after_first_verification(
    api: AsyncClient, outbox: Outbox
) -> None:
    await register_and_verify(api, outbox)
    response = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.json()["result"] == "authenticated"
    assert response.json()["user"]["status"] == "pending_approval"


async def test_two_factor_when_required(api: AsyncClient, db: AsyncSession, outbox: Outbox) -> None:
    await register_and_verify(api, outbox)
    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    user.two_factor_required = True
    await db.flush()
    outbox.sent.clear()

    challenge = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert challenge.json()["result"] == "two_factor_required"
    assert outbox.sent[-1].subject == "Código para iniciar sesión"
    response = await api.post(
        f"{API}/auth/2fa/verify",
        json={"challenge_id": challenge.json()["challenge_id"], "code": outbox.last_code(EMAIL)},
    )
    assert response.json()["result"] == "authenticated"
    await db.refresh(user)
    assert user.two_factor_required is False


async def test_blocked_accounts_cannot_log_in(
    api: AsyncClient, db: AsyncSession, outbox: Outbox
) -> None:
    await register_and_verify(api, outbox)
    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    user.status = UserStatus.BLOCKED
    await db.flush()
    response = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_BLOCKED"


# --- Sesiones ---------------------------------------------------------------------------------


async def test_refresh_rotates_and_detects_reuse(api: AsyncClient, outbox: Outbox) -> None:
    await register_and_verify(api, outbox)
    first = api.cookies["cp_refresh"]

    rotated = await api.post(f"{API}/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["access_token"]
    second = api.cookies["cp_refresh"]
    assert second != first

    api.cookies.set("cp_refresh", first, path="/api/v1/auth")
    reuse = await api.post(f"{API}/auth/refresh")
    assert reuse.status_code == 401
    assert reuse.json()["code"] == "REFRESH_REUSED"

    api.cookies.set("cp_refresh", second, path="/api/v1/auth")
    after = await api.post(f"{API}/auth/refresh")
    assert after.status_code == 401  # todas las sesiones quedaron revocadas


async def test_refresh_without_cookie(api: AsyncClient) -> None:
    response = await api.post(f"{API}/auth/refresh")
    assert response.status_code == 401
    assert response.json()["code"] == "REFRESH_INVALID"


async def test_logout_revokes_session_and_its_access_token(
    api: AsyncClient, outbox: Outbox
) -> None:
    body = await register_and_verify(api, outbox)
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert (await api.get(f"{API}/users/me", headers=headers)).status_code == 200

    assert (await api.post(f"{API}/auth/logout")).status_code == 204
    assert (await api.get(f"{API}/users/me", headers=headers)).status_code == 401
    assert (await api.post(f"{API}/auth/refresh")).status_code == 401


async def test_sessions_list_and_logout_others(api: AsyncClient, outbox: Outbox) -> None:
    first = await register_and_verify(api, outbox)
    second = (
        await api.post(
            f"{API}/auth/login",
            json={"email": EMAIL, "password": PASSWORD, "device_label": "Celular"},
        )
    ).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    sessions = (await api.get(f"{API}/auth/sessions", headers=second_headers)).json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    assert len(current) == 1 and current[0]["device_label"] == "Celular"

    revoked = await api.post(f"{API}/auth/logout-others", headers=second_headers)
    assert revoked.json() == {"revoked": 1}
    assert (await api.get(f"{API}/users/me", headers=first_headers)).status_code == 401
    assert (await api.get(f"{API}/users/me", headers=second_headers)).status_code == 200


# --- Recuperacion -----------------------------------------------------------------------------


async def test_forgot_password_does_not_reveal_accounts(api: AsyncClient, outbox: Outbox) -> None:
    await register_and_verify(api, outbox)
    outbox.sent.clear()
    known = await api.post(f"{API}/auth/password/forgot", json={"email": EMAIL})
    unknown = await api.post(
        f"{API}/auth/password/forgot", json={"email": "nadie@unipamplona.edu.co"}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json().keys() == unknown.json().keys()
    assert known.json()["result"] == unknown.json()["result"] == "password_reset_code_sent"
    assert [e.to for e in outbox.sent] == [EMAIL]

    fake = await api.post(
        f"{API}/auth/password/reset",
        json={
            "challenge_id": unknown.json()["challenge_id"],
            "code": "123456",
            "new_password": "x" * 12,
        },
    )
    assert fake.status_code == 400
    assert fake.json()["code"] == "CODE_INVALID"


async def test_reset_password_revokes_sessions_and_requires_second_factor(
    api: AsyncClient, db: AsyncSession, outbox: Outbox
) -> None:
    session_body = await register_and_verify(api, outbox)
    old_headers = {"Authorization": f"Bearer {session_body['access_token']}"}
    challenge = (await api.post(f"{API}/auth/password/forgot", json={"email": EMAIL})).json()[
        "challenge_id"
    ]

    weak = await api.post(
        f"{API}/auth/password/reset",
        json={"challenge_id": challenge, "code": outbox.last_code(EMAIL), "new_password": "corta"},
    )
    assert weak.json()["code"] == "PASSWORD_TOO_SHORT"

    reset = await api.post(
        f"{API}/auth/password/reset",
        json={
            "challenge_id": challenge,
            "code": outbox.last_code(EMAIL),
            "new_password": "nueva-clave-456",
        },
    )
    assert reset.status_code == 204
    assert (await api.get(f"{API}/users/me", headers=old_headers)).status_code == 401

    old_password = await api.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert old_password.json()["code"] == "INVALID_CREDENTIALS"
    new_login = await api.post(
        f"{API}/auth/login", json={"email": EMAIL, "password": "nueva-clave-456"}
    )
    assert new_login.json()["result"] == "two_factor_required"


# --- Perfil, documentos y terminos ------------------------------------------------------------


async def test_pending_accounts_see_their_profile_but_not_features(
    api: AsyncClient, outbox: Outbox
) -> None:
    body = await register_and_verify(api, outbox)
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = (await api.get(f"{API}/users/me", headers=headers)).json()
    assert me["status"] == "pending_approval"
    assert me["document"]["status"] == "pending"
    assert me["pending_legal"] == []
    pin = await api.post(
        f"{API}/places/custom", json={"name": "Casa", "lat": 7.38, "lon": -72.65}, headers=headers
    )
    assert pin.status_code == 403
    assert pin.json()["code"] == "ACCOUNT_NOT_ACTIVE"


async def test_new_document_replaces_pending_one(api: AsyncClient, outbox: Outbox) -> None:
    body = await register_and_verify(api, outbox)
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    pdf = ("constancia.pdf", b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n", "application/pdf")
    response = await api.post(
        f"{API}/users/me/documents",
        data={"kind": "institutional_proof"},
        files={"document": pdf},
        headers=headers,
    )
    assert response.status_code == 201
    history = (await api.get(f"{API}/users/me/documents", headers=headers)).json()
    assert len(history) == 1
    assert history[0]["kind"] == "institutional_proof"


async def test_profile_preferences_and_payment_note(
    api: AsyncClient, make_user: UserFactory
) -> None:
    passenger = await make_user(UserRole.PASSENGER)
    updated = await api.patch(
        f"{API}/users/me",
        json={"preferred_language": "fr", "theme_preference": "dark"},
        headers=auth(passenger),
    )
    assert updated.status_code == 200
    assert (updated.json()["preferred_language"], updated.json()["theme_preference"]) == (
        "fr",
        "dark",
    )

    forbidden = await api.patch(
        f"{API}/users/me", json={"payment_note": "Nequi"}, headers=auth(passenger)
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "PAYMENT_NOTE_DRIVERS_ONLY"

    driver = await make_user(UserRole.DRIVER)
    note = await api.patch(
        f"{API}/users/me", json={"payment_note": "Nequi 300 000 0000"}, headers=auth(driver)
    )
    assert note.json()["payment_note"] == "Nequi 300 000 0000"
    cleared = await api.patch(f"{API}/users/me", json={"payment_note": ""}, headers=auth(driver))
    assert cleared.json()["payment_note"] is None


async def test_new_legal_version_must_be_accepted(
    api: AsyncClient, outbox: Outbox, su_headers: dict[str, str]
) -> None:
    body = await register_and_verify(api, outbox)
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    published = await api.post(
        f"{API}/admin/legal",
        json={
            "kind": "terms",
            "version": "2.0",
            "language": "es",
            "body_markdown": "Nueva version de los terminos con suficiente longitud de texto.",
        },
        headers=su_headers,
    )
    new_id = published.json()["id"]
    pending = (await api.get(f"{API}/users/me", headers=headers)).json()["pending_legal"]
    assert [p["id"] for p in pending] == [new_id]

    stale = await api.post(
        f"{API}/legal/accept",
        json={"document_ids": [pending[0]["id"], "00000000-0000-0000-0000-000000000000"]},
        headers=headers,
    )
    assert stale.status_code == 422
    assert stale.json()["code"] == "LEGAL_VERSION_NOT_CURRENT"

    accepted = await api.post(
        f"{API}/legal/accept", json={"document_ids": [new_id]}, headers=headers
    )
    assert accepted.status_code == 204
    assert (await api.get(f"{API}/users/me", headers=headers)).json()["pending_legal"] == []


async def test_active_user_reaches_features(
    api: AsyncClient, db: AsyncSession, outbox: Outbox
) -> None:
    body = await register_and_verify(api, outbox)
    await activate(db)
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    pin = await api.post(
        f"{API}/places/custom", json={"name": "Casa", "lat": 7.38, "lon": -72.65}, headers=headers
    )
    assert pin.status_code == 201
