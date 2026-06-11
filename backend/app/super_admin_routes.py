from datetime import datetime
import json
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user
from sqlalchemy import or_

from app.access import cargos_for_profile, role_required
from app.extensions import db
from app.models import BoardPost, CARGO_DIRETOR, CARGO_PAI, CARGO_SUPER_ADMIN, Club, Member, Profile, User
from app.uploads_util import save_upload

bp = Blueprint("super_admin", __name__)


def _profile_has_role(profile: Profile | None, role: str) -> bool:
    if not profile:
        return False
    return role in cargos_for_profile(profile)


def _safe_remove_upload(rel_path: str | None) -> None:
    if not rel_path:
        return
    p = Path(current_app.config["UPLOAD_FOLDER"]) / rel_path
    if p.is_file():
        p.unlink()


@bp.before_request
@login_required
@role_required(CARGO_SUPER_ADMIN)
def _guard():
    pass


@bp.route("/super-admin")
def dashboard():
    clubs = Club.query.order_by(Club.nome.asc()).all()
    profiles = Profile.query.all()
    users = User.query.count()
    selected_club_id = (request.args.get("clube_id") or "").strip()
    search = (request.args.get("q") or "").strip()

    directors_query = (
        db.session.query(User, Profile, Club)
        .join(Profile, Profile.id == User.id)
        .outerjoin(Club, Club.id == Profile.clube_id)
        .filter(Profile.cargo == CARGO_DIRETOR)
    )
    if selected_club_id:
        directors_query = directors_query.filter(Profile.clube_id == selected_club_id)
    if search:
        search_like = f"%{search}%"
        directors_query = directors_query.filter(
            or_(User.email.ilike(search_like), User.full_name.ilike(search_like))
        )
    directors = directors_query.order_by(User.full_name.asc(), User.email.asc()).all()
    club_director_user_ids = {}
    for dir_user, profile, club in directors:
        if club and club.id and club.id not in club_director_user_ids:
            club_director_user_ids[club.id] = dir_user.id
    counts = {
        "users": users,
        "clubes": Club.query.count(),
        "diretores": sum(1 for p in profiles if p.cargo == CARGO_DIRETOR),
        "pais": sum(1 for p in profiles if p.cargo == CARGO_PAI),
    }
    return render_template(
        "super_admin/dashboard.html",
        clubs=clubs,
        counts=counts,
        directors=directors,
        club_director_user_ids=club_director_user_ids,
        selected_club_id=selected_club_id,
        search=search,
    )


@bp.route("/super-admin/entrar-como-admin/<int:user_id>", methods=["POST"])
def enter_as_director(user_id):
    user = db.session.get(User, user_id)
    profile = db.session.get(Profile, user_id) if user else None
    if not user or not _profile_has_role(profile, CARGO_DIRETOR):
        flash("Diretor não encontrado para entrar como admin.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    session["super_admin_impersonating"] = True
    session["super_admin_original_user_id"] = current_user.id
    login_user(user, remember=False, fresh=True)
    if profile and profile.clube_id:
        return redirect(url_for("admin.dashboard", clube_id=profile.clube_id))
    return redirect(url_for("admin.dashboard"))


@bp.route("/super-admin/clubes/novo", methods=["POST"])
def create_club():
    nome = (request.form.get("nome") or "").strip()
    cidade = (request.form.get("cidade") or "").strip()
    regiao = (request.form.get("regiao") or "").strip()
    cor_primaria = (request.form.get("cor_primaria") or "").strip() or "#003580"
    cor_secundaria = (request.form.get("cor_secundaria") or "").strip() or "#FFD700"
    cor_accent = (request.form.get("cor_accent") or "").strip() or "#CC0000"
    titulo_sistema = (request.form.get("titulo_sistema") or "").strip() or "Portal do Clube"
    template_slug = (request.form.get("template_slug") or "").strip() or "generico"

    if not nome:
        flash("Informe o nome do clube.", "warning")
        return redirect(url_for("super_admin.dashboard"))

    brasao_rel = save_upload(request.files.get("brasao"), current_app.config["UPLOAD_FOLDER"], "clubes")
    descricao = (request.form.get("descricao") or "").strip() or None
    club = Club(
        nome=nome,
        descricao=descricao,
        cidade=cidade or None,
        regiao=regiao or None,
        cor_primaria=cor_primaria,
        cor_secundaria=cor_secundaria,
        cor_accent=cor_accent,
        titulo_sistema=titulo_sistema,
        template_slug=template_slug,
        brasao_url=(f"/uploads/{brasao_rel}" if brasao_rel else None),
        criado_em=datetime.utcnow(),
    )
    db.session.add(club)
    db.session.commit()
    flash("Novo clube criado com sucesso.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/clubes/<clube_id>/editar", methods=["POST"])
def update_club(clube_id):
    club = db.session.get(Club, clube_id)
    if not club:
        flash("Clube não encontrado.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Nome do clube é obrigatório.", "warning")
        return redirect(url_for("super_admin.dashboard", clube_id=clube_id))
    club.nome = nome
    club.descricao = (request.form.get("descricao") or "").strip() or None
    club.cidade = (request.form.get("cidade") or "").strip() or None
    club.regiao = (request.form.get("regiao") or "").strip() or None
    club.titulo_sistema = (request.form.get("titulo_sistema") or "").strip() or club.titulo_sistema
    club.cor_primaria = (request.form.get("cor_primaria") or "").strip() or club.cor_primaria
    club.cor_secundaria = (request.form.get("cor_secundaria") or "").strip() or club.cor_secundaria
    club.cor_accent = (request.form.get("cor_accent") or "").strip() or club.cor_accent
    slug = (request.form.get("template_slug") or "").strip()
    if slug and club.template_slug != "duque_de_caxias":
        club.template_slug = slug
    brasao_rel = save_upload(request.files.get("brasao"), current_app.config["UPLOAD_FOLDER"], "clubes")
    if brasao_rel:
        if club.brasao_url and club.brasao_url.startswith("/uploads/"):
            _safe_remove_upload(club.brasao_url.replace("/uploads/", "", 1))
        club.brasao_url = f"/uploads/{brasao_rel}"
    db.session.commit()
    flash("Clube atualizado.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/diretores/atribuir", methods=["POST"])
def assign_director():
    email = (request.form.get("email") or "").strip().lower()
    clube_id = (request.form.get("clube_id") or "").strip()
    nome = (request.form.get("nome_completo") or "").strip()

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Usuário não encontrado. Peça para ele criar conta primeiro.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    club = db.session.get(Club, clube_id)
    if not club:
        flash("Clube inválido.", "warning")
        return redirect(url_for("super_admin.dashboard"))

    profile = db.session.get(Profile, user.id)
    if not profile:
        profile = Profile(id=user.id)
        db.session.add(profile)
    profile.cargo = CARGO_DIRETOR
    profile.cargos_json = json.dumps([CARGO_DIRETOR])
    profile.clube_id = club.id
    profile.nome_completo = nome or user.full_name
    profile.email_verificado = True
    user.role = "admin"
    db.session.commit()

    flash("Diretor vinculado ao clube com sucesso.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/clubes/<clube_id>/brasao/remover", methods=["POST"])
def remove_brasao(clube_id):
    club = db.session.get(Club, clube_id)
    if not club:
        flash("Clube não encontrado.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    if club.brasao_url and club.brasao_url.startswith("/uploads/"):
        _safe_remove_upload(club.brasao_url.replace("/uploads/", "", 1))
    club.brasao_url = None
    db.session.commit()
    flash("Brasão removido.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/clubes/<clube_id>/excluir", methods=["POST"])
def delete_club(clube_id):
    club = db.session.get(Club, clube_id)
    if not club:
        flash("Clube não encontrado.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    if club.template_slug == "duque_de_caxias":
        flash("O clube de referência (Duque de Caxias) não pode ser excluído.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    n_users = Profile.query.filter_by(clube_id=clube_id).count()
    if n_users > 0:
        flash(
            f"Não é possível excluir: há {n_users} usuário(s) vinculado(s) a este clube. "
            "Transfira ou remova os vínculos antes.",
            "warning",
        )
        return redirect(url_for("super_admin.dashboard"))
    if club.brasao_url and club.brasao_url.startswith("/uploads/"):
        _safe_remove_upload(club.brasao_url.replace("/uploads/", "", 1))
    db.session.delete(club)
    db.session.commit()
    flash("Clube excluído com sucesso.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/diretores/<int:user_id>/editar", methods=["POST"])
def update_director(user_id):
    user = db.session.get(User, user_id)
    profile = db.session.get(Profile, user_id) if user else None
    if not user or not _profile_has_role(profile, CARGO_DIRETOR):
        flash("Diretor não encontrado.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    nome = (request.form.get("nome_completo") or "").strip()
    clube_id = (request.form.get("clube_id") or "").strip()
    club = db.session.get(Club, clube_id)
    if not club:
        flash("Clube inválido para este diretor.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    if nome:
        user.full_name = nome
        profile.nome_completo = nome
    profile.clube_id = club.id
    # Diretor editado no painel super admin sempre vira diretor pleno do clube.
    profile.cargo = CARGO_DIRETOR
    profile.cargos_json = json.dumps([CARGO_DIRETOR])
    user.role = "admin"
    db.session.commit()
    flash("Conta do diretor atualizada.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/diretores/<int:user_id>/remover", methods=["POST"])
def remove_director(user_id):
    user = db.session.get(User, user_id)
    profile = db.session.get(Profile, user_id) if user else None
    if not user or not _profile_has_role(profile, CARGO_DIRETOR):
        flash("Diretor não encontrado.", "warning")
        return redirect(url_for("super_admin.dashboard"))
    profile.cargo = CARGO_PAI
    profile.cargos_json = json.dumps([CARGO_PAI])
    user.role = "parent"
    db.session.commit()
    flash("Permissão de diretor removida. Usuário voltou para perfil de responsável.", "info")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/super-admin/diretores/<int:user_id>/excluir", methods=["POST"])
def delete_director_account(user_id):
    """Exclui a conta do diretor (usuário + perfil) quando não houver dados vinculados."""
    if user_id == current_user.id:
        flash("Você não pode excluir sua própria conta.", "danger")
        return redirect(url_for("super_admin.dashboard"))

    user = db.session.get(User, user_id)
    profile = db.session.get(Profile, user_id) if user else None
    if not user or not _profile_has_role(profile, CARGO_DIRETOR):
        flash("Diretor não encontrado.", "warning")
        return redirect(url_for("super_admin.dashboard"))

    if _profile_has_role(profile, CARGO_SUPER_ADMIN):
        flash("Não é possível excluir uma conta de super admin por este painel.", "danger")
        return redirect(url_for("super_admin.dashboard"))

    has_children = (
        db.session.query(Member.id).filter(Member.parent_id == user_id).limit(1).first()
        is not None
    )
    has_posts = (
        db.session.query(BoardPost.id)
        .filter(BoardPost.author_id == user_id)
        .limit(1)
        .first()
        is not None
    )
    if has_children or has_posts:
        flash(
            "Não foi possível excluir esta conta: existem registros vinculados (filhos e/ou publicações). "
            "Use 'Remover cargo de diretor' para desativar o acesso administrativo.",
            "warning",
        )
        return redirect(url_for("super_admin.dashboard"))

    db.session.delete(profile)
    db.session.delete(user)
    db.session.commit()
    flash("Conta do diretor excluída com sucesso.", "success")
    return redirect(url_for("super_admin.dashboard"))
