from __future__ import annotations

from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user

from app.models import (
    CARGO_CONSELHEIRO,
    CARGO_DIRETOR,
    CARGO_PAI,
    CARGO_SECRETARIO,
    CARGO_SUPER_ADMIN,
    CARGO_TESOUREIRO,
)


def _normalize_cargo_token(value: str | None) -> str:
    s = (value or "").strip().lower()
    aliases = {
        "diretor(a)": CARGO_DIRETOR,
        "diretora": CARGO_DIRETOR,
        "tesouraria": CARGO_TESOUREIRO,
        "tesoureiro(a)": CARGO_TESOUREIRO,
        "secretaria": CARGO_SECRETARIO,
        "secretário": CARGO_SECRETARIO,
        "secretaria(a)": CARGO_SECRETARIO,
        "conselheiros": CARGO_CONSELHEIRO,
        "conselheiro(a)": CARGO_CONSELHEIRO,
        "responsavel": CARGO_PAI,
        "responsável": CARGO_PAI,
    }
    if s in aliases:
        return aliases[s]
    return s


def current_profile():
    if not current_user.is_authenticated:
        return None
    return getattr(current_user, "perfil", None)


def current_cargo() -> str | None:
    p = current_profile()
    if not p:
        return None
    normalized = _normalize_cargo_token(getattr(p, "cargo", None))
    return normalized or None


def cargos_for_profile(profile) -> set[str]:
    """Cargos normalizados a partir de um `Profile` (sessão atual ou outro usuário)."""
    if not profile:
        return set()
    raw = getattr(profile, "cargos_json", None)
    if raw:
        try:
            import json

            data = json.loads(raw)
            if isinstance(data, list):
                return {
                    _normalize_cargo_token(str(x))
                    for x in data
                    if _normalize_cargo_token(str(x))
                }
        except Exception:
            pass
    one = _normalize_cargo_token(getattr(profile, "cargo", None))
    return {one} if one else set()


def current_cargos() -> set[str]:
    """Conjunto de cargos do usuário (suporta múltiplas funções no mesmo perfil)."""
    return cargos_for_profile(current_profile())


def current_clube_id() -> str | None:
    p = current_profile()
    return p.clube_id if p else None


def is_super_admin() -> bool:
    return CARGO_SUPER_ADMIN in current_cargos()


_LEADERSHIP_CARGOS = frozenset(
    {
        CARGO_SUPER_ADMIN,
        CARGO_DIRETOR,
    }
)


def user_has_leadership_portal_access() -> bool:
    """True se o usuário deve usar os painéis de liderança (admin/clube), não o portal só de responsável."""
    if not current_user.is_authenticated:
        return False
    if getattr(current_user, "is_admin", None) and current_user.is_admin():
        return True
    return bool(current_cargos() & _LEADERSHIP_CARGOS)


# Valores quando não há usuário ou em fallback de template (base_admin.html).
ADMIN_PANEL_DEFAULTS: dict[str, bool] = {
    "show_finance_nav": False,
    "can_view_finance": False,
    "can_write_finance": False,
    "can_manage_directorate_ui": False,
    "can_delegate_roles": False,
    "can_write_agenda": False,
    "can_manage_member_links": False,
    "can_add_members": False,
    "can_delete_members": False,
    "can_delete_parent_accounts": False,
}


def get_admin_panel_permissions() -> dict[str, bool]:
    """Flags para menu e botões do /admin (base_admin e filhos)."""
    if not current_user.is_authenticated:
        return dict(ADMIN_PANEL_DEFAULTS)
    c = current_cargos()
    is_admin_account = bool(getattr(current_user, "is_admin", None) and current_user.is_admin())
    # Fallback: se a conta é admin mas o perfil/cargos ainda não carregou,
    # manter permissões de diretoria para não esconder funcionalidades críticas.
    if not c and getattr(current_user, "is_admin", None) and current_user.is_admin():
        return {
            "show_finance_nav": True,
            "can_view_finance": True,
            "can_write_finance": True,
            "can_manage_directorate_ui": True,
            "can_delegate_roles": True,
            "can_write_agenda": True,
            "can_manage_member_links": True,
            "can_add_members": True,
            "can_delete_members": True,
            "can_delete_parent_accounts": True,
        }
    su = CARGO_SUPER_ADMIN in c
    dr = CARGO_DIRETOR in c or is_admin_account

    # Regras por cargo:
    # - Conselheiro: sem exclusões de desbravador, sem gestão de diretoria, sem criar agenda, sem financeiro e sem gestão de vínculos.
    # - Tesoureiro: igual conselheiro, porém com financeiro liberado (view + escrita/ações).
    # - Secretaria: sem financeiro e sem gestão da diretoria, mas com o restante (cadastros/links/agenda) como diretoria.
    te = CARGO_TESOUREIRO in c
    se = CARGO_SECRETARIO in c
    co = CARGO_CONSELHEIRO in c

    full = su or dr or is_admin_account  # compatibilidade com contas admin legadas

    can_finance = su or dr or te
    can_manage_directorate = su or dr
    can_delegate_roles = su or dr
    can_write_agenda = su or dr or se
    can_manage_member_links = su or dr or se

    can_add_members = su or dr or se
    can_delete_members = su or dr or se
    can_delete_parent_accounts = su or dr or se

    return {
        # Financeiro
        "show_finance_nav": can_finance,
        "can_view_finance": can_finance,
        "can_write_finance": can_finance,

        # Diretoria
        "can_manage_directorate_ui": can_manage_directorate,
        "can_delegate_roles": can_delegate_roles,

        # Operações gerais
        "can_write_agenda": can_write_agenda,
        "can_manage_member_links": can_manage_member_links,

        "can_add_members": can_add_members,
        "can_delete_members": can_delete_members,
        "can_delete_parent_accounts": can_delete_parent_accounts,
    }


def render_admin_shell(template_name: str, **context):
    """Mesmo contexto de permissões do painel para qualquer template que estende admin/base_admin.html."""
    from flask import render_template

    ctx = dict(context)
    if "admin_panel" not in ctx:
        try:
            ctx["admin_panel"] = get_admin_panel_permissions()
        except Exception:
            ctx["admin_panel"] = dict(ADMIN_PANEL_DEFAULTS)
    return render_template(template_name, **ctx)


def club_leadership_nav_visibility() -> dict[str, bool]:
    """Abas do shell escuro /clube/* — cada cargo vê só o que pode acessar."""
    from flask_login import current_user

    if not getattr(current_user, "is_authenticated", False):
        return {
            "nav_director": False,
            "nav_tesouraria": False,
            "nav_secretaria": False,
            "nav_conselheiros": False,
        }
    c = current_cargos()
    su = CARGO_SUPER_ADMIN in c
    dr = CARGO_DIRETOR in c
    te = CARGO_TESOUREIRO in c
    se = CARGO_SECRETARIO in c
    co = CARGO_CONSELHEIRO in c
    # Diretor(a) e super admin enxergam todos os atalhos de liderança.
    return {
        "nav_director": su or dr,
        "nav_tesouraria": su or dr or te,
        "nav_secretaria": su or dr or se,
        "nav_conselheiros": su or dr or co,
    }


def can_access_clube(clube_id: str | None) -> bool:
    if is_super_admin():
        return True
    if not clube_id:
        return False
    return current_clube_id() == clube_id


def role_required(*allowed_roles: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            cargos = current_cargos()
            if not cargos.intersection(set(allowed_roles)):
                flash("Você não tem permissão para acessar esta área.", "warning")
                return redirect(url_for("auth.unauthorized"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def clube_access_required(clube_id_kw: str = "clube_id"):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            clube_id = kwargs.get(clube_id_kw)
            if not can_access_clube(clube_id):
                flash("Você não tem acesso a este clube.", "warning")
                return redirect(url_for("auth.unauthorized"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def route_for_user(user) -> str:
    perfil = getattr(user, "perfil", None)
    cargos = set()
    if perfil:
        raw = getattr(perfil, "cargos_json", None)
        if raw:
            try:
                import json

                data = json.loads(raw)
                if isinstance(data, list):
                    cargos = {
                        t
                        for x in data
                        if (t := _normalize_cargo_token(str(x)))
                    }
            except Exception:
                cargos = set()
        if not cargos and getattr(perfil, "cargo", None):
            cargos = {_normalize_cargo_token(perfil.cargo)}
    if not cargos:
        cargos = {CARGO_DIRETOR} if user.is_admin() else {CARGO_PAI}
    clube_id = perfil.clube_id if perfil else None

    if CARGO_SUPER_ADMIN in cargos:
        return url_for("super_admin.dashboard")
    leadership_roles = {
        CARGO_DIRETOR,
        CARGO_SECRETARIO,
        CARGO_TESOUREIRO,
        CARGO_CONSELHEIRO,
    }
    if user.is_admin() or cargos.intersection(leadership_roles):
        return url_for("admin.dashboard")
    if cargos and CARGO_PAI not in cargos:
        return url_for("auth.unauthorized")
    return url_for("parent.home")


def admin_area_required(fn):
    """Permite acesso ao painel admin para super admin e diretor."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        cargos = current_cargos()
        if not cargos.intersection({CARGO_SUPER_ADMIN, CARGO_DIRETOR}):
            flash("Esta área é só para a diretoria.", "warning")
            return redirect(route_for_user(current_user))
        return fn(*args, **kwargs)

    return wrapper


def parent_area_required(fn):
    """Permite acesso ao painel dos responsáveis (pais)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Faça login como responsável.", "danger")
            return redirect(url_for("auth.login"))
        if user_has_leadership_portal_access():
            return redirect(route_for_user(current_user))
        if current_user.is_admin():
            return redirect(route_for_user(current_user))
        cargos = current_cargos()
        if cargos and CARGO_PAI not in cargos:
            return redirect(route_for_user(current_user))
        return fn(*args, **kwargs)

    return wrapper
