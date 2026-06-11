import os
import json

import click
from flask import Flask, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

from app.access import route_for_user
from app.extensions import csrf, db, limiter
from config import Config, INSTANCE_DIR


def _configure_sqlite_engine(app) -> None:
    """WAL + busy_timeout — menos bloqueios com SQLite em pasta sincronizada (OneDrive)."""
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    if "sqlite" not in uri:
        return
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=45000")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    except Exception as exc:
        app.logger.warning("SQLite PRAGMA: %s", exc)


def _upsert_director_admin(email: str, password: str, full_name: str = "Diretoria do Clube") -> str:
    """Cria ou promove conta de diretor de clube (cargo diretor + clube padrão)."""
    from app.models import CARGO_DIRETOR, Club, Profile, User

    email = email.strip().lower()
    full_name = (full_name or "").strip() or "Diretoria do Clube"
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = "admin"
        u.email_verified = True
        u.full_name = full_name or u.full_name
        u.set_password(password)
    else:
        u = User(
            email=email,
            role="admin",
            full_name=full_name or "Admin",
            email_verified=True,
        )
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
    profile = db.session.get(Profile, u.id) if u.id else None
    if not profile:
        profile = Profile(id=u.id)
        db.session.add(profile)
    profile.cargo = CARGO_DIRETOR
    profile.cargos_json = json.dumps([CARGO_DIRETOR])
    profile.nome_completo = full_name or u.full_name
    profile.email_verificado = True
    if not profile.clube_id:
        default_club = Club.query.filter_by(template_slug="duque_de_caxias").first()
        if default_club:
            profile.clube_id = default_club.id
    db.session.commit()
    return email


def _ensure_bootstrap_director(app) -> None:
    """Render free tier não tem Shell — use DIRECTOR_ADMIN_* no Environment."""
    email = os.environ.get("DIRECTOR_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("DIRECTOR_ADMIN_PASSWORD", "").strip()
    if not email or not password:
        return
    full_name = os.environ.get("DIRECTOR_ADMIN_FULL_NAME", "").strip() or "Diretoria do Clube"
    configured = _upsert_director_admin(email, password, full_name)
    app.logger.info(
        "Conta de diretoria configurada via DIRECTOR_ADMIN_*: %s "
        "(remova DIRECTOR_ADMIN_PASSWORD do Environment após o primeiro login)",
        configured,
    )


def _initialize_database(app):
    """Cria tabelas e migrações; não impede o servidor de subir se o SQLite estiver bloqueado."""
    try:
        with app.app_context():
            db.create_all()
            from app.db_migrate import (
                backfill_clube_scope_data,
                ensure_default_club_and_profiles,
                ensure_leadership_accounts_admin_role,
                ensure_multiclub_scope_columns,
                ensure_leadership_premium_schema,
                ensure_parent_link_schema,
                ensure_activities_schema,
                ensure_specialties_schema,
                ensure_units_schema,
                ensure_gallery_schema,
                merge_club_news_into_board_posts,
                migrate_sqlite_schema,
                normalize_profile_roles,
                ensure_users_email_verified_column,
                mark_all_emails_verified,
            )

            migrate_sqlite_schema(app)
            ensure_parent_link_schema(app)
            ensure_users_email_verified_column(app)
            mark_all_emails_verified(app)
            ensure_multiclub_scope_columns(app)
            ensure_leadership_premium_schema(app)
            ensure_specialties_schema(app)
            ensure_units_schema(app)
            ensure_gallery_schema(app)
            ensure_activities_schema(app)
            merge_club_news_into_board_posts(app)
            ensure_default_club_and_profiles(app)
            backfill_clube_scope_data(app)
            ensure_leadership_accounts_admin_role(app)
            normalize_profile_roles(app)
            _ensure_master_admin(app)
            _ensure_bootstrap_director(app)
    except Exception as exc:
        app.logger.exception(
            "Falha na inicialização do banco (%s). O site pode abrir com funcionalidades "
            "limitadas — feche outras instâncias do app ou mova instance/ para fora do OneDrive.",
            exc,
        )


def create_app(config_class=Config):
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(os.path.dirname(_app_dir))
    _frontend_dir = os.path.join(_project_root, "frontend")
    _templates_dir = os.path.join(_frontend_dir, "templates")
    _static_dir = os.path.join(_frontend_dir, "static")
    if not os.path.isdir(_templates_dir):
        raise RuntimeError(
            f"Pasta de templates não encontrada: {_templates_dir}. "
            "Confirme que frontend/ está na raiz do repositório (ao lado de backend/)."
        )
    if not os.path.isdir(_static_dir):
        raise RuntimeError(
            f"Pasta de arquivos estáticos não encontrada: {_static_dir}. "
            "Confirme que frontend/static/ existe."
        )
    app = Flask(
        __name__,
        template_folder=os.path.join(_frontend_dir, "templates"),
        static_folder=os.path.join(_frontend_dir, "static"),
    )
    app.config.from_object(config_class)

    from app.access import ADMIN_PANEL_DEFAULTS

    app.jinja_env.globals["admin_panel_defaults"] = ADMIN_PANEL_DEFAULTS

    from app.template_filters import register_template_filters

    register_template_filters(app)

    # Evita "crash" em ambientes locais que estejam com FLASK_ENV=production por engano.
    # Em produção, ainda é altamente recomendado configurar SECRET_KEY.
    if os.environ.get("FLASK_ENV") == "production" and app.config.get(
        "SECRET_KEY"
    ) in (None, "", "troque-esta-chave-em-producao"):
        app.logger.warning(
            "SECRET_KEY não configurada (usando padrão). "
            "Defina SECRET_KEY em produção para segurança."
        )

    if os.environ.get("TRUST_PROXY", "").strip().lower() in ("1", "true", "yes", "on"):
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1
        )

    os.makedirs(INSTANCE_DIR, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    _configure_sqlite_engine(app)

    from app import models  # noqa: F401

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(models.User, int(user_id))
        if user:
            db.session.expire(user)
        return user

    @login_manager.unauthorized_handler
    def _login_required_redirect():
        return redirect(url_for("auth.login", next=request.url))

    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp)

    from app.admin_routes import bp as admin_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.parent_routes import bp as parent_bp

    app.register_blueprint(parent_bp, url_prefix="/pais")
    from app.super_admin_routes import bp as super_admin_bp

    app.register_blueprint(super_admin_bp)
    from app.club_routes import bp as club_bp

    app.register_blueprint(club_bp)

    csrf.exempt(admin_bp)
    csrf.exempt(parent_bp)
    csrf.exempt(super_admin_bp)
    csrf.exempt(club_bp)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.route("/")
    def index():
        # Sempre inicia no login para permitir escolher a conta
        # (super admin, diretor, pai etc.). O redirecionamento pós-login
        # acontece em auth.login.
        return redirect(url_for("auth.login"))

    @app.route("/club/<path:subpath>")
    def club_legacy_redirect(subpath):
        return redirect(f"/clube/{subpath}")

    @app.route("/parent")
    @app.route("/parent/")
    def parent_legacy_root_redirect():
        return redirect("/pais/")

    @app.route("/parent/<path:subpath>")
    def parent_legacy_redirect(subpath):
        return redirect(f"/pais/{subpath}")

    @app.context_processor
    def inject_active_club_theme():
        from flask_login import current_user

        from app.access import get_admin_panel_permissions
        from app.models import Club

        admin_panel_ctx = {"admin_panel": get_admin_panel_permissions()}

        default_theme = {"primary": "#003580", "secondary": "#FFD700", "accent": "#CC0000"}
        logo_static = url_for("static", filename="img/brasao-desbravadores-oficial.png")
        # Login e cadastro públicos: sempre emblema oficial e tema neutro (brasão do clube não mistura aqui).
        _auth_public = frozenset(
            {
                "auth.login",
                "auth.register",
                "auth.forgot_password",
                "auth.reset_password",
                "auth.confirm_registration_code",
                "auth.confirm_email",
            }
        )
        if (request.endpoint or "") in _auth_public:
            return {
                "active_club": None,
                "theme_colors": default_theme,
                "painel_cargo_label": None,
                "club_logo_src": logo_static,
                "leadership_home_url": None,
                **admin_panel_ctx,
            }

        leadership_home_url = None
        if current_user.is_authenticated:
            leadership_home_url = route_for_user(current_user)

        club = Club.query.filter_by(template_slug="duque_de_caxias").first()
        if current_user.is_authenticated and getattr(current_user, "perfil", None):
            if current_user.perfil.clube:
                club = current_user.perfil.clube
        route_clube_id = request.view_args.get("clube_id") if request.view_args else None
        if route_clube_id:
            route_club = db.session.get(Club, route_clube_id)
            if route_club:
                club = route_club
        if not club:
            return {
                "active_club": None,
                "theme_colors": default_theme,
                "painel_cargo_label": None,
                "club_logo_src": logo_static,
                "leadership_home_url": leadership_home_url,
                **admin_panel_ctx,
            }

        painel_cargo_label = None
        if current_user.is_authenticated and getattr(current_user, "perfil", None):
            from app.access import current_cargos
            from app.models import (
                CARGO_CONSELHEIRO,
                CARGO_DIRETOR,
                CARGO_PAI,
                CARGO_SECRETARIO,
                CARGO_SUPER_ADMIN,
                CARGO_TESOUREIRO,
            )

            labels = []
            for c in sorted(current_cargos()):
                labels.append(
                    {
                        CARGO_SUPER_ADMIN: "Super admin",
                        CARGO_DIRETOR: "Diretor(a)",
                        CARGO_SECRETARIO: "Secretaria",
                        CARGO_TESOUREIRO: "Tesouraria",
                        CARGO_CONSELHEIRO: "Conselheiro(a)",
                        CARGO_PAI: "Responsável",
                    }.get(c, c)
                )
            if labels:
                painel_cargo_label = "Função: " + ", ".join(labels)

        club_logo_src = club.brasao_url if getattr(club, "brasao_url", None) else logo_static

        return {
            "active_club": club,
            "theme_colors": {
                "primary": club.cor_primaria or default_theme["primary"],
                "secondary": club.cor_secundaria or default_theme["secondary"],
                "accent": club.cor_accent or default_theme["accent"],
            },
            "painel_cargo_label": painel_cargo_label,
            "club_logo_src": club_logo_src,
            "leadership_home_url": leadership_home_url,
            **admin_panel_ctx,
        }

    @app.context_processor
    def inject_admin_nav_kw():
        from flask_login import current_user

        from app.access import is_super_admin

        if not getattr(current_user, "is_authenticated", False):
            return {"admin_nav_kw": {}}
        ep = request.endpoint or ""
        if not ep.startswith("admin."):
            return {"admin_nav_kw": {}}
        try:
            from app.admin_routes import resolve_admin_clube_id

            cid = resolve_admin_clube_id()
        except Exception:
            cid = (request.args.get("clube_id") or "").strip() or None
        if is_super_admin() and cid:
            return {"admin_nav_kw": {"clube_id": cid}}
        return {"admin_nav_kw": {}}

    @app.route("/uploads/<path:rel_path>")
    def uploaded_file(rel_path):
        return send_from_directory(app.config["UPLOAD_FOLDER"], rel_path)

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    @app.errorhandler(404)
    def _not_found(_exc):
        if request.path.startswith("/api/") or (
            request.accept_mimetypes.best == "application/json"
        ):
            return {"error": "not_found"}, 404
        return (
            render_template(
                "errors/offline.html",
                title="Página não encontrada",
                message="O endereço que você abriu não existe neste servidor.",
                show_restart_hint=False,
            ),
            404,
        )

    @app.errorhandler(500)
    def _server_error(_exc):
        app.logger.exception("Erro interno em %s", request.path)
        if request.path.startswith("/api/"):
            return {"error": "server_error"}, 500
        return (
            render_template(
                "errors/offline.html",
                title="Erro no servidor",
                message="Algo falhou ao carregar esta página. O servidor continua ativo — tente atualizar.",
                show_restart_hint=True,
            ),
            500,
        )

    try:
        from sqlalchemy.exc import OperationalError

        @app.errorhandler(OperationalError)
        def _db_busy(exc):
            app.logger.warning("SQLite ocupado: %s", exc)
            db.session.rollback()
            return (
                render_template(
                    "errors/offline.html",
                    title="Base de dados ocupada",
                    message="O ficheiro da base está em uso (comum com OneDrive). Aguarde 2 segundos e atualize a página.",
                    show_restart_hint=True,
                ),
                503,
            )
    except ImportError:
        pass

    prefix = (app.config.get("URL_PREFIX") or "").strip()
    if prefix:
        # Só o PrefixMiddleware ajusta SCRIPT_NAME/PATH_INFO. Não defina APPLICATION_ROOT
        # com o mesmo prefixo: o Flask somaria os dois e url_for geraria /prefix/prefix/...
        app.config["SESSION_COOKIE_PATH"] = prefix + "/"
        from app.prefix_middleware import PrefixMiddleware

        app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix)

    _initialize_database(app)

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.argument("password")
    @click.option("--full-name", default="Diretoria do Clube", show_default=True)
    def create_admin_command(email, password, full_name):
        """Cria ou promove conta de diretoria (use no Render após o primeiro deploy)."""
        configured = _upsert_director_admin(email, password, full_name)
        click.echo(f"Conta de diretoria configurada: {configured}")

    @app.cli.command("create-master-admin")
    @click.argument("email")
    @click.argument("password")
    @click.option("--full-name", default="Admin Mestre", show_default=True)
    def create_master_admin_command(email, password, full_name):
        """Cria ou promove conta de admin mestre global."""
        from app.models import CARGO_SUPER_ADMIN, Profile, User

        email = email.strip().lower()
        u = User.query.filter_by(email=email).first()
        if u:
            u.role = "admin"
            u.email_verified = True
            u.full_name = full_name.strip() or u.full_name
            u.set_password(password)
        else:
            u = User(
                email=email,
                role="admin",
                full_name=full_name.strip() or "Admin Mestre",
                email_verified=True,
            )
            u.set_password(password)
            db.session.add(u)
            db.session.flush()
        profile = db.session.get(Profile, u.id) if u.id else None
        if not profile:
            profile = Profile(id=u.id)
            db.session.add(profile)
        profile.cargo = CARGO_SUPER_ADMIN
        profile.cargos_json = json.dumps([CARGO_SUPER_ADMIN])
        profile.nome_completo = full_name.strip() or u.full_name
        profile.email_verificado = True
        profile.clube_id = None
        db.session.commit()
        click.echo(f"Conta admin mestre configurada: {email}")

    return app


def _ensure_master_admin(app):
    """Garante admin mestre e remove admin legado por clube."""
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    if "sqlite" not in uri:
        return

    from app.models import CARGO_PAI, CARGO_SUPER_ADMIN, Profile, User

    master_email = (
        os.environ.get("MASTER_ADMIN_EMAIL", "").strip().lower() or "admin.mestre@clube.com"
    )
    master_password = os.environ.get("MASTER_ADMIN_PASSWORD", "").strip() or "Mestre@123"

    master = User.query.filter_by(email=master_email).first()
    if master:
        master.role = "admin"
        master.full_name = master.full_name or "Admin Mestre"
        master.email_verified = True
        master.set_password(master_password)
    else:
        master = User(
            email=master_email,
            role="admin",
            full_name="Admin Mestre",
            email_verified=True,
        )
        master.set_password(master_password)
        db.session.add(master)
        db.session.flush()

    profile = db.session.get(Profile, master.id)
    if profile is None:
        profile = Profile(id=master.id, email_verificado=True)
        db.session.add(profile)
    profile.cargo = CARGO_SUPER_ADMIN
    profile.cargos_json = json.dumps([CARGO_SUPER_ADMIN])
    profile.email_verificado = True
    profile.clube_id = None
    if not profile.nome_completo:
        profile.nome_completo = master.full_name

    legacy_email = "admin@clube.com"
    legacy = User.query.filter_by(email=legacy_email).first()
    if legacy and legacy.id != master.id:
        legacy_profile = db.session.get(Profile, legacy.id)
        # Remove o "admin padrão do clube" e transforma em conta comum.
        legacy.role = "parent"
        legacy.full_name = legacy.full_name or "Usuário legado"
        legacy.set_password(os.environ.get("LEGACY_ADMIN_DISABLED_PASSWORD", "desativado123"))
        if legacy_profile is None:
            legacy_profile = Profile(id=legacy.id)
            db.session.add(legacy_profile)
        legacy_profile.cargo = CARGO_PAI
        legacy_profile.cargos_json = json.dumps([CARGO_PAI])
        legacy_profile.email_verificado = True
    db.session.commit()
