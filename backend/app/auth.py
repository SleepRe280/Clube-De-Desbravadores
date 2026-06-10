from datetime import datetime, timedelta
import json
import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.access import route_for_user
from app.email_util import send_simple_email
from app.extensions import db, limiter
from app.models import (
    CARGO_CONSELHEIRO,
    CARGO_DIRETOR,
    CARGO_PAI,
    CARGO_SECRETARIO,
    CARGO_SUPER_ADMIN,
    CARGO_TESOUREIRO,
    Club,
    DirectorateMember,
    EmailVerificationToken,
    PasswordResetToken,
    Profile,
    User,
)
from app.uploads_util import safe_remove_upload, save_upload

bp = Blueprint("auth", __name__)

# Imagem da tela de login (sempre o emblema oficial; independente do brasão do clube no cadastro).
LOGIN_BRAND_STATIC = "img/brasao-desbravadores-oficial.png"


def _login_next_url():
    n = request.form.get("next") if request.method == "POST" else request.args.get("next")
    return (n or "").strip() or None


def _register_context():
    clubes = Club.query.order_by(Club.nome.asc()).all()
    return {"clubes": clubes}


def _profile_has_super_admin_role(profile: Profile | None) -> bool:
    if not profile:
        return False
    if profile.cargo == CARGO_SUPER_ADMIN:
        return True
    raw = getattr(profile, "cargos_json", None)
    if not raw:
        return False
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return CARGO_SUPER_ADMIN in {str(x).strip() for x in data if str(x).strip()}
    except Exception:
        pass
    return False


def _staff_cargo_roles():
    return {
        CARGO_SUPER_ADMIN,
        CARGO_DIRETOR,
        CARGO_SECRETARIO,
        CARGO_TESOUREIRO,
        CARGO_CONSELHEIRO,
    }


def _user_has_staff_access() -> bool:
    from app.access import current_cargos

    return bool(current_cargos().intersection(_staff_cargo_roles()))


def _process_profile_update_from_form():
    """Atualiza nome e e-mail a partir de request.form. Emite flash e retorna True se concluiu sem erro de validação."""
    full_name = (request.form.get("full_name") or "").strip()
    new_email = (request.form.get("email") or "").strip().lower()
    email_password = (request.form.get("email_password") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    bio = (request.form.get("bio") or "").strip()
    remove_photo = request.form.get("remove_photo") == "1"
    photo_file = request.files.get("profile_photo")

    if new_email and new_email != current_user.email:
        if not email_password or not current_user.check_password(email_password):
            flash("Informe a senha atual corretamente para alterar o e-mail.", "danger")
            return False
        taken = User.query.filter(User.email == new_email, User.id != current_user.id).first()
        if taken:
            flash("Este e-mail já está em uso por outra conta.", "warning")
            return False

    profile = _ensure_profile_for_user(current_user)
    directorate = (
        DirectorateMember.query.filter_by(user_id=current_user.id)
        .order_by(DirectorateMember.updated_at.desc())
        .first()
    )
    changed = False
    if full_name:
        current_user.full_name = full_name
        profile.nome_completo = full_name
        if directorate:
            directorate.full_name = full_name
        changed = True
    if new_email and new_email != current_user.email:
        current_user.email = new_email
        if directorate:
            directorate.email = new_email
            if not directorate.email_public:
                directorate.email_public = new_email
        changed = True
    if phone != (profile.phone or ""):
        profile.phone = phone or None
        if directorate:
            directorate.phone = phone or None
        changed = True
    if directorate and bio != (directorate.bio or ""):
        directorate.bio = bio or None
        changed = True
    if directorate and remove_photo and directorate.photo_filename:
        safe_remove_upload(current_app.config["UPLOAD_FOLDER"], directorate.photo_filename)
        directorate.photo_filename = None
        changed = True
    if directorate and photo_file and photo_file.filename:
        saved = save_upload(photo_file, current_app.config["UPLOAD_FOLDER"], "directorate")
        if not saved:
            flash("Formato de foto inválido. Use JPG, PNG ou WEBP.", "warning")
            return False
        safe_remove_upload(current_app.config["UPLOAD_FOLDER"], directorate.photo_filename)
        directorate.photo_filename = saved
        changed = True
    if changed:
        db.session.commit()
        flash("Dados atualizados.", "success")
    else:
        flash("Nada para alterar.", "info")
    return True


def process_account_form():
    """Atualiza nome/e-mail (POST). Usado pela área do responsável e por /usuario."""
    return _process_profile_update_from_form()


@bp.route("/usuario", methods=["GET", "POST"])
@login_required
def usuario():
    if not _user_has_staff_access():
        return redirect(url_for("parent.account"))
    profile = _ensure_profile_for_user(current_user)
    if request.method == "POST":
        _process_profile_update_from_form()
        return redirect(url_for("auth.usuario"))
    clube = profile.clube
    cargos = []
    if profile.cargos_json:
        try:
            data = json.loads(profile.cargos_json)
            if isinstance(data, list):
                cargos = [str(x).strip() for x in data if str(x).strip()]
        except Exception:
            cargos = []
    if not cargos and profile.cargo:
        cargos = [profile.cargo]
    label_map = {
        CARGO_SUPER_ADMIN: "Super admin",
        CARGO_DIRETOR: "Diretor(a)",
        CARGO_SECRETARIO: "Secretaria",
        CARGO_TESOUREIRO: "Tesouraria",
        CARGO_CONSELHEIRO: "Conselheiro(a)",
        CARGO_PAI: "Responsável",
    }
    cargo_labels_pt = [label_map.get(c, c) for c in cargos]
    db.session.commit()
    directorate = (
        DirectorateMember.query.filter_by(user_id=current_user.id)
        .order_by(DirectorateMember.updated_at.desc())
        .first()
    )
    profile_photo_url = (
        url_for("uploaded_file", rel_path=directorate.photo_filename)
        if directorate and directorate.photo_filename
        else None
    )
    role_label = directorate.cargo if directorate and directorate.cargo else (cargo_labels_pt[0] if cargo_labels_pt else "Diretoria")
    back_url = route_for_user(current_user)
    return render_template(
        "auth/user_profile.html",
        profile=profile,
        clube=clube,
        cargos=cargos,
        cargo_labels_pt=cargo_labels_pt,
        back_url=back_url,
        role_label=role_label,
        profile_phone=profile.phone or "",
        profile_bio=(directorate.bio if directorate and directorate.bio else ""),
        profile_photo_url=profile_photo_url,
    )


def _ensure_profile_for_user(user: User, clube_id: str | None = None, cargo: str | None = None):
    profile = db.session.get(Profile, user.id)
    if not profile:
        profile = Profile(id=user.id)
        db.session.add(profile)
    if not profile.nome_completo:
        profile.nome_completo = user.full_name
    if clube_id:
        profile.clube_id = clube_id
    if cargo:
        profile.cargo = cargo
        profile.cargos_json = json.dumps([cargo])
    elif not profile.cargos_json and profile.cargo:
        profile.cargos_json = json.dumps([profile.cargo])
    profile.email_verificado = bool(user.email_verified)
    return profile


def _can_transfer_registration(profile: Profile | None) -> bool:
    if not profile:
        return True
    return profile.cargo in (
        CARGO_PAI,
        CARGO_TESOUREIRO,
        CARGO_SECRETARIO,
        CARGO_CONSELHEIRO,
    )


@bp.route("/unauthorized")
def unauthorized():
    return render_template("auth/unauthorized.html"), 403


@bp.route("/perfil")
@login_required
def perfil():
    return redirect(url_for("auth.usuario"))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("40 per minute", exempt_when=lambda: request.method == "GET")
def login():
    # Mantém a tela de login como "tela inicial" e permite trocar de conta
    # (ex.: sair de diretor e entrar como super admin) sem precisar acessar /logout.
    if current_user.is_authenticated and request.method == "GET":
        flash("Você já está logado. Para entrar com outra conta, faça login novamente.", "info")

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.email_verified:
                flash(
                    "Confirme seu e-mail antes de entrar. Verifique sua caixa de entrada "
                    "ou solicite um novo link ao clube.",
                    "warning",
                )
                return render_template(
                    "auth/login.html",
                    next_url=_login_next_url(),
                    login_brand_img=url_for("static", filename=LOGIN_BRAND_STATIC),
                )
            profile = _ensure_profile_for_user(user)
            if not profile.cargo:
                profile.cargo = CARGO_DIRETOR if user.is_admin() else CARGO_PAI
            if not profile.cargos_json and profile.cargo:
                profile.cargos_json = json.dumps([profile.cargo])
            user.last_seen_at = datetime.utcnow()
            db.session.commit()
            remember = request.form.get("remember") in ("1", "on", "true")
            login_user(user, remember=remember)
            db.session.expire_all()
            next_url = _login_next_url()
            if next_url:
                return redirect(next_url)
            return redirect(route_for_user(user))
        flash("E-mail ou senha incorretos.", "danger")
    return render_template(
        "auth/login.html",
        next_url=_login_next_url(),
        login_brand_img=url_for("static", filename=LOGIN_BRAND_STATIC),
    )


@bp.route("/logout")
def logout():
    session.pop("super_admin_impersonating", None)
    session.pop("super_admin_original_user_id", None)
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/super-admin/voltar")
@login_required
def back_to_super_admin():
    if not session.get("super_admin_impersonating"):
        return redirect(route_for_user(current_user))
    original_id = session.get("super_admin_original_user_id")
    if not original_id:
        session.pop("super_admin_impersonating", None)
        return redirect(route_for_user(current_user))
    original = db.session.get(User, int(original_id))
    profile = db.session.get(Profile, int(original_id)) if original else None
    if not original or not profile or not _profile_has_super_admin_role(profile):
        session.pop("super_admin_impersonating", None)
        session.pop("super_admin_original_user_id", None)
        flash("Não foi possível retornar para o super admin original.", "warning")
        return redirect(route_for_user(current_user))
    login_user(original, remember=False, fresh=True)
    session.pop("super_admin_impersonating", None)
    session.pop("super_admin_original_user_id", None)
    flash("Sessão super admin restaurada.", "success")
    return redirect(url_for("super_admin.dashboard"))


@bp.route("/esqueci-senha", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(route_for_user(current_user))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email, role="parent").first()
        if user:
            PasswordResetToken.query.filter_by(user_id=user.id).delete()
            token = secrets.token_urlsafe(32)
            row = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
            db.session.add(row)
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            body = (
                f"Olá!\n\nPara criar uma nova senha no portal do clube, acesse:\n{reset_url}\n\n"
                "O link expira em 24 horas.\n"
            )
            sent = send_simple_email(
                user.email, "Recuperação de senha — Portal do clube", body
            )
            if not sent and current_app.debug:
                flash(
                    f"Desenvolvimento: abra este link para criar uma nova senha — {reset_url}",
                    "info",
                )
        flash(
            "Se este e-mail estiver cadastrado como responsável, você receberá instruções para redefinir a senha. "
            "Caso contrário, procure o clube.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(route_for_user(current_user))

    row = PasswordResetToken.query.filter_by(token=token).first()
    if not row or row.expires_at < datetime.utcnow():
        flash("Link inválido ou expirado. Solicite um novo.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, row.user_id)
    if not user or user.role != "parent":
        flash("Conta inválida.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        p1 = request.form.get("password") or ""
        p2 = request.form.get("password2") or ""
        if len(p1) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "warning")
            return render_template("auth/reset_password.html", token=token)
        if p1 != p2:
            flash("As senhas não coincidem.", "warning")
            return render_template("auth/reset_password.html", token=token)
        user.set_password(p1)
        PasswordResetToken.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        flash("Senha atualizada. Faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)


@bp.route("/cadastro", methods=["GET", "POST"])
@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(route_for_user(current_user))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        full_name = (request.form.get("full_name") or "").strip()
        clube_id = (request.form.get("clube_id") or "").strip()
        allow_transfer = request.form.get("allow_transfer") == "1"

        if not email or not password or not full_name or not clube_id:
            flash("Preencha todos os campos.", "warning")
            return render_template("auth/register.html", **_register_context())

        clube = db.session.get(Club, clube_id)
        if not clube:
            flash("Selecione um clube válido.", "warning")
            return render_template("auth/register.html", **_register_context())

        if email == "admin@clube.com":
            flash("Este e-mail é reservado para a conta da diretoria.", "warning")
            return render_template("auth/register.html", **_register_context())

        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "warning")
            return render_template("auth/register.html", **_register_context())

        existing = User.query.filter_by(email=email).first()
        if existing:
            profile = db.session.get(Profile, existing.id)
            if not allow_transfer:
                flash(
                    "Este e-mail já possui cadastro em um clube. Para transferir seu cadastro, "
                    "marque a opção de exclusão do vínculo anterior.",
                    "warning",
                )
                return render_template("auth/register.html", **_register_context())
            if not _can_transfer_registration(profile):
                flash(
                    "Esta conta não pode ser transferida por autoatendimento. "
                    "Peça ajuda ao admin mestre.",
                    "danger",
                )
                return render_template("auth/register.html", **_register_context())
            existing.full_name = full_name
            existing.role = "parent"
            existing.email_verified = True
            existing.set_password(password)
            _ensure_profile_for_user(existing, clube_id=clube_id, cargo=CARGO_PAI)
            db.session.commit()
            flash(
                "Cadastro transferido para o novo clube com sucesso. O vínculo anterior foi substituído.",
                "success",
            )
            return redirect(url_for("auth.login"))

        user = User(
            email=email, role="parent", full_name=full_name, email_verified=False
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        _ensure_profile_for_user(user, clube_id=clube_id, cargo=CARGO_PAI)
        EmailVerificationToken.query.filter_by(user_id=user.id).delete()
        token = secrets.token_urlsafe(32)
        row = EmailVerificationToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=48),
        )
        db.session.add(row)
        db.session.commit()
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        body = (
            f"Olá, {full_name}!\n\n"
            f"Para confirmar seu cadastro no portal do clube, acesse:\n{confirm_url}\n\n"
            "O link expira em 48 horas.\n"
        )
        sent = send_simple_email(
            user.email, "Confirme seu e-mail — Portal do clube", body
        )
        if not sent and current_app.debug:
            flash(
                f"Desenvolvimento: abra este link para confirmar o e-mail — {confirm_url}",
                "info",
            )
        flash(
            "Conta criada. Verifique seu e-mail para confirmar o cadastro antes de fazer login. "
            "Depois, aguarde o diretor ou a secretaria vincular seu filho em Responsáveis e vínculos.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", **_register_context())


@bp.route("/confirmar-cadastro", methods=["GET", "POST"])
def confirm_registration_code():
    return redirect(url_for("auth.register"))


@bp.route("/confirmar-email/<token>")
def confirm_email(token):
    row = EmailVerificationToken.query.filter_by(token=token).first()
    if not row or row.expires_at < datetime.utcnow():
        flash("Link inválido ou expirado. Faça um novo cadastro ou procure o clube.", "danger")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, row.user_id)
    if not user:
        flash("Conta inválida.", "danger")
        return redirect(url_for("auth.login"))

    user.email_verified = True
    profile = db.session.get(Profile, user.id)
    if profile:
        profile.email_verificado = True
    db.session.delete(row)
    db.session.commit()
    flash("E-mail confirmado com sucesso. Faça login para continuar.", "success")
    return redirect(url_for("auth.login"))


def _default_password_done_redirect():
    if _user_has_staff_access():
        return url_for("auth.usuario")
    return url_for("parent.account")


@bp.route("/conta/senha", methods=["GET", "POST"])
@login_required
def change_password():
    next_done = (request.form.get("next") or request.args.get("next") or "").strip()
    back_url = (request.form.get("back") or request.args.get("back") or "").strip() or _default_password_done_redirect()

    def _render_err():
        return render_template(
            "auth/change_password.html",
            next_url=next_done,
            back_url=back_url,
        )

    if request.method == "POST":
        cur = request.form.get("current_password") or ""
        p1 = request.form.get("password") or ""
        p2 = request.form.get("password2") or ""
        if not current_user.check_password(cur):
            flash("Senha atual incorreta.", "danger")
            return _render_err()
        if len(p1) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "warning")
            return _render_err()
        if p1 != p2:
            flash("As senhas novas não coincidem.", "warning")
            return _render_err()
        current_user.set_password(p1)
        db.session.commit()
        flash("Senha alterada com sucesso.", "success")
        return redirect(next_done or _default_password_done_redirect())

    return render_template(
        "auth/change_password.html",
        next_url=next_done,
        back_url=back_url,
    )
