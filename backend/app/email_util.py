"""Envio de e-mail via Gmail SMTP."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def _smtp_server() -> str:
    return (current_app.config.get("MAIL_SERVER") or "").strip()


def _smtp_password() -> str:
    return (current_app.config.get("MAIL_PASSWORD") or "").strip()


def _smtp_sender() -> str:
    return (current_app.config.get("MAIL_DEFAULT_SENDER") or "").strip()


def _smtp_is_configured() -> bool:
    return bool(_smtp_server() and _smtp_password() and _smtp_sender())


def mail_backend() -> str | None:
    """`smtp` ou None se o transporte não estiver configurado."""
    if _smtp_is_configured():
        return "smtp"
    return None


def mail_is_configured() -> bool:
    return mail_backend() is not None


def default_sender() -> str:
    """Remetente conforme o backend ativo."""
    return _smtp_sender()


def _send_via_smtp(
    to_addr: str,
    subject: str,
    body_text: str,
    *,
    html: str | None = None,
) -> bool:
    server = _smtp_server()
    sender = default_sender()
    if not server or not sender:
        current_app.logger.warning(
            "E-mail não enviado: MAIL_SERVER ou MAIL_DEFAULT_SENDER ausente."
        )
        return False

    user = (current_app.config.get("MAIL_USERNAME") or "").strip()
    password = (current_app.config.get("MAIL_PASSWORD") or "").strip()
    port = int(current_app.config.get("MAIL_PORT") or 587)
    use_ssl = current_app.config.get("MAIL_USE_SSL", False)
    use_tls = current_app.config.get("MAIL_USE_TLS", True)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(server, port, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.sendmail(sender, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(server, port, timeout=30) as smtp:
                if use_tls:
                    smtp.starttls()
                if user:
                    smtp.login(user, password)
                smtp.sendmail(sender, [to_addr], msg.as_string())
        return True
    except Exception as exc:
        current_app.logger.exception("Falha ao enviar e-mail (SMTP) para %s: %s", to_addr, exc)
        return False


def send_email(
    to_addr: str,
    subject: str,
    body_text: str,
    *,
    html: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Envia e-mail texto (e HTML opcional) via Gmail SMTP."""
    if mail_backend() == "smtp":
        if html:
            return _send_via_smtp(to_addr, subject, body_text, html=html)
        return _send_via_smtp(to_addr, subject, body_text)
    current_app.logger.warning(
        "E-mail não enviado para %s: configure MAIL_PASSWORD (Gmail).",
        to_addr,
    )
    return False


def send_simple_email(to_addr: str, subject: str, body_text: str) -> bool:
    """Compatível com chamadas legadas — apenas texto."""
    return send_email(to_addr, subject, body_text)
