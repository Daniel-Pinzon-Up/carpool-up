"""Correo transaccional: verificacion, segundo factor y recuperacion de contrasena.

Los textos llevan tildes porque los leen los usuarios; los comentarios del codigo no.

La API solo encola el mensaje; el worker ARQ lo envia por SMTP (Mailpit en desarrollo).
"""

from dataclasses import asdict, dataclass
from email.message import EmailMessage as MimeMessage
from html import escape
from typing import Any, Protocol

import aiosmtplib
from arq import ArqRedis

from app.core.config import get_settings
from app.core.enums import AuthPurpose, Language


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


async def send_smtp(email: OutgoingEmail) -> None:
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
        start_tls=settings.smtp_port == 587,
        timeout=20,
    )


# --- Plantillas ----------------------------------------------------------------------------

_TEXTS: dict[Language, dict[str, Any]] = {
    Language.ES: {
        "greeting": "Hola, {name}:",
        "code_intro": "Tu código es:",
        "expires": "Vence en {minutes} minutos y solo sirve una vez.",
        "ignore": "Si no fuiste tú, ignora este mensaje. Nadie de la universidad te pedirá este código.",
        "signature": "Carpool Universitario - Universidad de Pamplona",
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
    },
    Language.EN: {
        "greeting": "Hi {name},",
        "code_intro": "Your code is:",
        "expires": "It expires in {minutes} minutes and can be used only once.",
        "ignore": "If this was not you, ignore this message. The university will never ask for this code.",
        "signature": "University Carpool - Universidad de Pamplona",
        AuthPurpose.EMAIL_VERIFICATION: (
            "Verify your email",
            "Use this code to confirm your university email and finish signing up.",
        ),
        AuthPurpose.TWO_FACTOR: (
            "Sign-in code",
            "We received a sign-in with your password. Confirm it with this code.",
        ),
        AuthPurpose.PASSWORD_RESET: (
            "Reset your password",
            "Use this code to create a new password. All your sessions will be closed.",
        ),
    },
    Language.PT: {
        "greeting": "Olá, {name}:",
        "code_intro": "Seu código é:",
        "expires": "Ele vence em {minutes} minutos e só pode ser usado uma vez.",
        "ignore": "Se não foi você, ignore esta mensagem. A universidade nunca pedirá este código.",
        "signature": "Carona Universitária - Universidad de Pamplona",
        AuthPurpose.EMAIL_VERIFICATION: (
            "Verifique seu e-mail",
            "Use este código para confirmar seu e-mail institucional e concluir o cadastro.",
        ),
        AuthPurpose.TWO_FACTOR: (
            "Código para entrar",
            "Recebemos um acesso com sua senha. Confirme-o com este código.",
        ),
        AuthPurpose.PASSWORD_RESET: (
            "Redefina sua senha",
            "Use este código para criar uma nova senha. Todas as suas sessões serão encerradas.",
        ),
    },
    Language.FR: {
        "greeting": "Bonjour {name},",
        "code_intro": "Votre code est :",
        "expires": "Il expire dans {minutes} minutes et ne sert qu'une fois.",
        "ignore": "Si ce n'était pas vous, ignorez ce message. L'université ne vous demandera jamais ce code.",
        "signature": "Covoiturage Universitaire - Universidad de Pamplona",
        AuthPurpose.EMAIL_VERIFICATION: (
            "Vérifiez votre e-mail",
            "Utilisez ce code pour confirmer votre e-mail universitaire et terminer l'inscription.",
        ),
        AuthPurpose.TWO_FACTOR: (
            "Code de connexion",
            "Nous avons reçu une connexion avec votre mot de passe. Confirmez-la avec ce code.",
        ),
        AuthPurpose.PASSWORD_RESET: (
            "Réinitialisez votre mot de passe",
            "Utilisez ce code pour créer un nouveau mot de passe. Toutes vos sessions seront fermées.",
        ),
    },
}


def code_email(
    to: str, name: str, purpose: AuthPurpose, code: str, minutes: int, language: Language
) -> OutgoingEmail:
    texts = _TEXTS.get(language, _TEXTS[Language.ES])
    subject, intro = texts[purpose]
    greeting = texts["greeting"].format(name=name)
    expires = texts["expires"].format(minutes=minutes)
    text = "\n\n".join(
        [
            greeting,
            intro,
            f"{texts['code_intro']} {code}",
            expires,
            texts["ignore"],
            texts["signature"],
        ]
    )
    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:auto;'
        'color:#0A1F44">'
        f"<p>{escape(greeting)}</p><p>{escape(intro)}</p>"
        f"<p>{escape(texts['code_intro'])}</p>"
        '<p style="font-size:32px;font-weight:700;letter-spacing:8px;background:#EAF3FF;'
        f'border-radius:12px;padding:16px;text-align:center">{escape(code)}</p>'
        f"<p>{escape(expires)}</p>"
        f'<p style="color:#3B5378;font-size:13px">{escape(texts["ignore"])}</p>'
        f'<p style="color:#3B5378;font-size:13px">{escape(texts["signature"])}</p></div>'
    )
    return OutgoingEmail(to=to, subject=subject, text=text, html=html)
