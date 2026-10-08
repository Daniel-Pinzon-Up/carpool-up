"""Envio real de correo: cifrado segun el puerto y reintentos del worker."""

from typing import Any

import aiosmtplib
import pytest
from arq.worker import Retry

from app.core import email as email_module
from app.core.config import get_settings
from app.core.email import OutgoingEmail, send_smtp
from app.workers import main as worker

MESSAGE = OutgoingEmail(
    to="ana@unipamplona.edu.co", subject="Asunto", text="Hola", html="<p>Hola</p>"
)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def fake_send(message: Any, **kwargs: Any) -> None:
        calls.append({"message": message, **kwargs})

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)
    return calls


@pytest.mark.parametrize(
    ("port", "use_tls", "start_tls"),
    [(465, True, False), (587, False, True), (1025, False, False)],
)
async def test_port_selects_the_encryption(
    monkeypatch: pytest.MonkeyPatch,
    sent: list[dict[str, Any]],
    port: int,
    use_tls: bool,
    start_tls: bool,
) -> None:
    monkeypatch.setattr(get_settings(), "smtp_port", port)
    await send_smtp(MESSAGE)
    assert sent[0]["use_tls"] is use_tls
    assert sent[0]["start_tls"] is start_tls
    assert sent[0]["message"]["To"] == MESSAGE.to


async def test_worker_retries_when_the_server_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def down(email: OutgoingEmail) -> None:
        raise aiosmtplib.SMTPConnectError("sin conexion")

    monkeypatch.setattr(worker, "send_smtp", down)
    with pytest.raises(Retry) as retry:
        await worker.send_email({"job_try": 2}, vars(MESSAGE))
    assert retry.value.defer_score == 60_000


async def test_worker_does_not_retry_a_rejected_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refused(email: OutgoingEmail) -> None:
        raise aiosmtplib.SMTPRecipientsRefused([])

    monkeypatch.setattr(worker, "send_smtp", refused)
    with pytest.raises(aiosmtplib.SMTPRecipientsRefused):
        await worker.send_email({"job_try": 1}, vars(MESSAGE))
