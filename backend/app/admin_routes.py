import json
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, request, send_file, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import false, func, or_, text
from sqlalchemy.exc import IntegrityError

from app.agenda_calendar_util import (
    MONTH_NAMES_PT,
    agenda_add_months,
    agenda_clamp_day_in_month,
    agenda_month_bounds,
    agenda_resolve_selected_day,
    agenda_sort_day_events,
    agenda_weeks,
)
from app.access import (
    current_cargos,
    current_clube_id,
    get_admin_panel_permissions,
    is_super_admin,
    render_admin_shell,
    route_for_user,
)
from app.club_services import (
    director_dashboard_stats,
    finance_ledger_query,
    get_pix_for_club,
    set_pix_for_club,
)
from app.email_util import send_simple_email
from app.extensions import db
from app.finance_util import format_brl_cents, parse_money_brl
from app.member_profile import build_member_profile_context
from app.member_parent_link import (
    change_member_link_type,
    children_for_parent as _children_for_parent,
    delete_parent_account,
    find_parent_user_for_link,
    is_registered_parent_account,
    link_member_to_parent,
    link_summary_message,
    normalize_link_type,
    transfer_member_to_parent,
    unlink_member_from_parent,
)
from app.parents_service import (
    link_history_for_club,
    parents_metrics,
    search_parents,
    search_unlinked_members,
    serialize_member_card,
    serialize_parent_row,
    suggest_parents_for_member,
)
from app.leadership_service import (
    LEADERSHIP_ROLE_SLOTS,
    PERMISSION_LABELS,
    ROLE_LABELS,
    apply_directorate_from_form,
    audit_log_for_club,
    delegation_history_for_member,
    filter_team_rows,
    get_role_permissions,
    log_leadership_action,
    leadership_metrics,
    paginate_rows,
    recent_registrations,
    save_role_permissions,
    search_users_for_delegation,
    serialize_directorate_member,
    serialize_member_detail,
    validate_role_assignment,
)
from app.agenda_service import (
    EVENT_CATEGORIES,
    EVENT_CHECKLISTS,
    EVENT_COLOR_PALETTE,
    EVENT_STATUSES,
    EVENT_TEMPLATES,
    EVENT_TYPE_CARDS,
    apply_agenda_form,
    batch_confirmed_counts,
    featured_upcoming,
    month_stats,
    reminder_for_events,
    serialize_event,
    timeline_events,
)
from app.member_wizard import CLUB_UNIT_OPTIONS, unit_options_for_club
from app.models import (
    ActivityRecord,
    AgendaEvent,
    Attendance,
    BoardPost,
    DirectorateMember,
    LeadershipDelegation,
    FEE_CATEGORIES,
    FEE_STATUS_CANCELADO,
    FinanceAuditLog,
    FinanceLedgerEntry,
    MeetingDuque,
    Member,
    MemberFee,
    PaymentProof,
    PROOF_STATUS_APPROVED,
    PROOF_STATUS_PENDING,
    PROOF_STATUS_REJECTED,
    PROOF_STATUS_REVISION,
    PasswordResetToken,
    PARENT_LINK_TYPES,
    Profile,
    User,
    CARGO_CONSELHEIRO,
    CARGO_DIRETOR,
    CARGO_PAI,
    CARGO_SECRETARIO,
    CARGO_SUPER_ADMIN,
    CARGO_TESOUREIRO,
    Club,
    POST_KIND_COMUNICADO,
    POST_KIND_NOTICIA,
    WarehouseCategory,
    WarehouseItem,
    WarehouseMovement,
    WH_MOVEMENT_IN,
    WH_MOVEMENT_OUT,
    MemberSpecialtyProgress,
    Specialty,
)
from app.finance_service import (
    CATEGORY_LABELS,
    build_finance_dashboard,
    credit_fee_to_ledger,
    generate_fees_bulk,
    log_finance_action,
)
from app.warehouse_service import (
    apply_item_form,
    build_warehouse_dashboard,
    delete_movement,
    ensure_default_categories,
    record_movement,
)
from app.specialties_service import (
    apply_specialty_form,
    apply_specialty_icon_upload,
    approve_enrollment,
    build_admin_dashboard,
    delete_catalog_specialty,
    delete_member_enrollment,
    enroll_member,
    ensure_default_specialties,
    member_progress_summary,
    save_requirements_from_form,
    toggle_requirement,
)
from app.gallery_service import (
    album_photos_for_lightbox,
    build_gallery_page,
    create_album,
    ensure_demo_gallery,
    get_album_for_club,
    get_photo_for_club,
    move_photo_to_album,
    serialize_album,
    serialize_photo,
    set_album_cover,
    set_featured_album,
    trash_album,
    trash_photo,
    trashed_items,
    update_album,
    update_photo,
    upload_photos,
)
from app.uploads_util import save_document_upload, save_upload
from app.activities_service import (
    build_activities_dashboard,
    build_class_requirements_for_homework,
    build_member_notebook_detail,
    create_homework,
    ensure_member_notebook,
    review_homework_submission,
    set_requirement_status,
)
from app.admin_portal import (
    admin_dashboard_portal,
    admin_time_greeting,
)
from app.units_service import (
    assign_member_to_unit,
    create_unit,
    create_unit_role,
    delete_unit,
    delete_unit_role,
    get_unit_for_club,
    remove_member_from_unit,
    unit_detail_payload,
    units_dashboard_payload,
    update_member_unit_role,
    update_unit,
    update_unit_role,
)
from app.models import ClubUnit, ClubUnitRole, UNIT_STATUS_OPTIONS, UNIT_THEME_COLORS

bp = Blueprint("admin", __name__)


def _safe_admin_url(endpoint: str, **values) -> str:
    try:
        return url_for(endpoint, **values)
    except Exception:
        return url_for("admin.dashboard")


# Fallbacks se url_for falhar ou contexto ainda não estiver montado
ADMIN_NAV_DEFAULTS: dict[str, str] = {
    "dashboard": "/admin/",
    "members": "/admin/membros",
    "units": "/admin/unidades",
    "events": "/admin/agenda",
    "activities": "/admin/atividades",
    "specialties": "/admin/especialidades",
    "communications": "/admin/publicacoes",
    "finance": "/admin/financeiro",
    "warehouse": "/admin/almoxarifado",
    "gallery": "/admin/galeria",
    "settings": "/admin/configuracoes",
    "parents": "/admin/responsaveis",
    "attendance": "/admin/presencas",
    "directorate": "/admin/diretoria",
}


def _build_admin_nav(kw: dict | None = None) -> dict[str, str]:
    kw = kw or {}
    return {
        "dashboard": _safe_admin_url("admin.dashboard", **kw),
        "members": _safe_admin_url("admin.members", **kw),
        "units": _safe_admin_url("admin.admin_units", **kw),
        "events": _safe_admin_url("admin.agenda_list", **kw),
        "activities": _safe_admin_url("admin.admin_activities", **kw),
        "specialties": _safe_admin_url("admin.admin_specialties", **kw),
        "communications": _safe_admin_url("admin.posts", **kw),
        "finance": _safe_admin_url("admin.finance_dashboard", **kw),
        "warehouse": _safe_admin_url("admin.admin_warehouse", **kw),
        "gallery": _safe_admin_url("admin.admin_gallery", **kw),
        "settings": _safe_admin_url("admin.admin_settings", **kw),
        "parents": _safe_admin_url("admin.parents_list", **kw),
        "attendance": _safe_admin_url("admin.attendance_overview", **kw),
        "directorate": _safe_admin_url("admin.directorate_list", **kw),
    }


def get_admin_template_context() -> dict:
    """Contexto de shell da diretoria — sempre inclui admin_nav."""
    from app.admin_nav import desbravadores_nav_context

    try:
        panel = get_admin_panel_permissions()
    except Exception:
        from app.access import ADMIN_PANEL_DEFAULTS

        panel = dict(ADMIN_PANEL_DEFAULTS)

    first = "Direção"
    try:
        if getattr(current_user, "is_authenticated", False):
            first = (current_user.full_name or current_user.email or "Direção").split()[0]
    except Exception:
        pass

    ep = ""
    try:
        ep = request.endpoint or ""
    except Exception:
        pass

    kw: dict = {}
    nav_kw: dict = {}
    try:
        cid = resolve_admin_clube_id()
        if cid:
            kw["clube_id"] = cid
            nav_kw["clube_id"] = cid
    except Exception:
        pass

    try:
        nav = _build_admin_nav(kw)
    except Exception:
        nav = dict(ADMIN_NAV_DEFAULTS)

    return {
        "admin_greeting": admin_time_greeting(),
        "admin_first_name": first,
        "admin_nav": nav,
        "admin_nav_kw": nav_kw,
        "admin_panel": panel,
        **desbravadores_nav_context(ep),
    }


@bp.context_processor
def inject_admin_portal():
    ep = ""
    try:
        ep = request.endpoint or ""
    except Exception:
        pass
    if not ep.startswith("admin."):
        return {
            "admin_greeting": admin_time_greeting(),
            "admin_first_name": "Direção",
            "admin_nav": dict(ADMIN_NAV_DEFAULTS),
        }
    return get_admin_template_context()

# Cadernos de atividades (classes regulares dos Desbravadores — apenas estas opções na ficha)
NOTEBOOK_ACTIVITY_OPTIONS = (
    "Amigo",
    "Companheiro",
    "Pesquisador",
    "Pioneiro",
    "Excursionista",
    "Guia",
    "Clube de líderes",
)

NEWS_LEVELS = [
    ("local", "Clube (local)"),
    ("regional", "Associação (regional)"),
    ("estadual", "União (estadual)"),
    ("mundial", "Divisão mundial"),
]


def _safe_remove_upload(rel_path: str | None) -> None:
    if not rel_path:
        return
    p = Path(current_app.config["UPLOAD_FOLDER"]) / rel_path
    if p.is_file():
        p.unlink()


def _process_member_photo(member: Member) -> None:
    if request.form.get("remove_photo") == "1":
        _safe_remove_upload(member.photo_filename)
        member.photo_filename = None
        return
    f = request.files.get("photo")
    saved = save_upload(f, current_app.config["UPLOAD_FOLDER"], "members")
    if saved:
        _safe_remove_upload(member.photo_filename)
        member.photo_filename = saved


def parent_users_query():
    """Contas criadas pelo cadastro do site (role parent) no clube atual."""
    club_id = _read_scope_clube_id()
    q = (
        db.session.query(User)
        .join(Profile, Profile.id == User.id)
        .filter(User.role == "parent")
    )
    if club_id:
        q = q.filter(Profile.clube_id == club_id)
    elif is_super_admin():
        q = q.filter(false())
    else:
        q = q.filter(false())
    return q.order_by(User.full_name.asc(), User.created_at.desc()).all()


def _unlinked_members_for_club():
    return (
        _members_scoped_query()
        .filter(Member.parent_id.is_(None))
        .order_by(Member.full_name)
        .all()
    )


def _admin_scope_clube_id() -> str | None:
    if is_super_admin():
        return None
    return current_clube_id()


def resolve_admin_clube_id() -> str | None:
    """
    Clube ativo no painel admin.
    Super admin: query/form → sessão → único clube no sistema (se houver só um).
    Diretoria: clube do perfil.
    """
    if not is_super_admin():
        return current_clube_id()
    cid = (request.args.get("clube_id") or request.form.get("clube_id") or "").strip()
    if cid:
        session["admin_scope_clube_id"] = cid
        return cid
    stored = (session.get("admin_scope_clube_id") or "").strip()
    if stored:
        return stored
    clubs = Club.query.order_by(Club.nome.asc()).all()
    if len(clubs) == 1:
        session["admin_scope_clube_id"] = clubs[0].id
        return clubs[0].id
    return None


def _read_scope_clube_id() -> str | None:
    """Escopo de leitura/listagens no painel admin."""
    return resolve_admin_clube_id()


def _write_clube_id_for_admin() -> str | None:
    """Clube usado em criações (membros, agenda, etc.). Super admin: mesmo escopo que leitura."""
    if not is_super_admin():
        return current_clube_id()
    return resolve_admin_clube_id()


def _members_scoped_query():
    cid = _read_scope_clube_id()
    q = Member.query
    if cid:
        return q.filter(Member.clube_id == cid)
    if is_super_admin():
        return q.filter(false())
    return q.filter(false())


def _agenda_scoped_query():
    cid = _read_scope_clube_id()
    q = AgendaEvent.query
    if cid:
        return q.filter(AgendaEvent.clube_id == cid)
    if is_super_admin():
        return q.filter(false())
    return q.filter(false())


def _board_scoped_query():
    cid = _read_scope_clube_id()
    q = BoardPost.query
    if cid:
        return q.filter(BoardPost.clube_id == cid)
    if is_super_admin():
        return q.filter(false())
    return q.filter(false())


def _directorate_scoped_query():
    cid = _read_scope_clube_id()
    q = DirectorateMember.query
    if cid:
        return q.filter(DirectorateMember.clube_id == cid)
    if is_super_admin():
        return q.filter(false())
    return q.filter(false())


def _member_fees_scoped_query():
    cid = _read_scope_clube_id()
    q = MemberFee.query.join(Member, Member.id == MemberFee.member_id)
    if cid:
        return q.filter(Member.clube_id == cid)
    if is_super_admin():
        return q.filter(false())
    return q.filter(false())


def _member_for_admin(member_id: int) -> Member:
    m = db.session.get(Member, member_id)
    if not m:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or m.clube_id != cid:
            abort(404)
        return m
    if not cid or m.clube_id != cid:
        abort(404)
    return m


def _agenda_event_for_admin(eid: int) -> AgendaEvent:
    ev = db.session.get(AgendaEvent, eid)
    if not ev:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or ev.clube_id != cid:
            abort(404)
        return ev
    if not cid or ev.clube_id != cid:
        abort(404)
    return ev


def _board_post_for_admin(pid: int) -> BoardPost:
    p = db.session.get(BoardPost, pid)
    if not p:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or p.clube_id != cid:
            abort(404)
        return p
    if not cid or p.clube_id != cid:
        abort(404)
    return p


def _finance_ledger_for_admin(lid: int) -> FinanceLedgerEntry:
    row = db.session.get(FinanceLedgerEntry, lid)
    if not row:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or row.clube_id != cid:
            abort(404)
        return row
    if not cid or row.clube_id != cid:
        abort(404)
    return row


def _warehouse_item_for_admin(iid: int) -> WarehouseItem:
    item = db.session.get(WarehouseItem, iid)
    if not item:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or item.clube_id != cid:
            abort(404)
        return item
    if not cid or item.clube_id != cid:
        abort(404)
    return item


def _warehouse_category_for_admin(cid_cat: int) -> WarehouseCategory:
    cat = db.session.get(WarehouseCategory, cid_cat)
    if not cat:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or cat.clube_id != cid:
            abort(404)
        return cat
    if not cid or cat.clube_id != cid:
        abort(404)
    return cat


def _warehouse_movement_for_admin(mid: int) -> WarehouseMovement:
    mv = db.session.get(WarehouseMovement, mid)
    if not mv:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or mv.clube_id != cid:
            abort(404)
        return mv
    if not cid or mv.clube_id != cid:
        abort(404)
    return mv


def _directorate_member_for_admin(did: int) -> DirectorateMember:
    d = db.session.get(DirectorateMember, did)
    if not d:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or getattr(d, "clube_id", None) != cid:
            abort(404)
        return d
    if not cid or getattr(d, "clube_id", None) != cid:
        abort(404)
    return d


def _scope_kw_for_redirect(clube_id: str | None = None) -> dict:
    """Preserva ?clube_id= nos redirects quando super admin opera um clube."""
    if not is_super_admin():
        return {}
    cid = (
        clube_id
        or request.args.get("clube_id")
        or request.form.get("clube_id")
        or session.get("admin_scope_clube_id")
        or ""
    )
    cid = (cid or "").strip() if isinstance(cid, str) else ""
    if not cid:
        cid = resolve_admin_clube_id() or ""
    return {"clube_id": cid} if cid else {}


def _member_fee_for_admin(fid: int) -> MemberFee:
    fee = db.session.get(MemberFee, fid)
    if not fee:
        abort(404)
    m = db.session.get(Member, fee.member_id)
    if not m:
        abort(404)
    cid = _read_scope_clube_id()
    if is_super_admin():
        if not cid or m.clube_id != cid:
            abort(404)
        return fee
    if not cid or m.clube_id != cid:
        abort(404)
    return fee


def _link_leadership_account(account_email: str, full_name: str, perfil_cargo: str) -> str | None:
    """
    Vincula e-mail + cargo ao clube do diretor (perfil). Cria usuário se não existir e envia
    link de definição de senha quando o SMTP estiver configurado.
    Retorna mensagem de erro ou None em caso de sucesso.
    """
    email = (account_email or "").strip().lower()
    if not email:
        return None
    allowed = {CARGO_TESOUREIRO, CARGO_SECRETARIO, CARGO_CONSELHEIRO}
    if is_super_admin():
        allowed.add(CARGO_DIRETOR)
    if perfil_cargo not in allowed:
        if perfil_cargo == CARGO_DIRETOR:
            return "Apenas o administrador mestre pode promover usuários ao cargo de diretor no portal."
        return "Selecione a função no sistema (tesoureiro, secretário ou conselheiro)."
    scope_club_id = _write_clube_id_for_admin()
    if not scope_club_id:
        return "Seu usuário precisa estar vinculado a um clube para liberar acessos da liderança (super admin: informe clube_id no formulário ou ?clube_id=)."
    club = db.session.get(Club, scope_club_id)
    if not club:
        return "Clube não encontrado."

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            role="admin",
            full_name=(full_name or email).strip() or email,
            email_verified=True,
        )
        user.set_password(secrets.token_urlsafe(24))
        db.session.add(user)
        db.session.flush()
        token = secrets.token_urlsafe(32)
        row = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=72),
        )
        db.session.add(row)
        reset_url = url_for("auth.reset_password", token=token, _external=True)
        body = (
            f"Olá!\n\nVocê foi cadastrado(a) na liderança do clube {club.nome}.\n"
            f"Para definir sua senha e acessar o portal, use este link (válido por 72 horas):\n{reset_url}\n\n"
            "Após definir a senha, faça login com seu e-mail.\n"
        )
        sent = send_simple_email(
            user.email, f"Acesso à liderança — {club.nome}", body
        )
        if not sent and current_app.debug:
            flash(
                f"Desenvolvimento: link para definir senha do novo líder — {reset_url}",
                "info",
            )

    profile = db.session.get(Profile, user.id)
    if not profile:
        profile = Profile(id=user.id)
        db.session.add(profile)
    if profile.clube_id and profile.clube_id != scope_club_id and not is_super_admin():
        return "Este e-mail já está vinculado a um clube e não pode ser movido por este painel."
    from app.access import cargos_for_profile
    from app.member_parent_link import parent_has_children

    profile.clube_id = scope_club_id
    roles = cargos_for_profile(profile)
    roles.add(perfil_cargo)
    if parent_has_children(user):
        roles.add(CARGO_PAI)
    profile.cargo = perfil_cargo
    profile.cargos_json = json.dumps(sorted(roles))
    profile.nome_completo = (full_name or "").strip() or profile.nome_completo or user.full_name
    profile.email_verificado = bool(user.email_verified)
    leadership_roles = {CARGO_DIRETOR, CARGO_SECRETARIO, CARGO_TESOUREIRO, CARGO_CONSELHEIRO}
    user.role = "admin" if roles.intersection(leadership_roles) else "parent"
    if full_name and full_name.strip():
        user.full_name = full_name.strip()
    return None


def _user_profile_if_in_scope(user_id: int) -> tuple[User | None, Profile | None]:
    user = db.session.get(User, user_id)
    if not user:
        return None, None
    profile = db.session.get(Profile, user_id)
    if not profile:
        return user, None
    club_id = _read_scope_clube_id()
    if is_super_admin():
        if not club_id or profile.clube_id != club_id:
            return None, None
        return user, profile
    if not club_id or profile.clube_id != club_id:
        return None, None
    return user, profile


def normalize_cpf_digits(value: str | None) -> str | None:
    if not value:
        return None
    d = "".join(c for c in value if c.isdigit())
    if len(d) != 11:
        return None
    return d


def format_cpf_display(digits: str) -> str:
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def parse_notebook_checklist_from_form(form) -> list[bool]:
    return [form.get(f"nb_{i}") == "1" for i in range(1, 31)]


def _emergency_phone_ok(phone: str) -> bool:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return len(digits) >= 10


def apply_member_form(m: Member, form, member_id_exclude=None):
    name = (form.get("full_name") or "").strip()
    if not name:
        raise ValueError("Nome completo é obrigatório.")
    m.full_name = name

    unit = (form.get("unit") or "").strip()
    if not unit:
        raise ValueError(
            "Unidade é obrigatória — informe o nome da unidade (ex.: Amigo, Companheiro, nome do clube, etc.)."
        )
    m.unit = unit

    bd_raw = (form.get("birth_date") or "").strip()
    if not bd_raw:
        raise ValueError("Data de nascimento é obrigatória.")
    try:
        m.birth_date = date.fromisoformat(bd_raw)
    except ValueError:
        raise ValueError("Data de nascimento inválida.")

    cpf_field = (form.get("cpf") or "").strip()
    if not cpf_field:
        m.cpf = None
    else:
        cpf_raw = normalize_cpf_digits(cpf_field)
        if not cpf_raw:
            raise ValueError("CPF inválido. Informe 11 dígitos.")
        q = Member.query.filter(Member.cpf == cpf_raw)
        if getattr(m, "clube_id", None):
            q = q.filter(Member.clube_id == m.clube_id)
        if member_id_exclude:
            q = q.filter(Member.id != member_id_exclude)
        if q.first():
            raise ValueError("CPF já cadastrado para outro membro.")
        m.cpf = cpf_raw

    blood = (form.get("blood_type") or "").strip()
    if not blood:
        raise ValueError("Tipo sanguíneo é obrigatório.")
    m.blood_type = blood

    father = (form.get("father_name") or "").strip()
    mother = (form.get("mother_name") or "").strip()
    if not father:
        raise ValueError("Nome do pai ou responsável é obrigatório.")
    if not mother:
        raise ValueError("Nome da mãe ou responsável é obrigatório.")
    m.father_name = father
    m.mother_name = mother

    em_name = (form.get("emergency_contact_name") or "").strip()
    em_phone = (form.get("emergency_contact_phone") or "").strip()
    if not em_name:
        raise ValueError("Contato de emergência — nome é obrigatório.")
    if not em_phone:
        raise ValueError("Contato de emergência — telefone é obrigatório.")
    if not _emergency_phone_ok(em_phone):
        raise ValueError("Telefone de emergência deve ter pelo menos 10 dígitos.")
    m.emergency_contact_name = em_name
    m.emergency_contact_phone = em_phone

    allowed_notebooks = set(NOTEBOOK_ACTIVITY_OPTIONS)
    if member_id_exclude:
        existing = db.session.get(Member, member_id_exclude)
        if existing and existing.notebook_current:
            allowed_notebooks.add(existing.notebook_current.strip())
    nb = (form.get("notebook_current") or "").strip()
    if not nb or nb not in allowed_notebooks:
        raise ValueError(
            "Selecione o caderno de atividades: Amigo, Companheiro, Pesquisador, Pioneiro, Excursionista, Guia ou Clube de líderes."
        )
    m.notebook_current = nb
    m.overall_performance = m.computed_overall_performance()


def _can_assign_directorate_and_delegate():
    if is_super_admin() or CARGO_DIRETOR in current_cargos():
        return True
    # Fallback para contas admin legadas com perfil inconsistênte no banco.
    return bool(getattr(current_user, "is_admin", None) and current_user.is_admin())


def _assignable_leadership_roles():
    """Cargos delegáveis pelo usuário atual. Diretor geral só pelo super admin."""
    roles = [
        (CARGO_CONSELHEIRO, ROLE_LABELS[CARGO_CONSELHEIRO]),
        (CARGO_SECRETARIO, ROLE_LABELS[CARGO_SECRETARIO]),
        (CARGO_TESOUREIRO, ROLE_LABELS[CARGO_TESOUREIRO]),
    ]
    if is_super_admin():
        roles.insert(0, (CARGO_DIRETOR, ROLE_LABELS[CARGO_DIRETOR]))
    return roles


def _leadership_roles_for_directorate_form():
    """Funções do portal vinculáveis no cadastro da diretoria (diretor só para super admin)."""
    roles = [
        (CARGO_TESOUREIRO, "Tesoureiro(a) — finanças"),
        (CARGO_SECRETARIO, "Secretário(a) — secretaria"),
        (CARGO_CONSELHEIRO, "Conselheiro(a)"),
    ]
    if is_super_admin():
        roles.append((CARGO_DIRETOR, "Diretor(a)"))
    return tuple(roles)


def _role_assignment_denied_message(role_code: str) -> str | None:
    """Retorna mensagem de erro se o usuário atual não pode atribuir este cargo."""
    if role_code == CARGO_DIRETOR and not is_super_admin():
        return "Apenas o administrador mestre pode promover alguém ao cargo de diretor."
    if role_code not in LEADERSHIP_ROLE_SLOTS:
        return "Função inválida."
    return None


@bp.before_request
@login_required
def _admin_guard():
    cargos = current_cargos()
    allowed = {CARGO_SUPER_ADMIN, CARGO_DIRETOR, CARGO_TESOUREIRO, CARGO_SECRETARIO, CARGO_CONSELHEIRO}
    # Legado: contas "admin" sem cargos carregados (mantém acesso para não quebrar)
    if getattr(current_user, "is_admin", None) and current_user.is_admin():
        return None
    if cargos.intersection(allowed):
        return None
    flash("Esta área é só para liderança do clube.", "warning")
    return redirect(route_for_user(current_user))


@bp.route("/")
def dashboard():
    cid = _read_scope_clube_id()
    n_members = _members_scoped_query().count()
    pq = db.session.query(User).join(Profile, Profile.id == User.id).filter(User.role == "parent")
    if cid:
        pq = pq.filter(Profile.clube_id == cid)
    elif is_super_admin():
        pq = pq.filter(false())
    else:
        pq = pq.filter(false())
    n_parents = pq.count()
    n_dir = _directorate_scoped_query().count()
    n_publicacoes = _board_scoped_query().count()
    recent = (
        _board_scoped_query()
        .order_by(BoardPost.created_at.desc())
        .limit(3)
        .all()
    )
    unit_q = db.session.query(Member.unit, func.count(Member.id)).group_by(Member.unit)
    if cid:
        unit_q = unit_q.filter(Member.clube_id == cid)
    elif is_super_admin():
        unit_q = unit_q.filter(false())
    else:
        unit_q = unit_q.filter(false())
    unit_rows = unit_q.order_by(func.count(Member.id).desc()).all()
    unit_stats = []
    for u, cnt in unit_rows:
        label = u or "Sem unidade"
        unit_stats.append({"label": label, "count": cnt})
    max_u = max((s["count"] for s in unit_stats), default=1)
    directorate_preview = (
        _directorate_scoped_query()
        .order_by(DirectorateMember.display_order, DirectorateMember.full_name)
        .limit(12)
        .all()
    )
    if cid:
        total_in = (
            db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
            .filter(
                FinanceLedgerEntry.direction == "income",
                FinanceLedgerEntry.clube_id == cid,
            )
            .scalar()
            or 0
        )
        total_out = (
            db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
            .filter(
                FinanceLedgerEntry.direction == "expense",
                FinanceLedgerEntry.clube_id == cid,
            )
            .scalar()
            or 0
        )
        pending_fees = (
            db.session.query(func.coalesce(func.sum(MemberFee.amount_cents), 0))
            .join(Member, Member.id == MemberFee.member_id)
            .filter(MemberFee.paid_at.is_(None), Member.clube_id == cid)
            .scalar()
            or 0
        )
    else:
        total_in = total_out = pending_fees = 0
    recent_members = _members_scoped_query().order_by(Member.id.desc()).limit(8).all()
    if cid:
        dash = director_dashboard_stats(cid)
    else:
        dash = {
            "n_members": 0,
            "n_upcoming": 0,
            "n_posts": 0,
            "n_directorate": 0,
            "upcoming_events": [],
            "attendance_labels": [],
            "attendance_counts": [],
            "unit_labels": [],
            "unit_counts": [],
            "recent_members": [],
            "recent_activities": [],
        }
    portal = admin_dashboard_portal(
        cid,
        dash=dash,
        n_parents=n_parents,
        finance_pending_fees=int(pending_fees),
        recent_posts=recent,
    )
    return render_admin_shell(
        "admin/dashboard.html",
        n_members=n_members,
        n_parents=n_parents,
        n_dir=n_dir,
        n_publicacoes=n_publicacoes,
        recent_posts=recent,
        unit_stats=unit_stats,
        max_unit_count=max_u,
        directorate_preview=directorate_preview,
        finance_total_in=int(total_in),
        finance_total_out=int(total_out),
        finance_pending_fees=int(pending_fees),
        recent_members=recent_members,
        format_brl=format_brl_cents,
        admin_scope_clube_id=cid,
        admin_needs_clube_scope=is_super_admin() and not cid,
        dash=dash,
        admin_portal=portal,
    )


def _unit_photo_url(rel: str | None) -> str | None:
    if not rel:
        return None
    return url_for("uploaded_file", rel_path=rel)


@bp.route("/unidades")
def admin_units():
    cid = _read_scope_clube_id()
    dash = None
    if cid:
        dash = units_dashboard_payload(cid, _unit_photo_url)
        kw = _scope_kw_for_redirect(cid)
        for card in dash["cards"]:
            card["detail_url"] = url_for("admin.admin_unit_detail", unit_id=card["id"], **kw)
            card["edit_url"] = url_for("admin.admin_unit_edit", unit_id=card["id"], **kw)
    return render_admin_shell(
        "admin/units_dashboard.html",
        un=dash,
        admin_scope_clube_id=cid,
        admin_needs_clube_scope=is_super_admin() and not cid,
    )


@bp.route("/unidades/nova", methods=["GET", "POST"])
def admin_unit_create():
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Selecione um clube no painel.", "warning")
        return redirect(url_for("admin.admin_units", **_scope_kw_for_redirect()))
    if request.method == "POST":
        unit, err = create_unit(write_cid, request.form)
        if err:
            flash(err, "warning")
            return redirect(url_for("admin.admin_unit_create", **_scope_kw_for_redirect(write_cid)))
        logo = request.files.get("logo")
        if logo and logo.filename:
            rel = save_upload(logo, current_app.config["UPLOAD_FOLDER"], "units")
            if rel:
                unit.logo_filename = rel
                db.session.commit()
        flash(f"Unidade «{unit.name}» criada.", "success")
        return redirect(
            url_for("admin.admin_unit_detail", unit_id=unit.id, **_scope_kw_for_redirect(write_cid))
        )
    return render_admin_shell(
        "admin/unit_edit.html",
        unit=None,
        unit_status_options=UNIT_STATUS_OPTIONS,
        unit_theme_options=UNIT_THEME_COLORS,
        admin_scope_clube_id=write_cid,
        is_new=True,
    )


@bp.route("/unidades/<int:unit_id>")
def admin_unit_detail(unit_id: int):
    cid = _read_scope_clube_id()
    if not cid:
        return render_admin_shell(
            "admin/unit_detail.html",
            ud=None,
            admin_scope_clube_id=None,
            admin_needs_clube_scope=True,
        )
    ud = unit_detail_payload(unit_id, cid, _unit_photo_url)
    if not ud:
        flash("Unidade não encontrada.", "warning")
        return redirect(url_for("admin.admin_units", **_scope_kw_for_redirect(cid)))
    kw = _scope_kw_for_redirect(cid)
    ud["unit"]["edit_url"] = url_for("admin.admin_unit_edit", unit_id=unit_id, **kw)
    for row in ud["members"]:
        row["edit_url"] = url_for("admin.member_edit", id=row["id"], **kw)
    return render_admin_shell(
        "admin/unit_detail.html",
        ud=ud,
        active_tab=(request.args.get("tab") or "membros").strip(),
        admin_scope_clube_id=cid,
    )


@bp.route("/unidades/<int:unit_id>/editar", methods=["GET", "POST"])
def admin_unit_edit(unit_id: int):
    cid = _read_scope_clube_id() or _write_clube_id_for_admin()
    if not cid:
        flash("Selecione um clube no painel.", "warning")
        return redirect(url_for("admin.admin_units", **_scope_kw_for_redirect()))
    unit = get_unit_for_club(unit_id, cid)
    if not unit:
        flash("Unidade não encontrada.", "warning")
        return redirect(url_for("admin.admin_units", **_scope_kw_for_redirect(cid)))
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "delete":
            confirm = (request.form.get("confirm_name") or "").strip()
            if confirm != unit.name:
                flash("Digite o nome da unidade para confirmar a exclusão.", "warning")
                return redirect(
                    url_for("admin.admin_unit_edit", unit_id=unit_id, **_scope_kw_for_redirect(cid))
                )
            name = unit.name
            delete_unit(unit, cid)
            flash(f"Unidade «{name}» excluída.", "success")
            return redirect(url_for("admin.admin_units", **_scope_kw_for_redirect(cid)))
        err = update_unit(unit, request.form, cid)
        if err:
            flash(err, "warning")
            return redirect(
                url_for("admin.admin_unit_edit", unit_id=unit_id, **_scope_kw_for_redirect(cid))
            )
        logo = request.files.get("logo")
        if logo and logo.filename:
            rel = save_upload(logo, current_app.config["UPLOAD_FOLDER"], "units")
            if rel:
                unit.logo_filename = rel
                db.session.commit()
        flash("Unidade atualizada.", "success")
        return redirect(
            url_for("admin.admin_unit_detail", unit_id=unit_id, **_scope_kw_for_redirect(cid))
        )
    ud = unit_detail_payload(unit_id, cid, _unit_photo_url)
    return render_admin_shell(
        "admin/unit_edit.html",
        unit=unit,
        ud=ud,
        unit_status_options=UNIT_STATUS_OPTIONS,
        unit_theme_options=UNIT_THEME_COLORS,
        admin_scope_clube_id=cid,
        is_new=False,
    )


@bp.post("/unidades/<int:unit_id>/cargos")
def admin_unit_role_create(unit_id: int):
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Selecione um clube.", "warning")
        return redirect(url_for("admin.admin_units", **_scope_kw_for_redirect()))
    unit = get_unit_for_club(unit_id, write_cid)
    if not unit:
        abort(404)
    err = create_unit_role(
        unit,
        request.form.get("name"),
        request.form.get("color_key") or "gray",
    )
    if err:
        flash(err, "warning")
    else:
        flash("Cargo criado.", "success")
    tab = request.form.get("return_tab") or "cargos"
    return redirect(
        url_for(
            "admin.admin_unit_detail",
            unit_id=unit_id,
            tab=tab,
            **_scope_kw_for_redirect(write_cid),
        )
    )


@bp.post("/unidades/<int:unit_id>/cargos/<int:role_id>/editar")
def admin_unit_role_update(unit_id: int, role_id: int):
    write_cid = _write_clube_id_for_admin()
    unit = get_unit_for_club(unit_id, write_cid) if write_cid else None
    if not unit:
        abort(404)
    role = ClubUnitRole.query.filter_by(id=role_id, unit_id=unit.id).first_or_404()
    err = update_unit_role(role, request.form.get("name"), request.form.get("color_key") or "gray")
    if err:
        flash(err, "warning")
    else:
        flash("Cargo atualizado.", "success")
    return redirect(
        url_for(
            "admin.admin_unit_detail",
            unit_id=unit_id,
            tab=request.form.get("return_tab") or "cargos",
            **_scope_kw_for_redirect(write_cid),
        )
    )


@bp.post("/unidades/<int:unit_id>/cargos/<int:role_id>/excluir")
def admin_unit_role_delete(unit_id: int, role_id: int):
    write_cid = _write_clube_id_for_admin()
    unit = get_unit_for_club(unit_id, write_cid) if write_cid else None
    if not unit:
        abort(404)
    role = ClubUnitRole.query.filter_by(id=role_id, unit_id=unit.id).first_or_404()
    err = delete_unit_role(role)
    if err:
        flash(err, "warning")
    else:
        flash("Cargo excluído.", "success")
    return redirect(
        url_for(
            "admin.admin_unit_detail",
            unit_id=unit_id,
            tab="cargos",
            **_scope_kw_for_redirect(write_cid),
        )
    )


@bp.post("/unidades/<int:unit_id>/membros/adicionar")
def admin_unit_member_add(unit_id: int):
    write_cid = _write_clube_id_for_admin()
    unit = get_unit_for_club(unit_id, write_cid) if write_cid else None
    if not unit:
        abort(404)
    mid = request.form.get("member_id", type=int)
    member = Member.query.filter_by(id=mid, clube_id=write_cid).first()
    if not member:
        flash("Membro inválido.", "warning")
    else:
        err = assign_member_to_unit(
            member, unit, request.form.get("role_name"), write_cid
        )
        if err:
            flash(err, "warning")
        else:
            flash(f"{member.full_name} adicionado à unidade.", "success")
    return redirect(
        url_for("admin.admin_unit_detail", unit_id=unit_id, **_scope_kw_for_redirect(write_cid))
    )


@bp.post("/unidades/<int:unit_id>/membros/<int:member_id>/cargo")
def admin_unit_member_role(unit_id: int, member_id: int):
    write_cid = _write_clube_id_for_admin()
    unit = get_unit_for_club(unit_id, write_cid) if write_cid else None
    if not unit:
        abort(404)
    member = Member.query.filter_by(id=member_id, clube_id=write_cid).first_or_404()
    err = update_member_unit_role(member, unit, request.form.get("role_name") or "")
    if err:
        flash(err, "warning")
    else:
        flash("Cargo atualizado.", "success")
    return redirect(
        url_for("admin.admin_unit_detail", unit_id=unit_id, **_scope_kw_for_redirect(write_cid))
    )


@bp.post("/unidades/<int:unit_id>/membros/<int:member_id>/remover")
def admin_unit_member_remove(unit_id: int, member_id: int):
    write_cid = _write_clube_id_for_admin()
    unit = get_unit_for_club(unit_id, write_cid) if write_cid else None
    member = Member.query.filter_by(id=member_id, clube_id=write_cid).first_or_404()
    if unit and member.unit == unit.name:
        remove_member_from_unit(member)
        flash("Membro removido da unidade.", "success")
    return redirect(
        url_for("admin.admin_unit_detail", unit_id=unit_id, **_scope_kw_for_redirect(write_cid))
    )


@bp.route("/atividades")
def admin_activities():
    cid = _read_scope_clube_id()
    active_tab = (request.args.get("tab") or "desbravadores").strip().lower()
    if active_tab not in ("desbravadores", "classes", "tarefas", "aprovacoes", "relatorios", "todas"):
        active_tab = "desbravadores"

    def _photo_url(rel: str | None) -> str | None:
        if not rel:
            return None
        return url_for("uploaded_file", rel_path=rel)

    if not cid:
        return render_admin_shell(
            "admin/activities_dashboard.html",
            act=None,
            active_tab=active_tab,
            admin_scope_clube_id=None,
            admin_needs_clube_scope=is_super_admin(),
        )

    try:
        page = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    member_id = request.args.get("membro", type=int)
    act = build_activities_dashboard(
        cid,
        photo_url_builder=_photo_url,
        tab=active_tab,
        q=(request.args.get("q") or "").strip(),
        class_filter=(request.args.get("filtro_classe") or "").strip(),
        status_filter=(request.args.get("status") or "").strip(),
        sort=(request.args.get("sort") or "progress").strip(),
        page=page,
        member_id=member_id,
        class_slug=(request.args.get("classe") or "amigo").strip().lower(),
    )
    return render_admin_shell(
        "admin/activities_dashboard.html",
        act=act,
        active_tab=active_tab,
        admin_scope_clube_id=cid,
        admin_needs_clube_scope=False,
    )


@bp.route("/atividades/requisito/<int:progress_id>/status", methods=["POST"])
def activities_requirement_status(progress_id):
    row = set_requirement_status(
        progress_id,
        (request.form.get("status") or "").strip(),
        user_id=current_user.id,
        notes=(request.form.get("notes") or "").strip() or None,
        review_note=(request.form.get("review_note") or "").strip() or None,
    )
    if not row:
        flash("Requisito não encontrado.", "warning")
        return redirect(url_for("admin.admin_activities", **_scope_kw_for_redirect()))
    enr = row.enrollment
    m = enr.member if enr else None
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" and m:
        detail = build_member_notebook_detail(m)
        return jsonify(
            {
                "ok": True,
                "progress_percent": enr.progress_percent if enr else 0,
                "summary": detail.get("summary"),
            }
        )
    flash("Progresso do caderno atualizado.", "success")
    kw = _scope_kw_for_redirect(m.clube_id if m else None)
    if m:
        kw["membro"] = m.id
    return redirect(url_for("admin.admin_activities", **kw))


@bp.route("/atividades/catalogo/<slug>/requisitos.json")
def activities_requirements_json(slug):
    cid = _read_scope_clube_id()
    if not cid:
        return jsonify({"error": "scope"}), 403
    data = build_class_requirements_for_homework(slug.strip().lower())
    if not data:
        return jsonify({"error": "not_found"}), 404
    return jsonify(data)


@bp.route("/atividades/tarefa", methods=["POST"])
def activities_homework_create():
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Selecione um clube no painel.", "warning")
        return redirect(url_for("admin.admin_activities", **_scope_kw_for_redirect()))
    try:
        requirement_id = int(request.form.get("requirement_id") or 0)
    except (TypeError, ValueError):
        requirement_id = 0
    if not requirement_id:
        flash("Selecione um requisito oficial do caderno.", "warning")
        return redirect(url_for("admin.admin_activities", **_scope_kw_for_redirect(write_cid)))
    due_raw = (request.form.get("due_date") or "").strip()
    due_date = None
    if due_raw:
        try:
            due_date = date.fromisoformat(due_raw)
        except ValueError:
            flash("Data de prazo inválida.", "warning")
            return redirect(url_for("admin.admin_activities", tab="tarefas", **_scope_kw_for_redirect(write_cid)))
    attachment = None
    f = request.files.get("attachment")
    if f and f.filename:
        attachment = save_document_upload(f, current_app.config["UPLOAD_FOLDER"], "homework")
    units_raw = (request.form.get("target_units") or "").strip()
    units = [u.strip() for u in units_raw.split(",") if u.strip()] if units_raw else None
    member_ids = []
    for mid in request.form.getlist("target_member_ids"):
        try:
            member_ids.append(int(mid))
        except (TypeError, ValueError):
            pass
    try:
        create_homework(
            write_cid,
            requirement_id=requirement_id,
            description=(request.form.get("description") or "").strip() or None,
            due_date=due_date,
            attachment_filename=attachment,
            created_by_id=current_user.id,
            target_units=units,
            target_member_ids=member_ids or None,
        )
        db.session.commit()
        flash("Requisito enviado como atividade para casa.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("admin.admin_activities", **_scope_kw_for_redirect(write_cid)))


@bp.route("/atividades/envio/<int:sub_id>/revisar", methods=["POST"])
def activities_homework_review(sub_id):
    sub = review_homework_submission(
        sub_id,
        (request.form.get("action") or "").strip(),
        reviewer_id=current_user.id,
        review_note=(request.form.get("review_note") or "").strip() or None,
    )
    if not sub:
        flash("Envio não encontrado.", "warning")
        return redirect(url_for("admin.admin_activities", **_scope_kw_for_redirect()))
    m = sub.member
    db.session.commit()
    flash("Envio revisado.", "success")
    kw = _scope_kw_for_redirect(m.clube_id if m else None)
    if m:
        kw["membro"] = m.id
    return redirect(url_for("admin.admin_activities", **kw))


@bp.route("/especialidades")
def admin_specialties():
    cid = _read_scope_clube_id()
    active_tab = (request.args.get("tab") or "gestao").strip().lower()
    if active_tab not in ("gestao", "catalogo"):
        active_tab = "gestao"

    def _photo_url(rel: str | None) -> str | None:
        if not rel:
            return None
        return url_for("uploaded_file", rel_path=rel)

    if not cid:
        return render_admin_shell(
            "admin/specialties_dashboard.html",
            sp=None,
            active_tab=active_tab,
            admin_scope_clube_id=None,
            admin_needs_clube_scope=is_super_admin(),
        )

    try:
        page = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    member_id = request.args.get("membro", type=int)
    sp = build_admin_dashboard(
        cid,
        photo_url_builder=_photo_url,
        member_id=member_id,
        q=(request.args.get("q") or "").strip(),
        unit_filter=(request.args.get("unidade") or "").strip(),
        status_filter=(request.args.get("status") or "").strip(),
        sort=(request.args.get("sort") or "name").strip(),
        page=page,
        tab=(request.args.get("detail_tab") or "concluidas").strip(),
    )
    return render_admin_shell(
        "admin/specialties_dashboard.html",
        sp=sp,
        active_tab=active_tab,
        admin_scope_clube_id=cid,
        admin_needs_clube_scope=False,
        current_user_name=(current_user.full_name or "Diretor").split()[0],
    )


@bp.route("/especialidades/catalogo", methods=["POST"])
def specialty_catalog_create():
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Selecione um clube no painel.", "warning")
        return redirect(url_for("admin.admin_specialties", **_scope_kw_for_redirect()))
    ensure_default_specialties(write_cid)
    sp = Specialty(clube_id=write_cid)
    err = apply_specialty_form(sp, request.form)
    if err:
        flash(err, "warning")
        return redirect(url_for("admin.admin_specialties", tab="catalogo", **_scope_kw_for_redirect(write_cid)))
    apply_specialty_icon_upload(sp, request.files.get("icon_photo"), current_app.config["UPLOAD_FOLDER"])
    db.session.add(sp)
    db.session.flush()
    save_requirements_from_form(sp, request.form)
    db.session.commit()
    flash(f"Especialidade «{sp.name}» cadastrada.", "success")
    return redirect(url_for("admin.admin_specialties", tab="catalogo", **_scope_kw_for_redirect(write_cid)))


@bp.route("/especialidades/catalogo/<int:sid>", methods=["POST"])
def specialty_catalog_update(sid):
    write_cid = _write_clube_id_for_admin()
    sp = Specialty.query.filter_by(id=sid, clube_id=write_cid).first_or_404()
    err = apply_specialty_form(sp, request.form)
    if err:
        flash(err, "warning")
        return redirect(url_for("admin.admin_specialties", tab="catalogo", **_scope_kw_for_redirect(write_cid)))
    apply_specialty_icon_upload(sp, request.files.get("icon_photo"), current_app.config["UPLOAD_FOLDER"])
    save_requirements_from_form(sp, request.form)
    db.session.commit()
    flash("Especialidade atualizada.", "success")
    return redirect(url_for("admin.admin_specialties", tab="catalogo", **_scope_kw_for_redirect(write_cid)))


@bp.route("/especialidades/catalogo/<int:sid>/excluir", methods=["POST"])
def specialty_catalog_delete(sid):
    write_cid = _write_clube_id_for_admin()
    sp = Specialty.query.filter_by(id=sid, clube_id=write_cid).first_or_404()
    name = delete_catalog_specialty(sp, current_app.config["UPLOAD_FOLDER"])
    db.session.commit()
    flash(f"Especialidade «{name}» removida do catálogo.", "success")
    return redirect(url_for("admin.admin_specialties", tab="catalogo", **_scope_kw_for_redirect(write_cid)))


@bp.route("/especialidades/membro/<int:member_id>/inscrever", methods=["POST"])
def specialty_enroll_member(member_id):
    m = _member_for_admin(member_id)
    sid = request.form.get("specialty_id", type=int)
    if not sid:
        flash("Selecione uma especialidade.", "warning")
        return redirect(
            url_for(
                "admin.admin_specialties",
                membro=m.id,
                **_scope_kw_for_redirect(m.clube_id),
            )
        )
    sp = Specialty.query.filter_by(id=sid, clube_id=m.clube_id, active=True).first_or_404()
    enroll_member(m, sp, user_id=current_user.id)
    db.session.commit()
    flash(f"Especialidade «{sp.name}» vinculada a {m.full_name}.", "success")
    return redirect(
        url_for("admin.admin_specialties", membro=m.id, **_scope_kw_for_redirect(m.clube_id))
    )


@bp.route("/especialidades/progresso/<int:eid>/requisito", methods=["POST"])
def specialty_toggle_requirement(eid):
    enr = MemberSpecialtyProgress.query.get_or_404(eid)
    m = _member_for_admin(enr.member_id)
    req_id = request.form.get("requirement_id", type=int)
    completed = request.form.get("completed") in ("1", "on", "true", "yes")
    if not req_id:
        flash("Requisito inválido.", "warning")
        return redirect(
            url_for("admin.admin_specialties", membro=m.id, **_scope_kw_for_redirect(m.clube_id))
        )
    enr = toggle_requirement(eid, req_id, completed=completed, user_id=current_user.id)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" and enr:
        summary = member_progress_summary(m, m.clube_id)
        return jsonify(
            {
                "ok": True,
                "progress_percent": enr.progress_percent,
                "status": enr.status,
                "summary": summary,
            }
        )
    flash("Progresso atualizado automaticamente.", "success")
    return redirect(
        url_for("admin.admin_specialties", membro=m.id, **_scope_kw_for_redirect(m.clube_id))
    )


@bp.route("/especialidades/progresso/<int:eid>/aprovar", methods=["POST"])
def specialty_approve(eid):
    enr = MemberSpecialtyProgress.query.get_or_404(eid)
    m = _member_for_admin(enr.member_id)
    approve_enrollment(enr, approver_id=current_user.id)
    db.session.commit()
    flash(f"Especialidade aprovada! Insígnia e progresso sincronizados para {m.full_name}.", "success")
    return redirect(
        url_for("admin.admin_specialties", membro=m.id, **_scope_kw_for_redirect(m.clube_id))
    )


@bp.route("/especialidades/progresso/<int:eid>/excluir", methods=["POST"])
def specialty_enrollment_delete(eid):
    enr = MemberSpecialtyProgress.query.get_or_404(eid)
    m = _member_for_admin(enr.member_id)
    name = delete_member_enrollment(enr)
    db.session.commit()
    flash(f"Registro «{name}» removido de {m.full_name}. Progresso atualizado.", "success")
    return redirect(
        url_for("admin.admin_specialties", membro=m.id, **_scope_kw_for_redirect(m.clube_id))
    )


@bp.route("/almoxarifado")
def admin_warehouse():
    perms = get_admin_panel_permissions()
    if not perms.get("can_view_warehouse"):
        flash("Seu cargo não permite acessar o almoxarifado.", "warning")
        return redirect(url_for("admin.dashboard", **_scope_kw_for_redirect()))

    cid = _read_scope_clube_id()
    active_tab = (request.args.get("tab") or "dashboard").strip().lower()
    if active_tab not in ("dashboard", "items", "entradas", "saidas", "historico", "categorias"):
        active_tab = "dashboard"

    if not cid:
        return render_admin_shell(
            "admin/warehouse_dashboard.html",
            wh=None,
            active_tab=active_tab,
            can_write_warehouse=perms.get("can_write_warehouse"),
            admin_scope_clube_id=None,
            admin_needs_clube_scope=is_super_admin(),
            format_brl=format_brl_cents,
        )

    def _photo_url(rel: str | None) -> str | None:
        if not rel:
            return None
        return url_for("uploaded_file", rel_path=rel)

    wh = build_warehouse_dashboard(
        cid,
        photo_url_builder=_photo_url,
        viewer_id=current_user.id,
        can_write=bool(perms.get("can_write_warehouse")),
    )
    return render_admin_shell(
        "admin/warehouse_dashboard.html",
        wh=wh,
        active_tab=active_tab,
        can_write_warehouse=perms.get("can_write_warehouse"),
        admin_scope_clube_id=cid,
        format_brl=format_brl_cents,
    )


@bp.route("/almoxarifado/item", methods=["POST"])
def warehouse_item_create():
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão para cadastrar itens.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Selecione um clube no painel.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    ensure_default_categories(write_cid)
    item = WarehouseItem(clube_id=write_cid, quantity=0)
    err = apply_item_form(item, request.form)
    if err:
        flash(err, "warning")
        return redirect(url_for("admin.admin_warehouse", tab="items", **_scope_kw_for_redirect(write_cid)))

    try:
        initial_qty = max(0, int(request.form.get("initial_quantity") or 0))
    except (TypeError, ValueError):
        initial_qty = 0

    photo = save_upload(request.files.get("photo"), current_app.config["UPLOAD_FOLDER"], "warehouse")
    if photo:
        item.photo_filename = photo

    db.session.add(item)
    db.session.flush()

    if initial_qty > 0:
        record_movement(
            item,
            WH_MOVEMENT_IN,
            initial_qty,
            notes="Quantidade inicial",
            user_id=current_user.id,
        )

    db.session.commit()
    flash(f"Item «{item.name}» cadastrado.", "success")
    return redirect(url_for("admin.admin_warehouse", tab="items", **_scope_kw_for_redirect(write_cid)))


@bp.route("/almoxarifado/item/<int:iid>", methods=["POST"])
def warehouse_item_update(iid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão para editar itens.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    item = _warehouse_item_for_admin(iid)
    err = apply_item_form(item, request.form)
    if err:
        flash(err, "warning")
        return redirect(url_for("admin.admin_warehouse", tab="items", **_scope_kw_for_redirect(item.clube_id)))

    photo = save_upload(request.files.get("photo"), current_app.config["UPLOAD_FOLDER"], "warehouse")
    if photo:
        item.photo_filename = photo

    item.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Item atualizado.", "success")
    return redirect(url_for("admin.admin_warehouse", tab="items", **_scope_kw_for_redirect(item.clube_id)))


@bp.route("/almoxarifado/item/<int:iid>/excluir", methods=["POST"])
def warehouse_item_delete(iid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão para excluir itens.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    item = _warehouse_item_for_admin(iid)
    cid = item.clube_id
    item.active = False
    db.session.commit()
    flash("Item removido do almoxarifado.", "success")
    return redirect(url_for("admin.admin_warehouse", tab="items", **_scope_kw_for_redirect(cid)))


@bp.route("/almoxarifado/item/<int:iid>/movimento", methods=["POST"])
def warehouse_item_movement(iid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão para movimentar estoque.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    item = _warehouse_item_for_admin(iid)
    direction = (request.form.get("direction") or "").strip()
    try:
        qty = int(request.form.get("quantity") or 0)
    except (TypeError, ValueError):
        qty = 0
    notes = (request.form.get("notes") or "").strip()
    err = record_movement(item, direction, qty, notes=notes, user_id=current_user.id)
    if err:
        flash(err, "warning")
        tab = "entradas" if direction == WH_MOVEMENT_IN else "saidas"
        return redirect(url_for("admin.admin_warehouse", tab=tab, **_scope_kw_for_redirect(item.clube_id)))

    db.session.commit()
    label = "Entrada" if direction == WH_MOVEMENT_IN else "Saída"
    flash(f"{label} registrada para «{item.name}».", "success")
    tab = "entradas" if direction == WH_MOVEMENT_IN else "saidas"
    return redirect(url_for("admin.admin_warehouse", tab=tab, **_scope_kw_for_redirect(item.clube_id)))


@bp.route("/almoxarifado/movimento/<int:mid>/excluir", methods=["POST"])
def warehouse_movement_delete(mid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão para excluir lançamentos.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    mv = _warehouse_movement_for_admin(mid)
    cid = mv.clube_id
    tab = (request.form.get("tab") or "historico").strip()
    if tab not in ("dashboard", "entradas", "saidas", "historico"):
        tab = "historico"

    err = delete_movement(mv, viewer_id=current_user.id)
    if err:
        flash(err, "warning")
        return redirect(url_for("admin.admin_warehouse", tab=tab, **_scope_kw_for_redirect(cid)))

    db.session.commit()
    flash("Lançamento excluído e estoque atualizado.", "success")
    return redirect(url_for("admin.admin_warehouse", tab=tab, **_scope_kw_for_redirect(cid)))


@bp.route("/almoxarifado/categoria", methods=["POST"])
def warehouse_category_create():
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Selecione um clube.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Informe o nome da categoria.", "warning")
        return redirect(url_for("admin.admin_warehouse", tab="categorias", **_scope_kw_for_redirect(write_cid)))

    existing = WarehouseCategory.query.filter_by(clube_id=write_cid, name=name).first()
    if existing:
        flash("Já existe uma categoria com esse nome.", "warning")
        return redirect(url_for("admin.admin_warehouse", tab="categorias", **_scope_kw_for_redirect(write_cid)))

    max_order = (
        db.session.query(func.max(WarehouseCategory.sort_order))
        .filter_by(clube_id=write_cid)
        .scalar()
        or 0
    )
    db.session.add(WarehouseCategory(clube_id=write_cid, name=name[:80], sort_order=int(max_order) + 1))
    db.session.commit()
    flash("Categoria criada.", "success")
    return redirect(url_for("admin.admin_warehouse", tab="categorias", **_scope_kw_for_redirect(write_cid)))


@bp.route("/almoxarifado/categoria/<int:cat_id>/excluir", methods=["POST"])
def warehouse_category_delete(cat_id):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_warehouse"):
        flash("Sem permissão.", "warning")
        return redirect(url_for("admin.admin_warehouse", **_scope_kw_for_redirect()))

    cat = _warehouse_category_for_admin(cat_id)
    cid = cat.clube_id
    linked = WarehouseItem.query.filter_by(category_id=cat.id, active=True).count()
    if linked:
        flash(f"Não é possível excluir: {linked} item(ns) usam esta categoria.", "warning")
        return redirect(url_for("admin.admin_warehouse", tab="categorias", **_scope_kw_for_redirect(cid)))

    db.session.delete(cat)
    db.session.commit()
    flash("Categoria excluída.", "success")
    return redirect(url_for("admin.admin_warehouse", tab="categorias", **_scope_kw_for_redirect(cid)))


def _gallery_clube_or_abort():
    cid = _read_scope_clube_id()
    if not cid:
        if is_super_admin():
            flash("Selecione um clube no escopo para abrir a galeria.", "warning")
            return None
        abort(403)
    return cid


def _gallery_manage_guard():
    perms = get_admin_panel_permissions()
    if not perms.get("can_manage_gallery"):
        return jsonify({"ok": False, "error": "Sem permissão de diretoria."}), 403
    return None


@bp.route("/relatorios")
@login_required
def admin_reports_redirect():
    """Compatibilidade: antiga aba Relatórios → Galeria."""
    return redirect(url_for("admin.admin_gallery", **_scope_kw_for_redirect()))


@bp.route("/galeria")
@login_required
def admin_gallery():
    perms = get_admin_panel_permissions()
    if not perms.get("can_view_gallery"):
        abort(403)
    cid = _gallery_clube_or_abort()
    if not cid:
        return redirect(url_for("admin.dashboard", **_scope_kw_for_redirect()))
    static_img = Path(current_app.root_path).parent.parent / "frontend" / "static" / "img" / "login-nature.jpg"
    try:
        ensure_demo_gallery(cid, current_app.config["UPLOAD_FOLDER"], static_img=str(static_img))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("Demo galeria ignorada: %s", exc)
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("filtro") or request.args.get("filter") or "").strip()
    page = build_gallery_page(cid, q=q, category=category)
    return render_admin_shell(
        "admin/gallery_hub.html",
        gallery=page,
        can_manage_gallery=perms.get("can_manage_gallery"),
        search_q=q,
        active_filter=category,
    )


@bp.route("/galeria/api/bootstrap")
@login_required
def gallery_api_bootstrap():
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("filtro") or "").strip()
    return jsonify({"ok": True, **build_gallery_page(cid, q=q, category=category)})


@bp.route("/galeria/api/album/<int:album_id>/photos")
@login_required
def gallery_api_album_photos(album_id):
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    album = get_album_for_club(album_id, cid)
    if not album:
        return jsonify({"ok": False, "error": "Álbum não encontrado."}), 404
    return jsonify({"ok": True, "album": serialize_album(album), "photos": album_photos_for_lightbox(album_id, cid)})


@bp.route("/galeria/api/albums", methods=["POST"])
@login_required
def gallery_api_album_create():
    denied = _gallery_manage_guard()
    if denied:
        return denied
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "Informe o nome do álbum."}), 400
    from datetime import date as date_cls

    ev = None
    if data.get("event_date"):
        try:
            ev = date_cls.fromisoformat(str(data["event_date"])[:10])
        except ValueError:
            pass
    album = create_album(
        cid,
        title=title,
        description=data.get("description") or "",
        category=data.get("category") or "geral",
        event_date=ev,
        featured=bool(data.get("featured")),
    )
    db.session.commit()
    return jsonify({"ok": True, "album": serialize_album(album)})


@bp.route("/galeria/api/albums/<int:album_id>", methods=["PATCH", "DELETE"])
@login_required
def gallery_api_album_update(album_id):
    denied = _gallery_manage_guard()
    if denied:
        return denied
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    album = get_album_for_club(album_id, cid)
    if not album:
        return jsonify({"ok": False, "error": "Álbum não encontrado."}), 404
    if request.method == "DELETE":
        trash_album(album, current_app.config["UPLOAD_FOLDER"])
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    update_album(album, data)
    if data.get("set_featured"):
        set_featured_album(album)
    db.session.commit()
    return jsonify({"ok": True, "album": serialize_album(album)})


@bp.route("/galeria/api/albums/<int:album_id>/cover", methods=["POST"])
@login_required
def gallery_api_album_cover(album_id):
    denied = _gallery_manage_guard()
    if denied:
        return denied
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    album = get_album_for_club(album_id, cid)
    if not album:
        return jsonify({"ok": False, "error": "Álbum não encontrado."}), 404
    data = request.get_json(silent=True) or {}
    photo_id = int(data.get("photo_id") or 0)
    try:
        set_album_cover(album, photo_id)
        db.session.commit()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "album": serialize_album(album)})


@bp.route("/galeria/api/photos/upload", methods=["POST"])
@login_required
def gallery_api_photos_upload():
    denied = _gallery_manage_guard()
    if denied:
        return denied
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    album_id = int(request.form.get("album_id") or 0)
    if not album_id:
        new_title = (request.form.get("new_album_title") or "").strip()
        if new_title:
            album = create_album(cid, title=new_title, category=request.form.get("category") or "geral")
            db.session.flush()
            album_id = album.id
        else:
            return jsonify({"ok": False, "error": "Selecione ou crie um álbum."}), 400
    files = request.files.getlist("photos") or request.files.getlist("files") or []
    if not files:
        f = request.files.get("photo")
        if f:
            files = [f]
    if not files:
        return jsonify({"ok": False, "error": "Nenhuma imagem enviada."}), 400
    try:
        created = upload_photos(cid, album_id, files, current_app.config["UPLOAD_FOLDER"])
        db.session.commit()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify(
        {
            "ok": True,
            "count": len(created),
            "photos": [serialize_photo(p) for p in created],
        }
    )


@bp.route("/galeria/api/photos/<int:photo_id>", methods=["PATCH", "DELETE"])
@login_required
def gallery_api_photo_update(photo_id):
    denied = _gallery_manage_guard()
    if denied:
        return denied
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    photo = get_photo_for_club(photo_id, cid)
    if not photo:
        return jsonify({"ok": False, "error": "Foto não encontrada."}), 404
    if request.method == "DELETE":
        permanent = request.args.get("permanent") == "1"
        trash_photo(photo, current_app.config["UPLOAD_FOLDER"], permanent=permanent)
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    if data.get("album_id"):
        try:
            move_photo_to_album(photo, int(data["album_id"]), cid)
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
    else:
        update_photo(photo, data)
    db.session.commit()
    return jsonify({"ok": True, "photo": serialize_photo(photo)})


@bp.route("/galeria/api/trash")
@login_required
def gallery_api_trash():
    denied = _gallery_manage_guard()
    if denied:
        return denied
    cid = _gallery_clube_or_abort()
    if not cid:
        return jsonify({"ok": False}), 400
    return jsonify({"ok": True, **trashed_items(cid)})


@bp.route("/configuracoes")
def admin_settings():
    return render_admin_shell("admin/settings_hub.html", admin_scope_clube_id=_read_scope_clube_id())


@bp.route("/responsaveis/api/search-parents")
@login_required
def parents_api_search_parents():
    cid = _read_scope_clube_id()
    if not cid and is_super_admin():
        return jsonify([])
    q = (request.args.get("q") or "").strip()
    return jsonify(search_parents(cid, q))


@bp.route("/responsaveis/api/search-members")
@login_required
def parents_api_search_members():
    cid = _read_scope_clube_id()
    if not cid and is_super_admin():
        return jsonify([])
    q = (request.args.get("q") or "").strip()
    return jsonify(search_unlinked_members(cid, q))


@bp.route("/responsaveis/api/suggest/<int:member_id>")
@login_required
def parents_api_suggest(member_id):
    cid = _read_scope_clube_id()
    m = db.session.get(Member, member_id)
    if not m or (cid and m.clube_id != cid):
        return jsonify([])
    return jsonify(suggest_parents_for_member(m, cid))


@bp.route("/responsaveis", methods=["GET", "POST"])
def parents_list():
    cid = _read_scope_clube_id()
    perms = get_admin_panel_permissions()

    if request.method == "POST":
        if not perms.get("can_manage_member_links"):
            flash("Seu cargo não permite gerenciar vínculos.", "warning")
            return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
        action = (request.form.get("action") or "").strip()
        if action == "link":
            try:
                parent_id = int(request.form.get("parent_user_id") or "")
                member_id = int(request.form.get("member_id") or "")
            except (TypeError, ValueError):
                flash("Selecione o responsável e o desbravador.", "warning")
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            link_type = normalize_link_type(request.form.get("link_type"))
            parent_user = find_parent_user_for_link(user_id=parent_id)
            if not parent_user:
                flash(
                    "Responsável inválido. A conta deve ser criada em «Criar conta» no site.",
                    "warning",
                )
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            m = db.session.get(Member, member_id)
            if not m:
                flash("Desbravador não encontrado.", "danger")
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            if cid and m.clube_id != cid:
                flash("Desbravador não pertence a este clube.", "danger")
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            err = link_member_to_parent(
                m,
                parent_user,
                link_type=link_type,
                performed_by=current_user,
            )
            if err:
                flash(err, "warning")
            else:
                db.session.commit()
                flash(link_summary_message(m, parent_user), "success")
            return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect(cid or m.clube_id)))
        if action == "unlink":
            try:
                member_id = int(request.form.get("member_id") or "")
            except (TypeError, ValueError):
                flash("Desbravador inválido.", "warning")
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            m = db.session.get(Member, member_id)
            if not m:
                flash("Desbravador não encontrado.", "danger")
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            if cid and m.clube_id != cid:
                flash("Desbravador não pertence a este clube.", "danger")
                return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
            if m.parent_id:
                unlink_member_from_parent(m, m.parent_id, performed_by=current_user)
                db.session.commit()
                flash("Vínculo removido.", "info")
            return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect(cid or m.clube_id)))

    parents = parent_users_query()
    rows = [serialize_parent_row(p, cid) for p in parents]
    unlinked = _unlinked_members_for_club()
    unlinked_cards = [serialize_member_card(m) for m in unlinked]
    return render_admin_shell(
        "admin/parents_list.html",
        rows=rows,
        parent_accounts=parents,
        unlinked_members=unlinked,
        unlinked_cards=unlinked_cards,
        metrics=parents_metrics(cid),
        link_history=link_history_for_club(cid),
        link_types=PARENT_LINK_TYPES,
        link_type_labels=dict(PARENT_LINK_TYPES),
        admin_scope_clube_id=cid,
    )


@bp.route("/responsaveis/<int:user_id>", methods=["GET", "POST"])
def parent_detail(user_id):
    p, p_profile = _user_profile_if_in_scope(user_id)
    if not p or not p_profile:
        flash("Responsável não encontrado.", "danger")
        return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))

    if request.method == "POST":
        perms = get_admin_panel_permissions()
        action = request.form.get("action")
        if action in {"link", "unlink", "change_type", "transfer"} and not perms.get(
            "can_manage_member_links"
        ):
            flash("Seu cargo não permite gerenciar vínculos.", "warning")
            return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
        if action == "change_type":
            try:
                mid = int(request.form.get("member_id") or "")
            except (TypeError, ValueError):
                flash("Desbravador inválido.", "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            m = db.session.get(Member, mid)
            scope_c = _read_scope_clube_id()
            if not m or m.parent_id != p.id:
                flash("Vínculo não encontrado.", "danger")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            if scope_c and m.clube_id != scope_c:
                flash("Operação não permitida.", "danger")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            err = change_member_link_type(
                m, request.form.get("link_type"), performed_by=current_user
            )
            if err:
                flash(err, "warning")
            else:
                db.session.commit()
                flash("Tipo de vínculo atualizado.", "success")
            return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
        if action == "transfer":
            try:
                mid = int(request.form.get("member_id") or "")
                new_parent_id = int(request.form.get("new_parent_id") or "")
            except (TypeError, ValueError):
                flash("Selecione o desbravador e o novo responsável.", "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            m = db.session.get(Member, mid)
            new_parent = find_parent_user_for_link(user_id=new_parent_id)
            scope_c = _read_scope_clube_id()
            if not m or not new_parent:
                flash("Dados inválidos para transferência.", "danger")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            if scope_c and m.clube_id != scope_c:
                flash("Operação não permitida.", "danger")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            if m.parent_id != p.id:
                flash("Este desbravador não está vinculado a este responsável.", "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            link_type = normalize_link_type(request.form.get("link_type"))
            err = transfer_member_to_parent(
                m, new_parent, link_type=link_type, performed_by=current_user
            )
            if err:
                flash(err, "warning")
            else:
                db.session.commit()
                flash(
                    f"Desbravador transferido para {new_parent.full_name or new_parent.email}.",
                    "success",
                )
            return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
        if action == "link":
            mid_raw = request.form.get("member_id")
            try:
                mid = int(mid_raw)
            except (TypeError, ValueError):
                flash("Selecione um desbravador.", "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            m = db.session.get(Member, mid)
            if not m:
                flash("Membro inválido.", "danger")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            scope_c = _read_scope_clube_id()
            if scope_c and m.clube_id != scope_c:
                flash("Membro não encontrado neste clube.", "danger")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            if not is_registered_parent_account(p):
                flash(
                    "Esta conta não é de responsável cadastrado no site.",
                    "warning",
                )
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            link_type = normalize_link_type(request.form.get("link_type"))
            err = link_member_to_parent(
                m,
                p,
                link_type=link_type,
                performed_by=current_user,
            )
            if err:
                flash(err, "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
            db.session.commit()
            flash(f"Vínculo criado. {link_summary_message(m, p)}", "success")
            return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
        if action == "unlink":
            mid_raw = request.form.get("member_id")
            try:
                mid = int(mid_raw)
            except (TypeError, ValueError):
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            m = db.session.get(Member, mid)
            scope_c = _read_scope_clube_id()
            if m and m.parent_id == p.id:
                if scope_c and m.clube_id != scope_c:
                    flash("Operação não permitida.", "danger")
                    return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
                unlink_member_from_parent(m, p.id, performed_by=current_user)
                db.session.commit()
                flash("Vínculo removido.", "info")
            return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))

    scope = _read_scope_clube_id() or p_profile.clube_id
    linked = _children_for_parent(p.id)
    if scope:
        linked = [k for k in linked if k.clube_id == scope]
    other_parents = [
        u for u in parent_users_query() if u.id != p.id
    ]
    return render_admin_shell(
        "admin/parent_detail.html",
        parent_user=p,
        linked=linked,
        unlinked=_unlinked_members_for_club(),
        other_parents=other_parents,
        admin_scope_clube_id=scope,
        is_parent_account=is_registered_parent_account(p),
        link_types=PARENT_LINK_TYPES,
        link_type_labels=dict(PARENT_LINK_TYPES),
    )


@bp.route("/responsaveis/<int:user_id>/excluir", methods=["POST"])
def parent_delete(user_id):
    p, p_profile = _user_profile_if_in_scope(user_id)
    if not p or not p_profile:
        flash("Conta não encontrada.", "danger")
        return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
    perms = get_admin_panel_permissions()
    if not perms.get("can_delete_parent_accounts"):
        flash("Seu cargo não permite excluir conta de responsável.", "warning")
        return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
    if current_user.id == p.id:
        flash("Você não pode excluir a própria conta por este painel.", "danger")
        return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
    cid_scope = p_profile.clube_id if p_profile else None
    err = delete_parent_account(p, club_id=cid_scope)
    if err:
        flash(err, "danger")
        return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
    db.session.commit()
    flash(
        "Conta do responsável excluída. Os desbravadores permanecem no sistema, sem vínculo.",
        "info",
    )
    return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect(cid_scope)))


@bp.route("/presencas", methods=["GET", "POST"])
def attendance_overview():
    from app.attendance_service import (
        build_attendance_portal,
        normalize_attendance_status,
        save_roll_call,
    )

    cid = _read_scope_clube_id()
    if not cid:
        return render_admin_shell(
            "admin/attendance_overview.html",
            att=None,
            admin_needs_clube_scope=is_super_admin(),
            admin_scope_clube_id=None,
        )

    def _photo_url(rel: str | None) -> str | None:
        if not rel:
            return None
        return url_for("uploaded_file", rel_path=rel)

    if request.method == "POST":
        md_raw = (request.form.get("meeting_date") or "").strip()
        try:
            md = date.fromisoformat(md_raw)
        except ValueError:
            flash("Data da reunião inválida.", "warning")
            return redirect(url_for("admin.attendance_overview", **_scope_kw_for_redirect(cid)))
        entries = []
        for key in request.form:
            if key.startswith("status_"):
                try:
                    mid = int(key.replace("status_", "", 1))
                except ValueError:
                    continue
                status = normalize_attendance_status(request.form.get(key))
                note = (request.form.get(f"note_{mid}") or "").strip() or None
                entries.append({"member_id": mid, "status": status, "note": note})
        if request.form.get("bulk_present") == "1":
            members = _members_scoped_query().filter_by(clube_id=cid).all()
            entries = [
                {"member_id": m.id, "status": "presente", "note": ""} for m in members
            ]
        n = save_roll_call(cid, md, entries)
        flash(f"Presença salva — {n} registro(s) atualizado(s).", "success")
        return redirect(
            url_for(
                "admin.attendance_overview",
                meeting_date=md.isoformat(),
                **_scope_kw_for_redirect(cid),
            )
        )

    meeting_raw = (request.args.get("meeting_date") or "").strip()
    meeting_date = None
    if meeting_raw:
        try:
            meeting_date = date.fromisoformat(meeting_raw)
        except ValueError:
            meeting_date = None

    cal_raw = (request.args.get("cal_month") or "").strip()
    calendar_month = None
    if cal_raw and len(cal_raw) >= 7:
        try:
            calendar_month = date.fromisoformat(cal_raw + "-01")
        except ValueError:
            calendar_month = None

    att = build_attendance_portal(
        cid,
        meeting_date=meeting_date,
        calendar_month=calendar_month,
        photo_url_builder=_photo_url,
    )
    return render_admin_shell(
        "admin/attendance_overview.html",
        att=att,
        admin_scope_clube_id=cid,
        admin_needs_clube_scope=False,
    )


@bp.route("/membros")
def members():
    from app.members_service import members_page_context

    rows = _members_scoped_query().order_by(Member.full_name).all()
    cid = _read_scope_clube_id()
    nav_kw = _scope_kw_for_redirect(cid)

    def _photo_url(rel):
        return url_for("uploaded_file", rel_path=rel) if rel else None

    mb_ctx = members_page_context(rows, cid, _photo_url, nav_kw=nav_kw)
    return render_admin_shell(
        "admin/members.html",
        members=rows,
        format_cpf_display=format_cpf_display,
        admin_scope_clube_id=cid,
        **mb_ctx,
    )


def _member_form_ctx(member):
    opts = list(NOTEBOOK_ACTIVITY_OPTIONS)
    if member and member.notebook_current:
        cur = (member.notebook_current or "").strip()
        if cur and cur not in opts:
            opts = [cur] + opts
    cid = _read_scope_clube_id() or (member.clube_id if member else None)
    linked_parent = None
    if member and member.parent_id:
        linked_parent = db.session.get(User, member.parent_id)
    ctx = dict(
        member=member,
        linked_parent=linked_parent,
        notebook_options=opts,
        admin_scope_clube_id=cid,
    )
    if is_super_admin():
        ctx["clubs"] = Club.query.order_by(Club.nome.asc()).all()
        ctx["show_clube_picker"] = member is None
    else:
        ctx["clubs"] = []
        ctx["show_clube_picker"] = False
    return ctx


def _member_wizard_ctx(member=None):
    from app.member_wizard import wizard_context

    base = _member_form_ctx(member)
    cid = base.get("admin_scope_clube_id") or (member.clube_id if member else None)
    ctx = wizard_context(member, clube_id=cid)
    ctx.update(base)
    ctx["photo_url"] = (
        url_for("uploaded_file", rel_path=member.photo_filename)
        if member and member.photo_filename
        else None
    )
    return ctx


@bp.route("/membros/novo", methods=["GET", "POST"])
def member_new():
    from app.member_wizard import apply_wizard_form

    perms = get_admin_panel_permissions()
    if not perms.get("can_add_members"):
        flash("Você não tem permissão para cadastrar novos desbravadores.", "warning")
        return redirect(url_for("admin.members", **_scope_kw_for_redirect()))
    if request.method == "POST":
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash(
                "Selecione o clube para cadastrar o desbravador (super admin: use ?clube_id= ou o campo no formulário).",
                "warning",
            )
            return render_admin_shell("admin/member_wizard.html", **_member_wizard_ctx(None))
        m = Member(full_name="—", clube_id=write_cid, member_status="ativo")
        try:
            apply_wizard_form(m, request.form)
        except ValueError as e:
            flash(str(e), "warning")
            return render_admin_shell("admin/member_wizard.html", **_member_wizard_ctx(None))
        db.session.add(m)
        db.session.flush()
        _process_member_photo(m)
        ensure_member_notebook(m, user_id=current_user.id)
        db.session.commit()
        flash(
            "Desbravador cadastrado com sucesso! Vincule o responsável ao portal em Admin → Responsáveis.",
            "success",
        )
        return redirect(url_for("admin.member_profile", id=m.id, **_scope_kw_for_redirect(m.clube_id)))

    return render_admin_shell("admin/member_wizard.html", **_member_wizard_ctx(None))


@bp.route("/membros/<int:id>/vinculo", methods=["POST"])
def member_parent_link(id):
    """Gerencia vínculo portal família a partir da ficha do desbravador."""
    m = _member_for_admin(id)
    perms = get_admin_panel_permissions()
    if not perms.get("can_manage_member_links"):
        flash("Seu cargo não permite gerenciar vínculos.", "warning")
        return redirect(url_for("admin.member_profile", id=m.id, **_scope_kw_for_redirect(m.clube_id)))

    action = (request.form.get("action") or "").strip()
    redirect_to = request.form.get("next") or url_for(
        "admin.member_profile", id=m.id, **_scope_kw_for_redirect(m.clube_id)
    )

    if action == "unlink":
        if m.parent_id:
            unlink_member_from_parent(m, m.parent_id, performed_by=current_user)
            db.session.commit()
            flash("Vínculo com responsável removido.", "info")
        return redirect(redirect_to)

    if action == "change_type":
        if not m.parent_id:
            flash("Desbravador sem responsável vinculado.", "warning")
            return redirect(redirect_to)
        err = change_member_link_type(
            m, request.form.get("link_type"), performed_by=current_user
        )
        if err:
            flash(err, "warning")
        else:
            db.session.commit()
            flash("Tipo de vínculo atualizado.", "success")
        return redirect(redirect_to)

    if action in {"link", "transfer"}:
        try:
            parent_id = int(request.form.get("parent_user_id") or "")
        except (TypeError, ValueError):
            flash("Selecione um responsável.", "warning")
            return redirect(redirect_to)
        parent_user = find_parent_user_for_link(user_id=parent_id)
        if not parent_user:
            flash("Responsável inválido.", "warning")
            return redirect(redirect_to)
        link_type = normalize_link_type(request.form.get("link_type"))
        if action == "transfer" or m.parent_id:
            err = transfer_member_to_parent(
                m, parent_user, link_type=link_type, performed_by=current_user
            )
        else:
            err = link_member_to_parent(
                m, parent_user, link_type=link_type, performed_by=current_user
            )
        if err:
            flash(err, "warning")
        else:
            db.session.commit()
            flash(link_summary_message(m, parent_user), "success")
        return redirect(redirect_to)

    flash("Ação inválida.", "warning")
    return redirect(redirect_to)


@bp.route("/membros/<int:id>/perfil")
def member_profile(id):
    """Ficha premium do desbravador (visualização). Edição em member_edit."""
    m = _member_for_admin(id)
    profile_ctx = build_member_profile_context(m, mode="admin", linked_parent=m.parent)
    return render_admin_shell(
        "admin/member_profile.html",
        member=m,
        admin_scope_clube_id=_read_scope_clube_id() or m.clube_id,
        parent_link_types=PARENT_LINK_TYPES,
        **profile_ctx,
    )


@bp.route("/membros/<int:id>/editar", methods=["GET", "POST"])
def member_edit(id):
    from app.member_wizard import apply_wizard_form

    m = _member_for_admin(id)
    if request.method == "POST":
        try:
            apply_wizard_form(m, request.form, member_id_exclude=m.id)
        except ValueError as e:
            flash(str(e), "warning")
            return render_admin_shell("admin/member_wizard.html", **_member_wizard_ctx(m))
        _process_member_photo(m)
        ensure_member_notebook(m, user_id=current_user.id)
        db.session.commit()
        flash("Dados do desbravador atualizados.", "success")
        return redirect(url_for("admin.member_profile", id=m.id, **_scope_kw_for_redirect(m.clube_id)))
    return render_admin_shell("admin/member_wizard.html", **_member_wizard_ctx(m))


@bp.route("/membros/<int:id>/excluir", methods=["POST"])
def member_delete(id):
    m = _member_for_admin(id)
    perms = get_admin_panel_permissions()
    if not perms.get("can_delete_members"):
        flash("Você não tem permissão para excluir desbravadores.", "warning")
        return redirect(url_for("admin.members", **_scope_kw_for_redirect(m.clube_id)))
    MemberFee.query.filter_by(member_id=m.id).delete()
    FinanceLedgerEntry.query.filter_by(member_id=m.id).update(
        {FinanceLedgerEntry.member_id: None}, synchronize_session=False
    )
    ActivityRecord.query.filter_by(member_id=m.id).delete()
    from app.models import HomeworkSubmission, MemberNotebookEnrollment

    HomeworkSubmission.query.filter_by(member_id=m.id).delete()
    MemberNotebookEnrollment.query.filter_by(member_id=m.id).delete()
    Attendance.query.filter_by(member_id=m.id).delete()
    MeetingDuque.query.filter_by(member_id=m.id).delete()
    _safe_remove_upload(m.photo_filename)
    db.session.delete(m)
    db.session.commit()
    flash("Desbravador removido do sistema.", "info")
    return redirect(url_for("admin.members", **_scope_kw_for_redirect(m.clube_id)))


def _agenda_banner_url(ev: AgendaEvent | None) -> str | None:
    if ev and ev.banner_filename:
        return url_for("uploaded_file", rel_path=ev.banner_filename)
    return None


def _process_agenda_banner(ev: AgendaEvent) -> None:
    if request.form.get("remove_banner") == "1":
        _safe_remove_upload(ev.banner_filename)
        ev.banner_filename = None
        return
    f = request.files.get("banner")
    if not f or not f.filename:
        return
    saved = save_upload(f, current_app.config["UPLOAD_FOLDER"], "agenda")
    if saved:
        _safe_remove_upload(ev.banner_filename)
        ev.banner_filename = saved


def _agenda_page_context(
    month_events: list,
    *,
    year: int,
    month: int,
    selected_day: date,
    today: date,
    user_rsvps: dict | None = None,
) -> dict:
    user_rsvps = user_rsvps or {}
    rsvp_counts = batch_confirmed_counts([e.id for e in month_events])
    serialized = []
    events_by_date: dict[str, list] = {}
    for ev in month_events:
        banner = _agenda_banner_url(ev)
        data = serialize_event(
            ev,
            rsvp_count=rsvp_counts.get(ev.id, 0),
            user_rsvp=user_rsvps.get(ev.id),
            banner_url=banner,
        )
        serialized.append(data)
        key = ev.event_date.isoformat()
        events_by_date.setdefault(key, []).append(ev)

    featured = featured_upcoming(month_events, today)
    featured_data = None
    if featured:
        fe = featured[0]
        featured_data = serialize_event(
            fe,
            rsvp_count=rsvp_counts.get(fe.id, 0),
            banner_url=_agenda_banner_url(fe),
        )
        featured_data["countdown_target"] = fe.event_date.isoformat()

    timeline = [
        serialize_event(e, banner_url=_agenda_banner_url(e))
        for e in timeline_events(month_events, today)
    ]

    cid = _read_scope_clube_id()
    leaders = []
    if cid:
        for d in (
            _directorate_scoped_query()
            .order_by(DirectorateMember.display_order, DirectorateMember.full_name)
            .limit(24)
            .all()
        ):
            photo = ""
            if d.photo_filename:
                photo = url_for("uploaded_file", rel_path=d.photo_filename)
            leaders.append(
                {
                    "id": d.id,
                    "name": d.full_name,
                    "role": d.cargo,
                    "photo": photo,
                }
            )

    drawer_config = {
        "types": EVENT_TYPE_CARDS,
        "colors": EVENT_COLOR_PALETTE,
        "templates": {
            k: {**v, "checklist": v.get("checklist", [])}
            for k, v in EVENT_TEMPLATES.items()
        },
        "checklists": EVENT_CHECKLISTS,
        "categories": EVENT_CATEGORIES,
        "statuses": EVENT_STATUSES,
        "units": list(CLUB_UNIT_OPTIONS),
        "leaders": leaders,
        "default_banner": url_for("static", filename="img/login-nature.jpg"),
    }

    return {
        "agenda_events_json": json.dumps(serialized, ensure_ascii=False),
        "agenda_drawer_json": json.dumps(drawer_config, ensure_ascii=False),
        "month_stats": month_stats(month_events, today),
        "featured_event": featured_data,
        "timeline_events": timeline,
        "agenda_reminder": reminder_for_events(month_events, today),
        "events_by_date": events_by_date,
        "agenda_categories": EVENT_CATEGORIES,
        "agenda_statuses": EVENT_STATUSES,
        "agenda_units": list(CLUB_UNIT_OPTIONS),
        "agenda_leaders": leaders,
    }


@bp.route("/agenda")
def agenda_list():
    today = date.today()
    try:
        year = int(request.args.get("year") or today.year)
        month = int(request.args.get("month") or today.month)
    except (TypeError, ValueError):
        year, month = today.year, today.month
    year = max(2000, min(2100, year))
    month = max(1, min(12, month))

    month_label = f"{MONTH_NAMES_PT[month]} {year}"

    sel_raw = (request.args.get("selected") or "").strip()
    selected_day = agenda_resolve_selected_day(year, month, sel_raw, today)

    start, end = agenda_month_bounds(year, month)
    month_events = (
        _agenda_scoped_query()
        .filter(AgendaEvent.event_date >= start, AgendaEvent.event_date <= end)
        .order_by(AgendaEvent.event_date.asc(), AgendaEvent.id.asc())
        .all()
    )
    weeks = agenda_weeks(year, month)
    prev_y, prev_m = agenda_add_months(year, month, -1)
    next_y, next_m = agenda_add_months(year, month, 1)
    nav_sel_prev = agenda_clamp_day_in_month(prev_y, prev_m, selected_day.day).isoformat()
    nav_sel_next = agenda_clamp_day_in_month(next_y, next_m, selected_day.day).isoformat()

    day_events = [ev for ev in month_events if ev.event_date == selected_day]
    day_events = agenda_sort_day_events(day_events)

    view = (request.args.get("view") or "month").strip().lower()
    if view not in ("month", "week", "day"):
        view = "month"

    ctx = _agenda_page_context(
        month_events,
        year=year,
        month=month,
        selected_day=selected_day,
        today=today,
    )

    month_names_short = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    greeting_month = month_names_short[month - 1]

    return render_admin_shell(
        "admin/agenda_calendar.html",
        year=year,
        month=month,
        month_label=month_label,
        greeting_month=greeting_month,
        weeks=weeks,
        selected_day=selected_day,
        day_events=day_events,
        prev_y=prev_y,
        prev_m=prev_m,
        next_y=next_y,
        next_m=next_m,
        nav_sel_prev=nav_sel_prev,
        nav_sel_next=nav_sel_next,
        today_iso=today.isoformat(),
        agenda_view=view,
        **ctx,
    )


@bp.route("/agenda/nova", methods=["GET", "POST"])
def agenda_new():
    prefill = (request.args.get("date") or "").strip()
    today = date.today()
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_agenda"):
        if len(prefill) >= 10:
            try:
                d0 = date.fromisoformat(prefill[:10])
                return redirect(
                    url_for(
                        "admin.agenda_list",
                        year=d0.year,
                        month=d0.month,
                        selected=d0.isoformat(),
                        **_scope_kw_for_redirect(),
                    )
                )
            except ValueError:
                pass
        return redirect(
            url_for(
                "admin.agenda_list",
                year=today.year,
                month=today.month,
                selected=today.isoformat(),
                **_scope_kw_for_redirect(),
            )
        )
    back_year, back_month = today.year, today.month
    if len(prefill) >= 10:
        try:
            d0 = date.fromisoformat(prefill[:10])
            back_year, back_month = d0.year, d0.month
        except ValueError:
            pass
    if request.method == "POST":
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash("Defina o clube para agendar (super admin: ?clube_id= ou campo no formulário).", "warning")
            return redirect(url_for("admin.agenda_list", **_scope_kw_for_redirect()))
        ev = AgendaEvent(clube_id=write_cid, title="—", event_date=today)
        try:
            apply_agenda_form(ev, request.form)
            _process_agenda_banner(ev)
        except ValueError as e:
            flash(str(e), "warning")
            return redirect(
                url_for(
                    "admin.agenda_list",
                    year=back_year,
                    month=back_month,
                    selected=(prefill[:10] if prefill else today.isoformat()),
                    open_new=1,
                    **_scope_kw_for_redirect(),
                )
            )
        db.session.add(ev)
        db.session.commit()
        flash("Evento criado com sucesso!", "success")
        return redirect(
            url_for(
                "admin.agenda_list",
                year=ev.event_date.year,
                month=ev.event_date.month,
                selected=ev.event_date.isoformat(),
                **_scope_kw_for_redirect(write_cid),
            )
        )
    return redirect(
        url_for(
            "admin.agenda_list",
            year=back_year,
            month=back_month,
            selected=prefill[:10] if prefill else today.isoformat(),
            open_new=1,
            **_scope_kw_for_redirect(),
        )
    )


@bp.route("/agenda/<int:eid>/editar", methods=["GET", "POST"])
def agenda_edit(eid):
    ev = _agenda_event_for_admin(eid)
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_agenda"):
        flash("Seu cargo não permite editar eventos da agenda.", "warning")
        d = ev.event_date
        return redirect(
            url_for(
                "admin.agenda_list",
                year=d.year,
                month=d.month,
                selected=d.isoformat(),
                **_scope_kw_for_redirect(ev.clube_id),
            )
        )
    if request.method == "POST":
        try:
            apply_agenda_form(ev, request.form)
            _process_agenda_banner(ev)
        except ValueError as e:
            flash(str(e), "warning")
            return redirect(
                url_for(
                    "admin.agenda_list",
                    year=ev.event_date.year,
                    month=ev.event_date.month,
                    selected=ev.event_date.isoformat(),
                    edit=ev.id,
                    **_scope_kw_for_redirect(ev.clube_id),
                )
            )
        db.session.commit()
        flash("Evento atualizado.", "success")
        d = ev.event_date
        return redirect(
            url_for(
                "admin.agenda_list",
                year=d.year,
                month=d.month,
                selected=d.isoformat(),
                **_scope_kw_for_redirect(ev.clube_id),
            )
        )
    return redirect(
        url_for(
            "admin.agenda_list",
            year=ev.event_date.year,
            month=ev.event_date.month,
            selected=ev.event_date.isoformat(),
            edit=ev.id,
            **_scope_kw_for_redirect(ev.clube_id),
        )
    )


@bp.route("/agenda/<int:eid>/excluir", methods=["POST"])
def agenda_delete(eid):
    ev = _agenda_event_for_admin(eid)
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_agenda"):
        flash("Seu cargo não permite excluir eventos da agenda.", "warning")
        d = ev.event_date
        return redirect(
            url_for(
                "admin.agenda_list",
                year=d.year,
                month=d.month,
                selected=d.isoformat(),
                **_scope_kw_for_redirect(ev.clube_id),
            )
        )
    d = ev.event_date
    _safe_remove_upload(ev.banner_filename)
    db.session.delete(ev)
    db.session.commit()
    flash("Evento removido.", "info")
    return redirect(
        url_for(
            "admin.agenda_list",
            year=d.year,
            month=d.month,
            selected=d.isoformat(),
            **_scope_kw_for_redirect(ev.clube_id),
        )
    )


@bp.route("/membros/<int:member_id>/caderno/checklist", methods=["POST"])
def member_notebook_checklist_save(member_id):
    m = _member_for_admin(member_id)
    m.notebook_checklist_30_json = json.dumps(parse_notebook_checklist_from_form(request.form))
    db.session.commit()
    flash("Checklist do caderno (1–30) atualizado.", "success")
    return redirect(
        url_for(
            "admin.admin_activities",
            tab="desbravadores",
            membro=m.id,
            **_scope_kw_for_redirect(m.clube_id),
        )
    )


def _redirect_member_activities(member_id: int, clube_id: int | None):
    return redirect(
        url_for(
            "admin.admin_activities",
            tab="desbravadores",
            membro=member_id,
            **_scope_kw_for_redirect(clube_id),
        )
    )


@bp.route("/membros/<int:id>/atividade", methods=["GET", "POST"])
def member_activity(id):
    m = _member_for_admin(id)
    if request.method == "GET":
        return _redirect_member_activities(m.id, m.clube_id)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        category = (request.form.get("category") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None
        try:
            pct = int(request.form.get("progress_percent") or 0)
        except ValueError:
            pct = 0
        pct = max(0, min(100, pct))
        completed = request.form.get("completed") == "1"
        rec = ActivityRecord(
            member_id=m.id,
            title=title or "Atividade",
            category=category,
            notes=notes,
            progress_percent=pct,
            completed=completed,
        )
        db.session.add(rec)
        m.overall_performance = m.computed_overall_performance()
        db.session.commit()
        flash("Registro do caderno salvo.", "success")
        return _redirect_member_activities(m.id, m.clube_id)


@bp.route("/membros/<int:member_id>/atividade/<int:rec_id>/excluir", methods=["POST"])
def activity_delete(member_id, rec_id):
    m = _member_for_admin(member_id)
    rec = ActivityRecord.query.filter_by(id=rec_id, member_id=m.id).first_or_404()
    db.session.delete(rec)
    m.overall_performance = m.computed_overall_performance()
    db.session.commit()
    flash("Registro removido.", "info")
    return _redirect_member_activities(member_id, m.clube_id)


@bp.route("/membros/<int:member_id>/atividade/<int:rec_id>/concluir", methods=["POST"])
def activity_toggle_completed(member_id, rec_id):
    m = _member_for_admin(member_id)
    rec = ActivityRecord.query.filter_by(id=rec_id, member_id=m.id).first_or_404()
    rec.completed = request.form.get("completed") == "1"
    if rec.completed and rec.progress_percent < 100:
        rec.progress_percent = 100
    m.overall_performance = m.computed_overall_performance()
    db.session.commit()
    flash("Status atualizado.", "success")
    return _redirect_member_activities(member_id, m.clube_id)


@bp.route("/membros/<int:member_id>/atividade/duques", methods=["POST"])
def member_duques_add(member_id):
    m = _member_for_admin(member_id)
    md_raw = (request.form.get("meeting_date") or "").strip()
    try:
        md = date.fromisoformat(md_raw)
    except ValueError:
        flash("Informe uma data de reunião válida.", "warning")
        return _redirect_member_activities(m.id, m.clube_id)
    try:
        dq = int(request.form.get("duques") or 0)
    except ValueError:
        dq = 0
    dq = max(0, dq)
    note = (request.form.get("note") or "").strip() or None
    row = MeetingDuque(
        member_id=m.id,
        meeting_date=md,
        duques=dq,
        note=note,
    )
    db.session.add(row)
    db.session.commit()
    flash("Duques da reunião registrados.", "success")
    return _redirect_member_activities(m.id, m.clube_id)


@bp.route("/membros/<int:member_id>/atividade/duques/<int:duque_id>/excluir", methods=["POST"])
def member_duques_delete(member_id, duque_id):
    m = _member_for_admin(member_id)
    row = MeetingDuque.query.filter_by(id=duque_id, member_id=m.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash("Registro de duques removido.", "info")
    return _redirect_member_activities(m.id, m.clube_id)


def _redirect_attendance_overview(clube_id: int | None, *, meeting_date: str | None = None):
    kw = _scope_kw_for_redirect(clube_id)
    if meeting_date:
        kw["meeting_date"] = meeting_date
    return redirect(url_for("admin.attendance_overview", **kw))


@bp.route("/membros/<int:id>/presenca", methods=["GET", "POST"])
def member_attendance(id):
    m = _member_for_admin(id)
    if request.method == "GET":
        return _redirect_attendance_overview(m.clube_id)
    if request.method == "POST":
        md_raw = request.form.get("meeting_date") or ""
        try:
            md = date.fromisoformat(md_raw)
        except ValueError:
            flash("Data da reunião inválida.", "warning")
            return _redirect_attendance_overview(m.clube_id)
        from app.attendance_service import (
            normalize_attendance_status,
            sync_present_from_status,
        )

        status_raw = request.form.get("status")
        if status_raw:
            status = normalize_attendance_status(status_raw)
        else:
            status = normalize_attendance_status(
                None, present=request.form.get("present") == "1"
            )
        present = sync_present_from_status(status)
        note = (request.form.get("note") or "").strip() or None
        row = Attendance(
            member_id=m.id,
            meeting_date=md,
            present=present,
            status=status,
            note=note,
        )
        db.session.add(row)
        m.overall_performance = m.computed_overall_performance()
        db.session.commit()
        flash("Presença registrada.", "success")
        return _redirect_attendance_overview(m.clube_id, meeting_date=md.isoformat())


@bp.route("/membros/<int:member_id>/presenca/<int:att_id>/excluir", methods=["POST"])
def attendance_delete(member_id, att_id):
    m = _member_for_admin(member_id)
    row = Attendance.query.filter_by(id=att_id, member_id=m.id).first_or_404()
    db.session.delete(row)
    m.overall_performance = m.computed_overall_performance()
    db.session.commit()
    flash("Registro de presença excluído.", "info")
    return _redirect_attendance_overview(m.clube_id)


def _normalize_post_kind(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s == POST_KIND_NOTICIA:
        return POST_KIND_NOTICIA
    return POST_KIND_COMUNICADO


def _apply_publication_form_to_post(p: BoardPost, write_cid: str) -> None:
    """Formulário legado (notícias DBV) ou comunicado via drawer."""
    form_kind = (request.form.get("form_kind") or "").strip()
    if form_kind == "comunicado" or p.post_kind == POST_KIND_COMUNICADO:
        from app.communications_service import apply_comunicado_form

        p.clube_id = write_cid
        apply_comunicado_form(
            p,
            request.form,
            request.files,
            remove_image=request.form.get("remove_image") == "1",
            remove_attachment=request.form.get("remove_attachment") == "1",
        )
        return

    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    kind = _normalize_post_kind(request.form.get("post_kind"))
    p.title = title
    p.body = body
    p.post_kind = kind
    p.clube_id = write_cid
    if kind == POST_KIND_NOTICIA:
        level = (request.form.get("level") or "local").strip()
        if level not in dict(NEWS_LEVELS):
            level = "local"
        p.level = level
        if request.form.get("remove_image") == "1":
            _safe_remove_upload(p.image_filename)
            p.image_filename = None
        else:
            f = request.files.get("image")
            saved = save_upload(f, current_app.config["UPLOAD_FOLDER"], "news")
            if saved:
                _safe_remove_upload(p.image_filename)
                p.image_filename = saved
    else:
        p.level = None


def _communications_admin_context(active_filter: str) -> dict:
    from app.communications_service import build_communications_page
    from app.member_wizard import CLUB_UNIT_OPTIONS

    cid = _read_scope_clube_id()
    page = build_communications_page(
        clube_ids=None,
        clube_id=cid,
        active_filter=active_filter,
        user_id=None,
    )
    page["comms_units"] = list(CLUB_UNIT_OPTIONS)
    page["edit_post"] = None
    page["open_drawer"] = False
    return page


@bp.route("/publicacoes")
def posts():
    filt = (request.args.get("filtro") or "todos").strip().lower()
    ctx = _communications_admin_context(filt)
    edit_id = request.args.get("edit", type=int)
    if edit_id:
        p = _board_post_for_admin(edit_id)
        if p.post_kind == POST_KIND_COMUNICADO:
            from app.communications_service import serialize_post

            ctx["edit_post"] = serialize_post(p)
            ctx["open_drawer"] = True
    if request.args.get("novo"):
        ctx["open_drawer"] = True
    return render_admin_shell(
        "admin/communications_hub.html",
        admin_scope_clube_id=_read_scope_clube_id(),
        levels=NEWS_LEVELS,
        **ctx,
    )


@bp.route("/publicacoes/nova", methods=["GET", "POST"])
def post_new():
    scope_clube_id = _read_scope_clube_id()
    if request.method == "GET":
        return redirect(url_for("admin.posts", novo=1, **_scope_kw_for_redirect(scope_clube_id)))

    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    form_kind = (request.form.get("form_kind") or "comunicado").strip()
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Defina o clube (super admin: ?clube_id= ou campo oculto).", "warning")
        return redirect(url_for("admin.posts", **_scope_kw_for_redirect(scope_clube_id)))

    if form_kind == "comunicado":
        if not title or not body:
            flash("Título e descrição são obrigatórios.", "warning")
            return redirect(url_for("admin.posts", novo=1, **_scope_kw_for_redirect(write_cid)))
        from app.communications_service import apply_comunicado_form

        p = BoardPost(author_id=current_user.id, clube_id=write_cid, title=title, body=body)
        apply_comunicado_form(p, request.form, request.files)
        db.session.add(p)
        db.session.commit()
        flash("Comunicado publicado com carinho para as famílias. 💛", "success")
        return redirect(url_for("admin.posts", **_scope_kw_for_redirect(write_cid)))

    if not title or not body:
        flash("Título e texto são obrigatórios.", "warning")
        return render_admin_shell(
            "admin/post_form.html",
            post=None,
            levels=NEWS_LEVELS,
            admin_scope_clube_id=scope_clube_id,
        )
    p = BoardPost(
        title=title,
        body=body,
        author_id=current_user.id,
        clube_id=write_cid,
        post_kind=_normalize_post_kind(request.form.get("post_kind")),
    )
    if p.post_kind == POST_KIND_NOTICIA:
        level = (request.form.get("level") or "local").strip()
        p.level = level if level in dict(NEWS_LEVELS) else "local"
        f = request.files.get("image")
        saved = save_upload(f, current_app.config["UPLOAD_FOLDER"], "news")
        if saved:
            p.image_filename = saved
    else:
        p.level = None
    db.session.add(p)
    db.session.commit()
    flash("Publicação criada.", "success")
    return redirect(url_for("admin.posts", **_scope_kw_for_redirect(write_cid)))


@bp.route("/publicacoes/<int:pid>/editar", methods=["GET", "POST"])
def post_edit(pid):
    p = _board_post_for_admin(pid)
    scope_clube_id = _read_scope_clube_id()
    if p.post_kind == POST_KIND_COMUNICADO:
        if request.method == "GET":
            return redirect(
                url_for(
                    "admin.posts",
                    edit=pid,
                    **_scope_kw_for_redirect(scope_clube_id or p.clube_id),
                )
            )
        title = (request.form.get("title") or "").strip()
        body = (request.form.get("body") or "").strip()
        if not title or not body:
            flash("Título e descrição são obrigatórios.", "warning")
            return redirect(
                url_for(
                    "admin.posts",
                    edit=pid,
                    **_scope_kw_for_redirect(p.clube_id),
                )
            )
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash("Defina o clube.", "warning")
            return redirect(url_for("admin.posts", **_scope_kw_for_redirect(p.clube_id)))
        _apply_publication_form_to_post(p, write_cid)
        db.session.commit()
        flash("Comunicado atualizado.", "success")
        return redirect(url_for("admin.posts", **_scope_kw_for_redirect(p.clube_id)))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = (request.form.get("body") or "").strip()
        if not title or not body:
            flash("Título e texto são obrigatórios.", "warning")
            return render_admin_shell(
                "admin/post_form.html",
                post=p,
                levels=NEWS_LEVELS,
                admin_scope_clube_id=scope_clube_id or p.clube_id,
            )
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash("Defina o clube (super admin: ?clube_id= ou campo oculto).", "warning")
            return render_admin_shell(
                "admin/post_form.html",
                post=p,
                levels=NEWS_LEVELS,
                admin_scope_clube_id=scope_clube_id or p.clube_id,
            )
        _apply_publication_form_to_post(p, write_cid)
        db.session.commit()
        flash("Publicação atualizada.", "success")
        return redirect(url_for("admin.posts", **_scope_kw_for_redirect(p.clube_id)))
    return render_admin_shell(
        "admin/post_form.html",
        post=p,
        levels=NEWS_LEVELS,
        admin_scope_clube_id=scope_clube_id or p.clube_id,
    )


@bp.route("/publicacoes/<int:post_id>/excluir", methods=["POST"])
def post_delete(post_id):
    from app.models import BoardPostRead

    p = _board_post_for_admin(post_id)
    _safe_remove_upload(p.image_filename)
    _safe_remove_upload(p.attachment_filename)
    BoardPostRead.query.filter_by(post_id=p.id).delete(synchronize_session=False)
    db.session.delete(p)
    db.session.commit()
    flash("Publicação excluída.", "info")
    return redirect(url_for("admin.posts", **_scope_kw_for_redirect(p.clube_id)))


@bp.route("/noticias-desbravadores")
def legacy_club_news_redirect():
    return redirect(url_for("admin.posts", **request.args.to_dict()))


@bp.route("/noticias-desbravadores/nova")
def legacy_club_news_new_redirect():
    return redirect(url_for("admin.post_new", **request.args.to_dict()))


@bp.route("/noticias-desbravadores/<int:nid>/editar")
def legacy_club_news_edit_redirect(nid):
    return redirect(url_for("admin.posts", **request.args.to_dict()))


@bp.route("/diretoria")
def directorate_list():
    club_id = _read_scope_clube_id()
    perms = get_admin_panel_permissions()
    metrics = leadership_metrics(club_id)

    raw_rows = [
        serialize_directorate_member(m)
        for m in _directorate_scoped_query()
        .order_by(DirectorateMember.display_order, DirectorateMember.full_name)
        .all()
    ]
    q = (request.args.get("q") or "").strip()
    cargo_f = (request.args.get("cargo") or "").strip()
    status_f = (request.args.get("status") or "").strip()
    sort = (request.args.get("sort") or "name").strip()
    try:
        page = int(request.args.get("page") or 1)
    except ValueError:
        page = 1

    filtered = filter_team_rows(raw_rows, q=q, cargo=cargo_f, status=status_f, sort=sort)
    team_page, pagination = paginate_rows(filtered, page)

    allowed_roles = _assignable_leadership_roles()

    last_change_fmt = ""
    if metrics.get("last_change"):
        last_change_fmt = metrics["last_change"].strftime("%d/%m às %H:%M")

    return render_admin_shell(
        "admin/directorate_list.html",
        team_rows=team_page,
        team_all_count=len(raw_rows),
        pagination=pagination,
        metrics=metrics,
        metrics_last_change_fmt=last_change_fmt,
        recent_cards=recent_registrations(club_id),
        audit_log=audit_log_for_club(club_id, limit=12),
        allowed_roles=allowed_roles,
        role_permissions=get_role_permissions(club_id),
        permission_labels=PERMISSION_LABELS,
        unit_options=unit_options_for_club(club_id),
        filters={"q": q, "cargo": cargo_f, "status": status_f, "sort": sort},
        admin_scope_clube_id=club_id,
        can_assign_directorate=perms.get("can_delegate_roles"),
        can_edit_directorate_fichas=perms.get("can_manage_directorate_ui"),
    )


def _delegate_leadership_role(
    user: User,
    profile: Profile,
    scope_club_id: str,
    new_role: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    directorate_member: DirectorateMember | None = None,
) -> str | None:
    """Delega cargo no perfil + registro de histórico. Retorna mensagem de erro ou None."""
    denied = _role_assignment_denied_message(new_role)
    if denied:
        return denied
    err = validate_role_assignment(scope_club_id, new_role, exclude_user_id=user.id)
    if err:
        return err
    from app.access import cargos_for_profile
    from app.member_parent_link import parent_has_children

    old_role = profile.cargo
    roles = cargos_for_profile(profile)
    roles.discard(CARGO_PAI)
    roles.add(new_role)
    if parent_has_children(user):
        roles.add(CARGO_PAI)
    profile.clube_id = scope_club_id
    profile.cargo = new_role
    profile.cargos_json = json.dumps(sorted(roles))
    profile.email_verificado = bool(user.email_verified)
    profile.nome_completo = profile.nome_completo or user.full_name
    user.role = "admin" if new_role in {CARGO_DIRETOR, CARGO_SECRETARIO, CARGO_TESOUREIRO} else "parent"

    if directorate_member:
        directorate_member.system_role = new_role
        directorate_member.user_id = user.id
        directorate_member.delegation_start = start_date or directorate_member.delegation_start
        directorate_member.delegation_end = end_date
        directorate_member.status = "ativo"
        directorate_member.updated_at = datetime.utcnow()

    db.session.add(
        LeadershipDelegation(
            clube_id=scope_club_id,
            user_id=user.id,
            directorate_member_id=directorate_member.id if directorate_member else None,
            role_code=new_role,
            role_label=ROLE_LABELS.get(new_role, new_role),
            start_date=start_date,
            end_date=end_date,
            is_active=True,
            created_by_id=current_user.id if current_user.is_authenticated else None,
        )
    )
    actor = (current_user.full_name or current_user.email) if current_user.is_authenticated else "Sistema"
    target = user.full_name or user.email
    log_leadership_action(
        scope_club_id,
        "delegate",
        f"{actor} delegou {ROLE_LABELS.get(new_role, new_role)} para {target}",
        target_user_id=user.id,
        target_member_id=directorate_member.id if directorate_member else None,
        details={"old_role": old_role, "new_role": new_role},
    )
    return None


@bp.route("/diretoria/api/search-users")
@login_required
def directorate_api_search_users():
    cid = _read_scope_clube_id()
    q = (request.args.get("q") or "").strip()
    if not cid:
        return jsonify([])
    return jsonify(search_users_for_delegation(cid, q))


@bp.route("/diretoria/api/member/<int:member_id>")
@login_required
def directorate_api_member(member_id):
    d = _directorate_member_for_admin(member_id)
    data = serialize_member_detail(d)
    data["delegation_history"] = delegation_history_for_member(member_id)
    if d.user_id:
        user = db.session.get(User, d.user_id)
        if user:
            data["account_email"] = user.email
    return jsonify(data)


@bp.route("/diretoria/api/save", methods=["POST"])
@login_required
def directorate_api_save():
    if not _can_assign_directorate_and_delegate():
        return jsonify({"ok": False, "error": "Sem permissão para editar a equipe."}), 403
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        return jsonify({"ok": False, "error": "Defina o clube no escopo."}), 400
    mid = request.form.get("id")
    if mid:
        try:
            d = _directorate_member_for_admin(int(mid))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Membro inválido."}), 404
    else:
        name = (request.form.get("full_name") or "").strip()
        cargo = (request.form.get("cargo") or "").strip()
        if not name or not cargo:
            return jsonify({"ok": False, "error": "Nome e cargo são obrigatórios."}), 400
        d = DirectorateMember(full_name=name, cargo=cargo, clube_id=write_cid)
        db.session.add(d)
        db.session.flush()
    apply_directorate_from_form(d, request.form, request.files)
    account_email = (request.form.get("account_email") or "").strip()
    perfil_cargo = (request.form.get("perfil_cargo") or "").strip()
    denied = _role_assignment_denied_message(perfil_cargo) if perfil_cargo else None
    if denied:
        return jsonify({"ok": False, "error": denied}), 400
    if d.system_role == CARGO_DIRETOR and not is_super_admin():
        return jsonify({"ok": False, "error": _role_assignment_denied_message(CARGO_DIRETOR)}), 400
    if account_email and perfil_cargo:
        err = _link_leadership_account(account_email, d.full_name, perfil_cargo)
        if err:
            db.session.rollback()
            return jsonify({"ok": False, "error": err}), 400
        user = User.query.filter_by(email=account_email.lower()).first()
        if user:
            d.user_id = user.id
            d.system_role = perfil_cargo
    log_leadership_action(
        write_cid,
        "update" if mid else "create",
        f"Ficha de {d.full_name} {'atualizada' if mid else 'cadastrada'}",
        target_member_id=d.id,
    )
    db.session.commit()
    return jsonify({"ok": True, "member": serialize_member_detail(d)})


@bp.route("/diretoria/api/delegate", methods=["POST"])
@login_required
def directorate_api_delegate():
    if not _can_assign_directorate_and_delegate():
        return jsonify({"ok": False, "error": "Apenas o diretor pode delegar funções."}), 403
    scope_club_id = _write_clube_id_for_admin()
    if not scope_club_id:
        return jsonify({"ok": False, "error": "Defina o clube no escopo."}), 400
    try:
        user_id = int(request.form.get("user_id") or 0)
    except ValueError:
        return jsonify({"ok": False, "error": "Selecione um membro."}), 400
    new_role = (request.form.get("cargo") or "").strip()
    denied = _role_assignment_denied_message(new_role)
    if denied:
        return jsonify({"ok": False, "error": denied}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"ok": False, "error": "Usuário não encontrado."}), 404
    profile = db.session.get(Profile, user.id)
    if not profile:
        profile = Profile(id=user.id)
        db.session.add(profile)
    if not is_super_admin() and profile.clube_id and profile.clube_id != scope_club_id:
        return jsonify({"ok": False, "error": "Usuário fora do seu clube."}), 403

    start_date = end_date = None
    raw_start = (request.form.get("start_date") or "").strip()
    raw_end = (request.form.get("end_date") or "").strip()
    if raw_start:
        try:
            start_date = date.fromisoformat(raw_start)
        except ValueError:
            pass
    if raw_end:
        try:
            end_date = date.fromisoformat(raw_end)
        except ValueError:
            pass

    dm = DirectorateMember.query.filter_by(clube_id=scope_club_id, user_id=user.id).first()
    if not dm:
        dm = DirectorateMember(
            clube_id=scope_club_id,
            user_id=user.id,
            full_name=user.full_name or profile.nome_completo or user.email,
            cargo=ROLE_LABELS.get(new_role, new_role),
            system_role=new_role,
            status="ativo",
        )
        db.session.add(dm)
        db.session.flush()
    else:
        dm.cargo = ROLE_LABELS.get(new_role, new_role)

    err = _delegate_leadership_role(
        user, profile, scope_club_id, new_role,
        start_date=start_date, end_date=end_date, directorate_member=dm,
    )
    if err:
        db.session.rollback()
        return jsonify({"ok": False, "error": err}), 400
    db.session.commit()
    return jsonify({"ok": True, "member": serialize_directorate_member(dm)})


@bp.route("/diretoria/api/permissions", methods=["GET", "POST"])
@login_required
def directorate_api_permissions():
    if not _can_assign_directorate_and_delegate():
        if request.method == "GET":
            return jsonify({"ok": False, "error": "Sem permissão."}), 403
        return jsonify({"ok": False, "error": "Sem permissão."}), 403
    cid = _write_clube_id_for_admin() or _read_scope_clube_id()
    if not cid:
        return jsonify({"ok": False, "error": "Defina o clube."}), 400
    if request.method == "GET":
        perms = get_role_permissions(cid)
        return jsonify({"ok": True, "permissions": perms, "labels": PERMISSION_LABELS})
    data = request.get_json(silent=True) or {}
    perms_in = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
    save_role_permissions(cid, perms_in)
    log_leadership_action(cid, "permissions", "Permissões por cargo atualizadas")
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/diretoria/permissoes", methods=["POST"])
def directorate_permissions():
    if not _can_assign_directorate_and_delegate():
        flash("Apenas o diretor ou o super admin pode delegar funções da liderança.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    email = (request.form.get("email") or "").strip().lower()
    new_role = (request.form.get("cargo") or "").strip()
    denied = _role_assignment_denied_message(new_role)
    if not email or denied:
        flash(denied or "Informe e-mail e função válidos.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(request.form.get("clube_id"))))
    profile = db.session.get(Profile, user.id)
    if not profile:
        profile = Profile(id=user.id)
        db.session.add(profile)
    scope_club_id = _write_clube_id_for_admin()
    if not scope_club_id:
        flash("Defina o clube (super admin: use ?clube_id= na URL ou campo no formulário).", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    if not is_super_admin() and profile.clube_id and profile.clube_id != scope_club_id:
        flash("Você não pode alterar permissões de usuários fora do seu clube.", "danger")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(scope_club_id)))
    err = _delegate_leadership_role(user, profile, scope_club_id, new_role)
    if err:
        flash(err, "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(scope_club_id)))
    db.session.commit()
    flash("Permissão atualizada com sucesso.", "success")
    return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(scope_club_id)))


@bp.route("/diretoria/novo", methods=["GET", "POST"])
def directorate_new():
    if not _can_assign_directorate_and_delegate():
        flash("Apenas o diretor ou o super admin pode cadastrar ou alterar membros da equipe da diretoria.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    leadership_roles = _leadership_roles_for_directorate_form()
    if request.method == "POST":
        name = (request.form.get("full_name") or "").strip()
        cargo = (request.form.get("cargo") or "").strip()
        account_email = (request.form.get("account_email") or "").strip()
        perfil_cargo = (request.form.get("perfil_cargo") or "").strip()
        if not name or not cargo:
            flash("Nome e cargo são obrigatórios.", "warning")
            return render_admin_shell(
                "admin/directorate_form.html",
                m=None,
                leadership_roles=leadership_roles,
            )
        if account_email and not perfil_cargo:
            flash("Selecione a função no sistema para vincular ao e-mail.", "warning")
            return render_admin_shell(
                "admin/directorate_form.html",
                m=None,
                leadership_roles=leadership_roles,
            )
        if perfil_cargo and not account_email:
            flash("Informe o e-mail para vincular a função no sistema.", "warning")
            return render_admin_shell(
                "admin/directorate_form.html",
                m=None,
                leadership_roles=leadership_roles,
            )
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash("Defina o clube (super admin: ?clube_id= na URL ou campo no formulário).", "warning")
            return render_admin_shell(
                "admin/directorate_form.html",
                m=None,
                leadership_roles=leadership_roles,
            )
        d = DirectorateMember(full_name=name, cargo=cargo, clube_id=write_cid)
        apply_directorate_from_form(d, request.form, request.files)
        db.session.add(d)
        db.session.flush()
        err = _link_leadership_account(account_email, name, perfil_cargo)
        if err:
            db.session.rollback()
            flash(err, "danger")
            return render_admin_shell(
                "admin/directorate_form.html",
                m=None,
                leadership_roles=leadership_roles,
            )
        db.session.commit()
        if account_email and perfil_cargo:
            flash(
                "Membro cadastrado e acesso ao portal vinculado. "
                "O usuário verá as telas da função escolhida após definir a senha (e-mail com link, se o servidor de e-mail estiver ativo).",
                "success",
            )
        else:
            flash("Membro da diretoria cadastrado.", "success")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(write_cid)))
    return render_admin_shell(
        "admin/directorate_form.html", m=None, leadership_roles=leadership_roles
    )


@bp.route("/diretoria/<int:id>/editar", methods=["GET", "POST"])
def directorate_edit(id):
    if not _can_assign_directorate_and_delegate():
        flash("Apenas o diretor ou o super admin pode cadastrar ou alterar membros da equipe da diretoria.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    leadership_roles = _leadership_roles_for_directorate_form()
    d = _directorate_member_for_admin(id)
    if request.method == "POST":
        account_email = (request.form.get("account_email") or "").strip()
        perfil_cargo = (request.form.get("perfil_cargo") or "").strip()
        if account_email and not perfil_cargo:
            flash("Selecione a função no sistema para vincular ao e-mail.", "warning")
            return render_admin_shell(
                "admin/directorate_form.html", m=d, leadership_roles=leadership_roles
            )
        if perfil_cargo and not account_email:
            flash("Informe o e-mail para vincular a função no sistema.", "warning")
            return render_admin_shell(
                "admin/directorate_form.html", m=d, leadership_roles=leadership_roles
            )
        apply_directorate_from_form(d, request.form, request.files)
        err = _link_leadership_account(account_email, d.full_name, perfil_cargo)
        if err:
            db.session.rollback()
            flash(err, "danger")
            return render_admin_shell(
                "admin/directorate_form.html", m=d, leadership_roles=leadership_roles
            )
        db.session.commit()
        if account_email and perfil_cargo:
            flash(
                "Dados atualizados e acesso ao portal vinculado a este e-mail e função.",
                "success",
            )
        else:
            flash("Dados atualizados.", "success")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(d.clube_id)))
    return render_admin_shell(
        "admin/directorate_form.html", m=d, leadership_roles=leadership_roles
    )


@bp.route("/diretoria/<int:id>/excluir", methods=["POST"])
def directorate_delete(id):
    if not _can_assign_directorate_and_delegate():
        flash("Apenas o diretor ou o super admin pode excluir registros da equipe da diretoria.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    d = _directorate_member_for_admin(id)
    cid = d.clube_id
    name = d.full_name
    log_leadership_action(
        cid,
        "delete",
        f"Membro {name} removido da equipe da diretoria",
        target_member_id=d.id,
        target_user_id=d.user_id,
    )
    _safe_remove_upload(d.photo_filename)
    db.session.delete(d)
    db.session.commit()
    flash("Registro removido.", "info")
    return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(cid)))


# ---------- Financeiro ----------


@bp.route("/financeiro")
def finance_dashboard():
    perms = get_admin_panel_permissions()
    if not perms.get("can_view_finance"):
        flash("Seu cargo não permite acessar o financeiro.", "warning")
        return redirect(route_for_user(current_user))
    cid = _read_scope_clube_id()
    if not cid:
        ctx = build_finance_dashboard("", "Clube")
        ctx["summary"] = {
            "balance_cents": 0,
            "month_in_cents": 0,
            "month_out_cents": 0,
            "pending_cents": 0,
            "pending_count": 0,
            "overdue_count": 0,
            "month_in_delta_pct": None,
            "month_out_delta_pct": None,
            "cash_status": "positivo",
        }
        return render_admin_shell(
            "admin/finance_dashboard.html",
            fin=ctx,
            format_brl=format_brl_cents,
            admin_scope_clube_id=cid,
            can_write_finance=perms.get("can_write_finance"),
        )
    club = db.session.get(Club, cid)
    club_name = club.nome if club else "Clube"
    fin = build_finance_dashboard(cid, club_name)
    return render_admin_shell(
        "admin/finance_dashboard.html",
        fin=fin,
        format_brl=format_brl_cents,
        admin_scope_clube_id=cid,
        can_write_finance=perms.get("can_write_finance"),
    )


@bp.route("/financeiro/chave-pix", methods=["POST"])
def finance_pix_key_save():
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    raw = (request.form.get("pix_key") or "").strip()
    if len(raw) > 500:
        flash("Chave PIX muito longa (máx. 500 caracteres).", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect()))
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Defina o clube (super admin: ?clube_id=).", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect()))
    set_pix_for_club(write_cid, raw)
    db.session.commit()
    flash(
        "Chave PIX atualizada. Os responsáveis passam a ver a nova chave no portal família."
        if raw
        else "Chave PIX removida do portal família.",
        "success",
    )
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))


@bp.route("/financeiro/lancamento", methods=["POST"])
def finance_ledger_add():
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    direction = (request.form.get("direction") or "").strip()
    if direction not in ("income", "expense"):
        flash("Tipo de lançamento inválido.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect()))
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Defina o clube (super admin: ?clube_id=).", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect()))
    amt = parse_money_brl(request.form.get("amount") or "")
    if amt is None or amt <= 0:
        flash("Informe um valor válido.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
    desc = (request.form.get("description") or "").strip()
    if not desc:
        flash("Descrição é obrigatória.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
    raw_date = (request.form.get("occurred_at") or "").strip()
    try:
        occurred = date.fromisoformat(raw_date) if raw_date else date.today()
    except ValueError:
        occurred = date.today()
    cat = (request.form.get("category") or "").strip() or None
    mid_raw = (request.form.get("member_id") or "").strip()
    mid = None
    if mid_raw and mid_raw != "0":
        try:
            mid_int = int(mid_raw)
        except (TypeError, ValueError):
            flash("Desbravador inválido.", "warning")
            return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
        m = db.session.get(Member, mid_int)
        if not m or m.clube_id != write_cid:
            flash("Desbravador não encontrado neste clube.", "warning")
            return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
        mid = m.id
    notes = (request.form.get("notes") or "").strip() or None
    cat_norm = cat[:120] if cat else None
    if cat_norm and cat_norm not in FEE_CATEGORIES:
        cat_norm = "outros"
    row = FinanceLedgerEntry(
        occurred_at=occurred,
        direction=direction,
        amount_cents=amt,
        description=desc[:400],
        category=cat_norm,
        notes=notes,
        member_id=mid,
        clube_id=write_cid,
        created_by_id=current_user.id,
    )
    f = request.files.get("attachment")
    saved = save_document_upload(f, current_app.config["UPLOAD_FOLDER"], "finance")
    if saved:
        row.attachment_filename = saved
    db.session.add(row)
    log_finance_action(
        write_cid,
        "ledger_add",
        user_id=current_user.id,
        entity_type="ledger",
        details={"direction": direction, "amount_cents": amt, "description": desc[:80]},
    )
    db.session.commit()
    flash("Lançamento registrado.", "success")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))


@bp.route("/financeiro/lancamento/<int:lid>/excluir", methods=["POST"])
def finance_ledger_delete(lid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    row = _finance_ledger_for_admin(lid)
    cid = row.clube_id
    db.session.delete(row)
    log_finance_action(
        cid,
        "ledger_delete",
        user_id=current_user.id,
        entity_type="ledger",
        entity_id=lid,
        details={"description": row.description, "amount_cents": row.amount_cents},
    )
    db.session.commit()
    flash("Lançamento removido.", "info")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(cid)))


@bp.route("/financeiro/mensalidade", methods=["POST"])
def finance_fee_add():
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Defina o clube (super admin: ?clube_id=).", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect()))
    send_all = (request.form.get("send_to_all") or "").strip() in ("1", "true", "on", "yes")
    amt = parse_money_brl(request.form.get("amount") or "")
    if amt is None or amt <= 0:
        flash("Informe um valor válido para a cobrança.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
    title = (request.form.get("title") or "").strip() or "Mensalidade"
    raw_due = (request.form.get("due_date") or "").strip()
    try:
        due = date.fromisoformat(raw_due) if raw_due else date.today()
    except ValueError:
        due = date.today()
    notes = (request.form.get("notes") or "").strip() or None
    cat = (request.form.get("category") or "mensalidade").strip()
    if cat not in FEE_CATEGORIES:
        cat = "mensalidade"
    disc = parse_money_brl(request.form.get("discount") or "") or 0
    fine = parse_money_brl(request.form.get("fine") or "") or 0
    inst = max(1, min(int(request.form.get("installments") or 1), 12))

    if send_all:
        created = generate_fees_bulk(
            write_cid,
            amount_cents=amt,
            due_date=due,
            title=title[:200],
            category=cat,
            discount_cents=disc,
            fine_cents=fine,
            installments=inst,
        )
        log_finance_action(
            write_cid,
            "fees_bulk",
            user_id=current_user.id,
            details={"count": len(created), "title": title, "via": "fee_form"},
        )
        db.session.commit()
        flash(f"Cobrança enviada para {len(created)} desbravador(es).", "success")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))

    try:
        mid = int(request.form.get("member_id") or 0)
    except (TypeError, ValueError):
        mid = 0
    m = db.session.get(Member, mid)
    if not m or m.clube_id != write_cid:
        flash("Selecione um desbravador deste clube.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
    if inst > 1:
        created = generate_fees_bulk(
            write_cid,
            amount_cents=amt,
            due_date=due,
            title=title[:200],
            category=cat,
            member_ids=[m.id],
            discount_cents=disc,
            fine_cents=fine,
            installments=inst,
        )
        log_finance_action(
            write_cid,
            "fee_add_installments",
            user_id=current_user.id,
            entity_type="fee",
            details={"count": len(created), "member_id": m.id},
        )
    else:
        fee = MemberFee(
            member_id=m.id,
            title=title[:200],
            category=cat,
            amount_cents=amt,
            discount_cents=disc,
            fine_cents=fine,
            due_date=due,
            notes=notes,
        )
        db.session.add(fee)
        db.session.flush()
        log_finance_action(
            write_cid,
            "fee_add",
            user_id=current_user.id,
            entity_type="fee",
            entity_id=fee.id,
            details={"member_id": m.id, "amount_cents": amt},
        )
    db.session.commit()
    flash("Cobrança criada para o desbravador.", "success")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))


@bp.route("/financeiro/mensalidade/<int:fid>/paga", methods=["POST"])
def finance_fee_mark_paid(fid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    fee = _member_fee_for_admin(fid)
    if fee.paid_at:
        m0 = db.session.get(Member, fee.member_id)
        flash("Esta cobrança já está marcada como paga.", "info")
        return redirect(
            url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m0.clube_id if m0 else None))
        )
    fee.paid_at = datetime.utcnow()
    fee.status = None
    m = db.session.get(Member, fee.member_id)
    ledger_row = credit_fee_to_ledger(fee, user_id=current_user.id)
    log_finance_action(
        m.clube_id if m else None,
        "fee_mark_paid",
        user_id=current_user.id,
        entity_type="fee",
        entity_id=fee.id,
        details={"ledger_id": ledger_row.id if ledger_row else None},
    )
    db.session.commit()
    flash(
        "Pagamento confirmado com o botão Paga. O valor foi somado ao caixa do clube.",
        "success",
    )
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))


@bp.route("/financeiro/mensalidade/<int:fid>/excluir", methods=["POST"])
def finance_fee_delete(fid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    fee = _member_fee_for_admin(fid)
    m = db.session.get(Member, fee.member_id)
    linked = FinanceLedgerEntry.query.filter_by(member_fee_id=fee.id).first()
    if linked:
        db.session.delete(linked)
    db.session.delete(fee)
    log_finance_action(
        m.clube_id if m else None,
        "fee_delete",
        user_id=current_user.id,
        entity_type="fee",
        entity_id=fid,
    )
    db.session.commit()
    flash("Cobrança removida.", "info")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))


@bp.route("/financeiro/mensalidades/gerar-lote", methods=["POST"])
def finance_fees_bulk():
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    write_cid = _write_clube_id_for_admin()
    if not write_cid:
        flash("Defina o clube.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect()))
    amt = parse_money_brl(request.form.get("amount") or "")
    if amt is None or amt <= 0:
        flash("Valor inválido.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
    raw_due = (request.form.get("due_date") or "").strip()
    try:
        due = date.fromisoformat(raw_due) if raw_due else date.today()
    except ValueError:
        due = date.today()
    title = (request.form.get("title") or "").strip() or "Mensalidade"
    cat = (request.form.get("category") or "mensalidade").strip()
    inst = max(1, min(int(request.form.get("installments") or 1), 12))
    created = generate_fees_bulk(
        write_cid,
        amount_cents=amt,
        due_date=due,
        title=title[:200],
        category=cat,
        discount_cents=parse_money_brl(request.form.get("discount") or "") or 0,
        fine_cents=parse_money_brl(request.form.get("fine") or "") or 0,
        installments=inst,
    )
    log_finance_action(
        write_cid,
        "fees_bulk",
        user_id=current_user.id,
        details={"count": len(created), "title": title},
    )
    db.session.commit()
    flash(f"Mensalidades geradas para {len(created)} registro(s).", "success")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))


@bp.route("/financeiro/comprovante/<int:proof_id>/aprovar", methods=["POST"])
def finance_proof_approve(proof_id):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Sem permissão.", "warning")
        return redirect(route_for_user(current_user))
    proof = db.session.get(PaymentProof, proof_id)
    if not proof:
        abort(404)
    fee = proof.fee
    m = db.session.get(Member, fee.member_id) if fee else None
    if m and _read_scope_clube_id() and m.clube_id != _read_scope_clube_id():
        abort(404)
    proof.status = PROOF_STATUS_APPROVED
    proof.reviewed_by_id = current_user.id
    proof.reviewed_at = datetime.utcnow()
    proof.review_note = (request.form.get("review_note") or "").strip() or None
    log_finance_action(
        m.clube_id if m else None,
        "proof_approved",
        user_id=current_user.id,
        entity_type="proof",
        entity_id=proof.id,
    )
    db.session.commit()
    flash(
        "Comprovante validado. Confirme o pagamento clicando em Pago na cobrança, se o valor foi recebido.",
        "success",
    )
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))


@bp.route("/financeiro/comprovante/<int:proof_id>/rejeitar", methods=["POST"])
def finance_proof_reject(proof_id):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Sem permissão.", "warning")
        return redirect(route_for_user(current_user))
    proof = db.session.get(PaymentProof, proof_id)
    if not proof:
        abort(404)
    fee = proof.fee
    m = db.session.get(Member, fee.member_id) if fee else None
    if m and _read_scope_clube_id() and m.clube_id != _read_scope_clube_id():
        abort(404)
    proof.status = PROOF_STATUS_REJECTED
    proof.reviewed_by_id = current_user.id
    proof.reviewed_at = datetime.utcnow()
    proof.review_note = (request.form.get("review_note") or "").strip() or "Comprovante não validado."
    log_finance_action(
        m.clube_id if m else None,
        "proof_rejected",
        user_id=current_user.id,
        entity_type="proof",
        entity_id=proof.id,
    )
    db.session.commit()
    flash("Comprovante rejeitado.", "info")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))


@bp.route("/financeiro/comprovante/<int:proof_id>/revisao", methods=["POST"])
def finance_proof_revision(proof_id):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Sem permissão.", "warning")
        return redirect(route_for_user(current_user))
    proof = db.session.get(PaymentProof, proof_id)
    if not proof:
        abort(404)
    proof.status = PROOF_STATUS_REVISION
    proof.reviewed_by_id = current_user.id
    proof.reviewed_at = datetime.utcnow()
    proof.review_note = (request.form.get("review_note") or "").strip() or "Envie um novo comprovante, por favor."
    fee = proof.fee
    m = db.session.get(Member, fee.member_id) if fee else None
    log_finance_action(
        m.clube_id if m else None,
        "proof_revision",
        user_id=current_user.id,
        entity_type="proof",
        entity_id=proof.id,
    )
    db.session.commit()
    flash("Solicitação de revisão enviada ao responsável.", "info")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))


@bp.route("/financeiro/relatorio")
def finance_report():
    perms = get_admin_panel_permissions()
    if not perms.get("can_view_finance"):
        flash("Sem permissão.", "warning")
        return redirect(route_for_user(current_user))
    cid = _read_scope_clube_id()
    if not cid:
        flash("Defina o clube.", "warning")
        return redirect(url_for("admin.finance_dashboard"))
    fmt = (request.args.get("format") or "csv").strip().lower()
    start_s = request.args.get("de") or ""
    end_s = request.args.get("ate") or ""
    try:
        start = date.fromisoformat(start_s) if start_s else date.today().replace(day=1)
    except ValueError:
        start = date.today().replace(day=1)
    try:
        end = date.fromisoformat(end_s) if end_s else date.today()
    except ValueError:
        end = date.today()

    ledger = (
        finance_ledger_query(cid)
        .filter(FinanceLedgerEntry.occurred_at >= start, FinanceLedgerEntry.occurred_at <= end)
        .order_by(FinanceLedgerEntry.occurred_at.asc())
        .all()
    )
    fees = (
        MemberFee.query.join(Member, Member.id == MemberFee.member_id)
        .filter(Member.clube_id == cid)
        .order_by(MemberFee.due_date.asc())
        .all()
    )

    if fmt == "xlsx":
        try:
            from io import BytesIO

            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "Lançamentos"
            ws.append(["Data", "Tipo", "Valor", "Descrição", "Categoria"])
            for r in ledger:
                ws.append(
                    [
                        r.occurred_at.isoformat(),
                        "Entrada" if r.direction == "income" else "Saída",
                        r.amount_cents / 100,
                        r.description,
                        r.category or "",
                    ]
                )
            ws2 = wb.create_sheet("Cobranças")
            ws2.append(["Desbravador", "Título", "Valor", "Vencimento", "Status"])
            today = date.today()
            for f in fees:
                ws2.append(
                    [
                        f.member.full_name if f.member else "",
                        f.title,
                        f.effective_amount_cents() / 100,
                        f.due_date.isoformat(),
                        f.computed_status(today),
                    ]
                )
            buf = BytesIO()
            wb.save(buf)
            buf.seek(0)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"financeiro_{cid[:8]}_{start.isoformat()}.xlsx",
            )
        except ImportError:
            fmt = "csv"

    lines = ["Data,Tipo,Valor,Descrição,Categoria"]
    for r in ledger:
        lines.append(
            f"{r.occurred_at.isoformat()},{'Entrada' if r.direction == 'income' else 'Saída'},"
            f"{r.amount_cents / 100:.2f},{r.description.replace(',', ';')},{r.category or ''}"
        )
    lines.append("")
    lines.append("Desbravador,Título,Valor,Vencimento,Status")
    today = date.today()
    for f in fees:
        lines.append(
            f"{(f.member.full_name if f.member else '').replace(',', ';')},{f.title.replace(',', ';')},"
            f"{f.effective_amount_cents() / 100:.2f},{f.due_date.isoformat()},{f.computed_status(today)}"
        )
    body = "\n".join(lines)
    return Response(
        body,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=financeiro_{start.isoformat()}.csv"},
    )
