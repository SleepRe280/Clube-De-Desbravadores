from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required
import json

from datetime import date

from sqlalchemy import func, or_

from app.access import (
    clube_access_required,
    is_super_admin,
    render_admin_shell,
    role_required,
)
from app.club_services import (
    director_dashboard_stats,
    finance_ledger_query,
    members_query,
)
from app.extensions import db, limiter
from app.finance_util import format_brl_cents
from app.models import (
    CARGO_CONSELHEIRO,
    CARGO_DIRETOR,
    CARGO_PAI,
    CARGO_SECRETARIO,
    CARGO_SUPER_ADMIN,
    CARGO_TESOUREIRO,
    AgendaEvent,
    Club,
    FinanceLedgerEntry,
    Profile,
    User,
)

bp = Blueprint("club", __name__, url_prefix="/clube")


def _nav_event_badge(clube_id: str) -> int:
    from app.club_services import agenda_query

    n = agenda_query(clube_id).filter(AgendaEvent.event_date >= date.today()).count()
    return min(n, 9)


def _club_or_redirect(clube_id: str):
    club = db.session.get(Club, clube_id)
    if not club:
        flash("Clube não encontrado.", "warning")
        return None, redirect(url_for("auth.unauthorized"))
    return club, None


def _redirect_to_user_club(endpoint: str):
    from app.access import current_profile

    profile = current_profile()
    if not profile or not profile.clube_id:
        flash("Seu usuário não está vinculado a um clube.", "warning")
        return redirect(url_for("auth.unauthorized"))
    return redirect(url_for(endpoint, clube_id=profile.clube_id))


@bp.route("/director")
@bp.route("/diretor")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR)
def director_shortcut():
    return redirect(url_for("admin.dashboard"))


@bp.route("/<clube_id>/diretor")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR)
@clube_access_required("clube_id")
def director_panel(clube_id):
    return redirect(url_for("admin.dashboard"))


@bp.route("/<clube_id>/diretor/delegar", methods=["POST"])
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR)
@clube_access_required("clube_id")
@limiter.limit("30 per minute")
def delegate_role(clube_id):
    club, err = _club_or_redirect(clube_id)
    if err:
        return err
    email = (request.form.get("email") or "").strip().lower()
    roles = [r.strip() for r in (request.form.getlist("cargos") or []) if r.strip()]
    valid_roles = {CARGO_TESOUREIRO, CARGO_SECRETARIO, CARGO_CONSELHEIRO}
    if is_super_admin():
        valid_roles.add(CARGO_DIRETOR)
    if CARGO_DIRETOR in roles and not is_super_admin():
        flash(
            "Apenas o administrador mestre pode promover usuários ao cargo de diretor no portal.",
            "warning",
        )
        return redirect(url_for("club.director_panel", clube_id=club.id))
    if CARGO_PAI in roles:
        flash("Responsável do portal família não é uma função delegável.", "warning")
        return redirect(url_for("club.director_panel", clube_id=club.id))
    if not email or not roles or any(r not in valid_roles for r in roles):
        flash("Informe e-mail e selecione uma ou mais funções válidas para delegação.", "warning")
        return redirect(url_for("club.director_panel", clube_id=club.id))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Usuário não encontrado. Peça para criar conta primeiro.", "warning")
        return redirect(url_for("club.director_panel", clube_id=club.id))

    if user.id == current_user.id:
        flash("Não é possível delegar ou alterar funções para a própria conta.", "warning")
        return redirect(url_for("club.director_panel", clube_id=club.id))

    profile = db.session.get(Profile, user.id)
    if not profile:
        profile = Profile(id=user.id)
        db.session.add(profile)
    if profile.clube_id and profile.clube_id != club.id:
        flash("Este e-mail já está vinculado e não pode ser movido por este painel.", "warning")
        return redirect(url_for("club.director_panel", clube_id=club.id))

    profile.clube_id = club.id
    if CARGO_DIRETOR in roles:
        profile.cargo = CARGO_DIRETOR
    else:
        profile.cargo = roles[0]
    profile.cargos_json = json.dumps(sorted(set(roles)))
    profile.nome_completo = profile.nome_completo or user.full_name
    profile.email_verificado = bool(user.email_verified)
    user.role = "admin" if CARGO_DIRETOR in roles else "parent"
    db.session.commit()
    flash("Funções delegadas com sucesso.", "success")
    return redirect(url_for("club.director_panel", clube_id=club.id))


@bp.route("/<clube_id>/tesouraria")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_TESOUREIRO)
@clube_access_required("clube_id")
def tesouraria_panel(clube_id):
    return redirect(url_for("admin.dashboard"))


@bp.route("/tesouraria")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_TESOUREIRO)
def tesouraria_shortcut():
    return redirect(url_for("admin.dashboard"))


@bp.route("/<clube_id>/secretaria")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_SECRETARIO)
@clube_access_required("clube_id")
def secretaria_panel(clube_id):
    return redirect(url_for("admin.dashboard"))


@bp.route("/secretaria")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_SECRETARIO)
def secretaria_shortcut():
    return redirect(url_for("admin.dashboard"))


@bp.route("/<clube_id>/conselheiros")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_CONSELHEIRO)
@clube_access_required("clube_id")
def conselheiros_panel(clube_id):
    return redirect(url_for("admin.dashboard"))


@bp.route("/conselheiros")
@login_required
@role_required(CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_CONSELHEIRO)
def conselheiros_shortcut():
    return redirect(url_for("admin.dashboard"))
