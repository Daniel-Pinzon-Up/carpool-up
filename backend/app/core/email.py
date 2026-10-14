"""Correo transaccional: verificacion, segundo factor y recuperacion de contrasena.

Los textos llevan tildes porque los leen los usuarios; los comentarios del codigo no.

La API solo encola el mensaje; el worker ARQ lo envia por SMTP: Mailpit en desarrollo o un
servidor real (Gmail, Brevo, Resend, el de la universidad) cuando se configura SMTP_*.
"""

from dataclasses import asdict, dataclass
from email.message import EmailMessage as MimeMessage
from html import escape
from typing import Protocol

import aiosmtplib
from arq import ArqRedis

from app.core.config import get_settings
from app.core.enums import AuthPurpose


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


class EmailQueue(Protocol):
    async def enqueue(self, email: OutgoingEmail) -> None: ...


class ArqEmailQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self.pool = pool

    async def enqueue(self, email: OutgoingEmail) -> None:
        await self.pool.enqueue_job("send_email", asdict(email))


# Fallos pasajeros del servidor de correo: el worker reintenta. Un destinatario o remitente
# rechazado, o credenciales malas, no se arreglan reintentando.
TRANSIENT_SMTP_ERRORS: tuple[type[Exception], ...] = (
    aiosmtplib.SMTPConnectError,
    aiosmtplib.SMTPServerDisconnected,
    aiosmtplib.SMTPTimeoutError,
    TimeoutError,
    OSError,
)


async def send_smtp(email: OutgoingEmail) -> None:
    """Envia por SMTP. El puerto decide el cifrado: 465 TLS directo, 587 STARTTLS, otro sin TLS."""
    settings = get_settings()
    message = MimeMessage()
    message["From"] = settings.smtp_from
    message["To"] = email.to
    message["Subject"] = email.subject
    message.set_content(email.text)
    message.add_alternative(email.html, subtype="html")
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_port == 465,
        start_tls=settings.smtp_port == 587,
        timeout=20,
    )


# --- Plantilla ---------------------------------------------------------------------------

GREETING = "Hola, {name}:"
CODE_INTRO = "Tu código es:"
EXPIRES = "Vence en {minutes} minutos y solo sirve una vez."
IGNORE = "Si no fuiste tú, ignora este mensaje. Nadie de la universidad te pedirá este código."
SIGNATURE = "Carpool Universitario - Universidad de Pamplona"
PURPOSES: dict[AuthPurpose, tuple[str, str]] = {
    AuthPurpose.EMAIL_VERIFICATION: (
        "Verifica tu correo",
        "Usa este código para confirmar tu correo institucional y terminar tu registro.",
    ),
    AuthPurpose.TWO_FACTOR: (
        "Código para iniciar sesión",
        "Recibimos un inicio de sesión con tu contraseña. Confírmalo con este código.",
    ),
    AuthPurpose.PASSWORD_RESET: (
        "Restablece tu contraseña",
        "Usa este código para crear una contraseña nueva. Se cerrarán todas tus sesiones.",
    ),
}


def code_email(to: str, name: str, purpose: AuthPurpose, code: str, minutes: int) -> OutgoingEmail:
    """Correo con el código de 6 números (verificación, segundo factor o recuperación)."""
    subject, intro = PURPOSES[purpose]
    greeting = GREETING.format(name=name)
    expires = EXPIRES.format(minutes=minutes)
    text = "\n\n".join([greeting, intro, f"{CODE_INTRO} {code}", expires, IGNORE, SIGNATURE])
    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:auto;'
        'color:#0A1F44">'
        f"<p>{escape(greeting)}</p><p>{escape(intro)}</p>"
        f"<p>{escape(CODE_INTRO)}</p>"
        '<p style="font-size:32px;font-weight:700;letter-spacing:8px;background:#EAF3FF;'
        f'border-radius:12px;padding:16px;text-align:center">{escape(code)}</p>'
        f"<p>{escape(expires)}</p>"
        f'<p style="color:#3B5378;font-size:13px">{escape(IGNORE)}</p>'
        f'<p style="color:#3B5378;font-size:13px">{escape(SIGNATURE)}</p></div>'
    )
    return OutgoingEmail(to=to, subject=subject, text=text, html=html)
