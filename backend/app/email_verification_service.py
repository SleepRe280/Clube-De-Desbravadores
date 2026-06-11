"""Verificação de e-mail no cadastro (Gmail SMTP ou Resend).

Ative em produção com:
  EMAIL_VERIFICATION_REQUIRED=1
  MAIL_PASSWORD=<senha de app do Google>   # conta sleepre07@gmail.com
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from flask import current_app, render_template, url_for

from app.email_util import mail_is_configured, send_email
from app.extensions import db
from app.models import EmailVerificationToken, Profile, User

VERIFICATION_TOKEN_HOURS = 48


def email_verification_required() -> bool:
    """Verificação só vale se a flag estiver ligada e o transporte de e-mail configurado."""
    if not current_app.config.get("EMAIL_VERIFICATION_REQUIRED"):
        return False
    if mail_is_configured():
        return True
    current_app.logger.warning(
        "EMAIL_VERIFICATION_REQUIRED=1 mas e-mail não configurado; cadastro segue sem verificação."
    )
    return False


def user_blocks_login_until_verified(user: User) -> bool:
    return email_verification_required() and not user.email_verified


def login_verification_message() -> str:
    return (
        "Confirme seu e-mail antes de entrar. Verifique sua caixa de entrada "
        "ou solicite um novo link ao clube."
    )


def issue_verification_token(user_id: int) -> str:
    EmailVerificationToken.query.filter_by(user_id=user_id).delete()
    token = secrets.token_urlsafe(32)
    row = EmailVerificationToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_HOURS),
    )
    db.session.add(row)
    return token


def send_verification_email(user: User, token: str) -> bool:
    confirm_url = url_for("auth.confirm_email", token=token, _external=True)
    subject = "Confirme seu e-mail — Portal do clube"
    body_text = (
        f"Olá, {user.full_name or 'responsável'}!\n\n"
        f"Para confirmar seu cadastro no portal do clube, acesse:\n{confirm_url}\n\n"
        f"O link expira em {VERIFICATION_TOKEN_HOURS} horas.\n"
    )
    html = render_template(
        "email/verify_email.html",
        user_name=user.full_name or "responsável",
        confirm_url=confirm_url,
        expires_hours=VERIFICATION_TOKEN_HOURS,
    )
    return send_email(user.email, subject, body_text, html=html)


def confirm_verification_token(token: str) -> tuple[User | None, str | None]:
    """Retorna (user, None) em sucesso ou (None, mensagem_de_erro)."""
    row = EmailVerificationToken.query.filter_by(token=token).first()
    if not row or row.expires_at < datetime.utcnow():
        return None, "Link inválido ou expirado. Faça um novo cadastro ou procure o clube."

    user = db.session.get(User, row.user_id)
    if not user:
        return None, "Conta inválida."

    user.email_verified = True
    profile = db.session.get(Profile, user.id)
    if profile:
        profile.email_verificado = True
    db.session.delete(row)
    db.session.commit()
    return user, None


def registration_success_message(*, verification_sent: bool) -> str:
    if verification_sent:
        return (
            "Conta criada. Verifique seu e-mail para confirmar o cadastro antes de fazer login. "
            "Depois, aguarde o diretor ou a secretaria vincular seu filho em Responsáveis e vínculos."
        )
    return (
        "Conta criada com sucesso. Faça login e aguarde o diretor ou a secretaria "
        "vincular seu filho em Responsáveis e vínculos."
    )
