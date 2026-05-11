import json
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, request, url_for
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
from app.models import (
    ActivityRecord,
    AgendaEvent,
    Attendance,
    BoardPost,
    DirectorateMember,
    FinanceLedgerEntry,
    MeetingDuque,
    Member,
    MemberFee,
    PasswordResetToken,
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
)
from app.uploads_util import save_upload

bp = Blueprint("admin", __name__)

# Cadernos de atividades (classes regulares dos Desbravadores — apenas estas opções na ficha)
NOTEBOOK_ACTIVITY_OPTIONS = (
    "Amigo",
    "Companheiro",
    "Pesquisador",
    "Pioneiro",
    "Excursionista",
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
    q = db.session.query(User).join(Profile, Profile.id == User.id).filter(User.role == "parent")
    club_id = _read_scope_clube_id()
    if club_id:
        q = q.filter(Profile.clube_id == club_id)
    elif is_super_admin():
        q = q.filter(false())
    else:
        q = q.filter(false())
    return q.order_by(User.created_at.desc()).all()


def _admin_scope_clube_id() -> str | None:
    if is_super_admin():
        return None
    return current_clube_id()


def _read_scope_clube_id() -> str | None:
    """Escopo de leitura/listagens no painel admin. Super admin deve usar ?clube_id= (evita misturar clubes)."""
    if is_super_admin():
        return (request.args.get("clube_id") or request.form.get("clube_id") or "").strip() or None
    return current_clube_id()


def _write_clube_id_for_admin() -> str | None:
    """Clube usado em criações (membros, agenda, etc.). Super admin pode passar clube_id no form/query."""
    cid = _admin_scope_clube_id()
    if cid:
        return cid
    if is_super_admin():
        return (request.form.get("clube_id") or request.args.get("clube_id") or "").strip() or None
    return None


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
    cid = (clube_id or request.args.get("clube_id") or request.form.get("clube_id") or "").strip()
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
    profile.clube_id = scope_club_id
    profile.cargo = perfil_cargo
    try:
        import json

        profile.cargos_json = json.dumps(sorted({perfil_cargo}))
    except Exception:
        profile.cargos_json = None
    profile.nome_completo = (full_name or "").strip() or profile.nome_completo or user.full_name
    profile.email_verificado = bool(user.email_verified)
    user.role = "admin" if perfil_cargo == CARGO_DIRETOR else "parent"
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


def parse_parent_id(raw):
    if raw is None or raw == "" or raw == "0":
        return None
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        return None
    p, prof = _user_profile_if_in_scope(pid)
    if not p or p.role != "parent" or not prof:
        return None
    return pid


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
    # Controle de vínculo (pai/mãe) é restrito por cargo.
    perms = get_admin_panel_permissions()
    can_manage_member_links = bool(perms.get("can_manage_member_links"))

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
            "Selecione o caderno de atividades: Amigo, Companheiro, Pesquisador, Pioneiro, Excursionista ou Clube de líderes."
        )
    m.notebook_current = nb
    # Conselheiro/Tesouraria/secretaria (conforme cargo) não devem conseguir alterar vínculo via formulário.
    if can_manage_member_links:
        m.parent_id = parse_parent_id(form.get("parent_id"))
    m.overall_performance = m.computed_overall_performance()


def _can_assign_directorate_and_delegate():
    if is_super_admin() or CARGO_DIRETOR in current_cargos():
        return True
    # Fallback para contas admin legadas com perfil inconsistênte no banco.
    return bool(getattr(current_user, "is_admin", None) and current_user.is_admin())


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
    )


@bp.route("/responsaveis")
def parents_list():
    parents = parent_users_query()
    rows = []
    for p in parents:
        kids = list(p.children)
        rows.append({"user": p, "children": kids, "n_children": len(kids)})
    cid = _read_scope_clube_id()
    return render_admin_shell("admin/parents_list.html", rows=rows, admin_scope_clube_id=cid)


@bp.route("/responsaveis/<int:user_id>", methods=["GET", "POST"])
def parent_detail(user_id):
    p, p_profile = _user_profile_if_in_scope(user_id)
    if not p or p.role != "parent" or not p_profile:
        flash("Responsável não encontrado.", "danger")
        return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))

    if request.method == "POST":
        perms = get_admin_panel_permissions()
        action = request.form.get("action")
        if action in {"link", "unlink"} and not perms.get("can_manage_member_links"):
            flash("Seu cargo não permite gerenciar vínculos.", "warning")
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
            if p_profile.clube_id and m.clube_id != p_profile.clube_id:
                flash("Este desbravador não pertence ao mesmo clube do responsável.", "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            if m.parent_id is not None and m.parent_id != p.id:
                flash("Este desbravador já está vinculado a outro responsável.", "warning")
                return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
            m.parent_id = p.id
            db.session.commit()
            flash("Vínculo criado.", "success")
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
                m.parent_id = None
                db.session.commit()
                flash("Vínculo removido.", "info")
            return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))

    linked = list(p.children)
    unlinked = (
        _members_scoped_query()
        .filter(Member.parent_id.is_(None))
        .order_by(Member.full_name)
        .all()
    )
    return render_admin_shell(
        "admin/parent_detail.html",
        parent_user=p,
        linked=linked,
        unlinked=unlinked,
        admin_scope_clube_id=_read_scope_clube_id() or p_profile.clube_id,
    )


@bp.route("/responsaveis/<int:user_id>/excluir", methods=["POST"])
def parent_delete(user_id):
    p, p_profile = _user_profile_if_in_scope(user_id)
    if not p or p.role != "parent" or not p_profile:
        flash("Conta não encontrada.", "danger")
        return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect()))
    perms = get_admin_panel_permissions()
    if not perms.get("can_delete_parent_accounts"):
        flash("Seu cargo não permite excluir conta de responsável.", "warning")
        return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect(p_profile.clube_id)))
    if current_user.id == p.id:
        flash("Você não pode excluir a própria conta por este painel.", "danger")
        return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
    # Tabela legada (confirmação por e-mail removida do código) ainda pode existir no SQLite e bloquear o DELETE
    try:
        with db.session.begin_nested():
            db.session.execute(
                text("DELETE FROM email_confirmation_tokens WHERE user_id = :uid"),
                {"uid": p.id},
            )
    except Exception:
        pass
    mq = Member.query.filter_by(parent_id=p.id)
    cid_scope = p_profile.clube_id if p_profile else None
    if cid_scope:
        mq = mq.filter(Member.clube_id == cid_scope)
    for m in mq.all():
        m.parent_id = None
    if cid_scope:
        BoardPost.query.filter_by(author_id=p.id, clube_id=cid_scope).update(
            {BoardPost.author_id: None}, synchronize_session=False
        )
    else:
        BoardPost.query.filter_by(author_id=p.id).update({BoardPost.author_id: None}, synchronize_session=False)
    PasswordResetToken.query.filter_by(user_id=p.id).delete()
    profile_to_delete = db.session.get(Profile, p.id)
    if profile_to_delete:
        db.session.delete(profile_to_delete)
    try:
        db.session.delete(p)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            "Não foi possível excluir esta conta: ainda existem registros ligados a ela no banco de dados. "
            "Tente novamente ou peça suporte técnico.",
            "danger",
        )
        return redirect(url_for("admin.parent_detail", user_id=user_id, **_scope_kw_for_redirect()))
    flash(
        "Conta do responsável excluída. Os desbravadores permanecem no sistema, sem vínculo com esta conta.",
        "info",
    )
    return redirect(url_for("admin.parents_list", **_scope_kw_for_redirect(cid_scope)))


@bp.route("/presencas")
def attendance_overview():
    members = _members_scoped_query().order_by(Member.full_name).all()
    stats = []
    for m in members:
        pr, tot, pct = m.attendance_stats()
        last = (
            Attendance.query.filter_by(member_id=m.id)
            .order_by(Attendance.meeting_date.desc())
            .first()
        )
        stats.append(
            {
                "member": m,
                "present": pr,
                "total": tot,
                "rate": pct if tot else None,
                "last_meeting": last.meeting_date if last else None,
            }
        )
    return render_admin_shell("admin/attendance_overview.html", stats=stats)


@bp.route("/membros")
def members():
    rows = _members_scoped_query().order_by(Member.full_name).all()
    cid = _read_scope_clube_id()
    return render_admin_shell(
        "admin/members.html",
        members=rows,
        format_cpf_display=format_cpf_display,
        admin_scope_clube_id=cid,
    )


def _member_form_ctx(member, parents):
    opts = list(NOTEBOOK_ACTIVITY_OPTIONS)
    if member and member.notebook_current:
        cur = (member.notebook_current or "").strip()
        if cur and cur not in opts:
            opts = [cur] + opts
    ctx = dict(member=member, parent_users=parents, notebook_options=opts)
    if is_super_admin():
        ctx["clubs"] = Club.query.order_by(Club.nome.asc()).all()
        ctx["show_clube_picker"] = member is None
    else:
        ctx["clubs"] = []
        ctx["show_clube_picker"] = False
    return ctx


@bp.route("/membros/novo", methods=["GET", "POST"])
def member_new():
    parents = parent_users_query()
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
            return render_admin_shell("admin/member_form.html", **_member_form_ctx(None, parents))
        m = Member(full_name="—", clube_id=write_cid)
        try:
            apply_member_form(m, request.form)
        except ValueError as e:
            flash(str(e), "warning")
            return render_admin_shell("admin/member_form.html", **_member_form_ctx(None, parents))
        db.session.add(m)
        db.session.flush()
        _process_member_photo(m)
        db.session.commit()
        flash("Desbravador cadastrado.", "success")
        return redirect(url_for("admin.member_edit", id=m.id, **_scope_kw_for_redirect(m.clube_id)))

    return render_admin_shell(
        "admin/member_form.html", **_member_form_ctx(None, parents)
    )


@bp.route("/membros/<int:id>/editar", methods=["GET", "POST"])
def member_edit(id):
    m = _member_for_admin(id)
    parents = parent_users_query()
    if request.method == "POST":
        try:
            apply_member_form(m, request.form, member_id_exclude=m.id)
        except ValueError as e:
            flash(str(e), "warning")
            return render_admin_shell("admin/member_form.html", **_member_form_ctx(m, parents))
        _process_member_photo(m)
        db.session.commit()
        flash("Dados atualizados.", "success")
        return redirect(url_for("admin.member_edit", id=m.id, **_scope_kw_for_redirect(m.clube_id)))
    return render_admin_shell("admin/member_form.html", **_member_form_ctx(m, parents))


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
    Attendance.query.filter_by(member_id=m.id).delete()
    MeetingDuque.query.filter_by(member_id=m.id).delete()
    _safe_remove_upload(m.photo_filename)
    db.session.delete(m)
    db.session.commit()
    flash("Desbravador removido do sistema.", "info")
    return redirect(url_for("admin.members", **_scope_kw_for_redirect(m.clube_id)))


def _parse_agenda_form(form):
    title = (form.get("title") or "").strip()
    if not title:
        raise ValueError("Título é obrigatório.")
    body = (form.get("body") or "").strip() or None
    d_raw = (form.get("event_date") or "").strip()
    if not d_raw:
        raise ValueError("Data é obrigatória.")
    try:
        evd = date.fromisoformat(d_raw)
    except ValueError:
        raise ValueError("Data inválida.")
    tm = (form.get("event_time") or "").strip() or None
    if tm and len(tm) > 8:
        tm = tm[:8]
    return title, body, evd, tm


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
    events_by_date: dict[str, list] = {}
    for ev in month_events:
        key = ev.event_date.isoformat()
        events_by_date.setdefault(key, []).append(ev)

    weeks = agenda_weeks(year, month)
    prev_y, prev_m = agenda_add_months(year, month, -1)
    next_y, next_m = agenda_add_months(year, month, 1)
    nav_sel_prev = agenda_clamp_day_in_month(prev_y, prev_m, selected_day.day).isoformat()
    nav_sel_next = agenda_clamp_day_in_month(next_y, next_m, selected_day.day).isoformat()

    day_events = [ev for ev in month_events if ev.event_date == selected_day]
    day_events = agenda_sort_day_events(day_events)

    return render_admin_shell(
        "admin/agenda_calendar.html",
        year=year,
        month=month,
        month_label=month_label,
        weeks=weeks,
        events_by_date=events_by_date,
        selected_day=selected_day,
        day_events=day_events,
        prev_y=prev_y,
        prev_m=prev_m,
        next_y=next_y,
        next_m=next_m,
        nav_sel_prev=nav_sel_prev,
        nav_sel_next=nav_sel_next,
        today_iso=today.isoformat(),
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
        try:
            title, body, evd, tm = _parse_agenda_form(request.form)
        except ValueError as e:
            flash(str(e), "warning")
            return render_admin_shell(
                "admin/agenda_form.html",
                ev=None,
                prefill_date=prefill or None,
                back_year=back_year,
                back_month=back_month,
            )
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash("Defina o clube para agendar (super admin: ?clube_id= ou campo no formulário).", "warning")
            return render_admin_shell(
                "admin/agenda_form.html",
                ev=None,
                prefill_date=prefill or None,
                back_year=back_year,
                back_month=back_month,
            )
        ev = AgendaEvent(
            title=title,
            body=body,
            event_date=evd,
            event_time=tm,
            clube_id=write_cid,
        )
        db.session.add(ev)
        db.session.commit()
        flash("Evento agendado.", "success")
        return redirect(
            url_for(
                "admin.agenda_list",
                year=evd.year,
                month=evd.month,
                selected=evd.isoformat(),
                **_scope_kw_for_redirect(write_cid),
            )
        )
    return render_admin_shell(
        "admin/agenda_form.html",
        ev=None,
        prefill_date=prefill or None,
        back_year=back_year,
        back_month=back_month,
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
            title, body, evd, tm = _parse_agenda_form(request.form)
        except ValueError as e:
            flash(str(e), "warning")
            return render_admin_shell(
                "admin/agenda_form.html",
                ev=ev,
                prefill_date=None,
                back_year=ev.event_date.year,
                back_month=ev.event_date.month,
            )
        ev.title = title
        ev.body = body
        ev.event_date = evd
        ev.event_time = tm
        db.session.commit()
        flash("Agenda atualizada.", "success")
        return redirect(
            url_for(
                "admin.agenda_list",
                year=evd.year,
                month=evd.month,
                selected=evd.isoformat(),
                **_scope_kw_for_redirect(ev.clube_id),
            )
        )
    return render_admin_shell(
        "admin/agenda_form.html",
        ev=ev,
        prefill_date=None,
        back_year=ev.event_date.year,
        back_month=ev.event_date.month,
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
    return redirect(url_for("admin.member_activity", id=m.id, **_scope_kw_for_redirect(m.clube_id)))


@bp.route("/membros/<int:id>/atividade", methods=["GET", "POST"])
def member_activity(id):
    m = _member_for_admin(id)
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
        return redirect(url_for("admin.member_activity", id=m.id, **_scope_kw_for_redirect(m.clube_id)))

    records = (
        ActivityRecord.query.filter_by(member_id=m.id)
        .order_by(ActivityRecord.recorded_at.desc(), ActivityRecord.id.desc())
        .limit(80)
        .all()
    )
    completed_recs = [r for r in records if r.completed]
    open_recs = [r for r in records if not r.completed]
    n_done = len(completed_recs)
    n_open = len(open_recs)
    notebook_pct = m.notebook_checklist_progress_percent()
    checklist_30 = m.get_notebook_checklist_30()
    checklist_done_count = sum(1 for x in checklist_30 if x)
    duques_rows = (
        MeetingDuque.query.filter_by(member_id=m.id)
        .order_by(MeetingDuque.meeting_date.desc(), MeetingDuque.id.desc())
        .limit(60)
        .all()
    )
    duques_total = (
        db.session.query(func.coalesce(func.sum(MeetingDuque.duques), 0))
        .filter(MeetingDuque.member_id == m.id)
        .scalar()
        or 0
    )
    return render_admin_shell(
        "admin/member_activity.html",
        member=m,
        records=records,
        completed_recs=completed_recs,
        open_recs=open_recs,
        n_done=n_done,
        n_open=n_open,
        notebook_pct=notebook_pct,
        checklist_30=checklist_30,
        checklist_done_count=checklist_done_count,
        duques_rows=duques_rows,
        duques_total=int(duques_total),
        today_iso=date.today().isoformat(),
    )


@bp.route("/membros/<int:member_id>/atividade/<int:rec_id>/excluir", methods=["POST"])
def activity_delete(member_id, rec_id):
    m = _member_for_admin(member_id)
    rec = ActivityRecord.query.filter_by(id=rec_id, member_id=m.id).first_or_404()
    db.session.delete(rec)
    m.overall_performance = m.computed_overall_performance()
    db.session.commit()
    flash("Registro removido.", "info")
    return redirect(url_for("admin.member_activity", id=member_id, **_scope_kw_for_redirect(m.clube_id)))


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
    return redirect(url_for("admin.member_activity", id=member_id, **_scope_kw_for_redirect(m.clube_id)))


@bp.route("/membros/<int:member_id>/atividade/duques", methods=["POST"])
def member_duques_add(member_id):
    m = _member_for_admin(member_id)
    md_raw = (request.form.get("meeting_date") or "").strip()
    try:
        md = date.fromisoformat(md_raw)
    except ValueError:
        flash("Informe uma data de reunião válida.", "warning")
        return redirect(url_for("admin.member_activity", id=m.id, **_scope_kw_for_redirect(m.clube_id)))
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
    return redirect(url_for("admin.member_activity", id=m.id, **_scope_kw_for_redirect(m.clube_id)))


@bp.route("/membros/<int:member_id>/atividade/duques/<int:duque_id>/excluir", methods=["POST"])
def member_duques_delete(member_id, duque_id):
    m = _member_for_admin(member_id)
    row = MeetingDuque.query.filter_by(id=duque_id, member_id=m.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash("Registro de duques removido.", "info")
    return redirect(url_for("admin.member_activity", id=m.id, **_scope_kw_for_redirect(m.clube_id)))


@bp.route("/membros/<int:id>/presenca", methods=["GET", "POST"])
def member_attendance(id):
    m = _member_for_admin(id)
    if request.method == "POST":
        md_raw = request.form.get("meeting_date") or ""
        try:
            md = date.fromisoformat(md_raw)
        except ValueError:
            flash("Data da reunião inválida.", "warning")
            return redirect(url_for("admin.member_attendance", id=m.id, **_scope_kw_for_redirect(m.clube_id)))
        present = request.form.get("present") == "1"
        note = (request.form.get("note") or "").strip() or None
        row = Attendance(
            member_id=m.id,
            meeting_date=md,
            present=present,
            note=note,
        )
        db.session.add(row)
        m.overall_performance = m.computed_overall_performance()
        db.session.commit()
        flash("Presença registrada.", "success")
        return redirect(url_for("admin.member_attendance", id=m.id, **_scope_kw_for_redirect(m.clube_id)))

    rows = (
        Attendance.query.filter_by(member_id=m.id)
        .order_by(Attendance.meeting_date.desc())
        .limit(80)
        .all()
    )
    pr, tot, pct = m.attendance_stats()
    return render_admin_shell(
        "admin/member_attendance.html",
        member=m,
        rows=rows,
        att_present=pr,
        att_total=tot,
        att_rate=pct if tot else None,
    )


@bp.route("/membros/<int:member_id>/presenca/<int:att_id>/excluir", methods=["POST"])
def attendance_delete(member_id, att_id):
    m = _member_for_admin(member_id)
    row = Attendance.query.filter_by(id=att_id, member_id=m.id).first_or_404()
    db.session.delete(row)
    m.overall_performance = m.computed_overall_performance()
    db.session.commit()
    flash("Registro de presença excluído.", "info")
    return redirect(url_for("admin.member_attendance", id=member_id, **_scope_kw_for_redirect(m.clube_id)))


def _normalize_post_kind(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s == POST_KIND_NOTICIA:
        return POST_KIND_NOTICIA
    return POST_KIND_COMUNICADO


def _apply_publication_form_to_post(p: BoardPost, write_cid: str) -> None:
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
        if p.image_filename:
            _safe_remove_upload(p.image_filename)
        p.image_filename = None


@bp.route("/publicacoes")
def posts():
    cid = _read_scope_clube_id()
    rows = _board_scoped_query().order_by(BoardPost.created_at.desc()).all()
    return render_admin_shell(
        "admin/posts.html",
        posts=rows,
        levels=NEWS_LEVELS,
        admin_scope_clube_id=cid,
    )


@bp.route("/publicacoes/nova", methods=["GET", "POST"])
def post_new():
    scope_clube_id = _read_scope_clube_id()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = (request.form.get("body") or "").strip()
        if not title or not body:
            flash("Título e texto são obrigatórios.", "warning")
            return render_admin_shell(
                "admin/post_form.html",
                post=None,
                levels=NEWS_LEVELS,
                admin_scope_clube_id=scope_clube_id,
            )
        write_cid = _write_clube_id_for_admin()
        if not write_cid:
            flash("Defina o clube (super admin: ?clube_id= ou campo oculto).", "warning")
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
            p.image_filename = None
        db.session.add(p)
        db.session.commit()
        flash("Publicação criada.", "success")
        return redirect(url_for("admin.posts", **_scope_kw_for_redirect(write_cid)))
    return render_admin_shell(
        "admin/post_form.html",
        post=None,
        levels=NEWS_LEVELS,
        admin_scope_clube_id=scope_clube_id,
    )


@bp.route("/publicacoes/<int:pid>/editar", methods=["GET", "POST"])
def post_edit(pid):
    p = _board_post_for_admin(pid)
    scope_clube_id = _read_scope_clube_id()
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
    p = _board_post_for_admin(post_id)
    _safe_remove_upload(p.image_filename)
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
    rows = (
        _directorate_scoped_query()
        .order_by(DirectorateMember.display_order, DirectorateMember.full_name)
        .all()
    )
    club_id = _read_scope_clube_id()
    leadership_cargos = (
        CARGO_CONSELHEIRO,
        CARGO_SECRETARIO,
        CARGO_TESOUREIRO,
        CARGO_DIRETOR,
    )
    users_query = (
        db.session.query(User, Profile, Club)
        .join(Profile, Profile.id == User.id)
        .outerjoin(Club, Club.id == Profile.clube_id)
        .filter(Profile.cargo != CARGO_SUPER_ADMIN)
        .filter(Profile.cargo.in_(leadership_cargos))
    )
    if club_id:
        users_query = users_query.filter(Profile.clube_id == club_id)
    elif is_super_admin():
        users_query = users_query.filter(false())
    else:
        users_query = users_query.filter(false())
    users_for_roles = users_query.order_by(User.full_name.asc(), User.email.asc()).all()

    delegacao_busca = (request.args.get("delegacao") or "").strip()
    delegacao_resultados = []
    if delegacao_busca and club_id:
        like = f"%{delegacao_busca}%"
        dq = (
            db.session.query(User, Profile)
            .join(Profile, Profile.id == User.id)
            .filter(Profile.clube_id == club_id)
            .filter(or_(User.email.ilike(like), User.full_name.ilike(like)))
            .order_by(User.full_name.asc(), User.email.asc())
            .limit(25)
            .all()
        )
        delegacao_resultados = dq

    allowed_roles = [
        (CARGO_CONSELHEIRO, "Conselheiro"),
        (CARGO_SECRETARIO, "Secretaria"),
        (CARGO_TESOUREIRO, "Tesouraria"),
    ]
    if is_super_admin():
        allowed_roles.append((CARGO_DIRETOR, "Diretor"))
    return render_admin_shell(
        "admin/directorate_list.html",
        members=rows,
        users_for_roles=users_for_roles,
        delegacao_busca=delegacao_busca,
        delegacao_resultados=delegacao_resultados,
        allowed_roles=allowed_roles,
        admin_scope_clube_id=club_id,
        can_assign_directorate=_can_assign_directorate_and_delegate(),
    )


@bp.route("/diretoria/permissoes", methods=["POST"])
def directorate_permissions():
    if not _can_assign_directorate_and_delegate():
        flash("Apenas o diretor ou o super admin pode delegar funções da liderança.", "warning")
        return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect()))
    email = (request.form.get("email") or "").strip().lower()
    new_role = (request.form.get("cargo") or "").strip()
    allowed = {CARGO_CONSELHEIRO, CARGO_SECRETARIO, CARGO_TESOUREIRO}
    if is_super_admin():
        allowed.add(CARGO_DIRETOR)
    if not email or new_role not in allowed:
        flash("Informe e-mail e função válidos.", "warning")
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
    profile.clube_id = scope_club_id
    profile.cargo = new_role
    profile.cargos_json = json.dumps([new_role])
    profile.email_verificado = bool(user.email_verified)
    profile.nome_completo = profile.nome_completo or user.full_name
    user.role = "admin" if new_role == CARGO_DIRETOR else "parent"
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
        _apply_directorate_form(d, request.form, request.files)
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
        d.full_name = (request.form.get("full_name") or "").strip() or d.full_name
        d.cargo = (request.form.get("cargo") or "").strip() or d.cargo
        _apply_directorate_form(d, request.form, request.files)
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
    _safe_remove_upload(d.photo_filename)
    db.session.delete(d)
    db.session.commit()
    flash("Registro removido.", "info")
    return redirect(url_for("admin.directorate_list", **_scope_kw_for_redirect(cid)))


def _apply_directorate_form(d: DirectorateMember, form, files) -> None:
    d.phone = (form.get("phone") or "").strip() or None
    d.email_public = (form.get("email_public") or "").strip() or None
    d.bio = (form.get("bio") or "").strip() or None
    try:
        d.display_order = int(form.get("display_order") or 0)
    except ValueError:
        d.display_order = 0

    if form.get("remove_photo") == "1":
        _safe_remove_upload(d.photo_filename)
        d.photo_filename = None
    else:
        f = files.get("photo")
        saved = save_upload(f, current_app.config["UPLOAD_FOLDER"], "directorate")
        if saved:
            _safe_remove_upload(d.photo_filename)
            d.photo_filename = saved


# ---------- Financeiro ----------


@bp.route("/financeiro")
def finance_dashboard():
    perms = get_admin_panel_permissions()
    if not perms.get("can_view_finance"):
        flash("Seu cargo não permite acessar o financeiro.", "warning")
        return redirect(route_for_user(current_user))
    cid = _read_scope_clube_id()
    if cid:
        total_in = (
            db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
            .filter(FinanceLedgerEntry.direction == "income", FinanceLedgerEntry.clube_id == cid)
            .scalar()
            or 0
        )
        total_out = (
            db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
            .filter(FinanceLedgerEntry.direction == "expense", FinanceLedgerEntry.clube_id == cid)
            .scalar()
            or 0
        )
        pending = (
            db.session.query(func.coalesce(func.sum(MemberFee.amount_cents), 0))
            .join(Member, Member.id == MemberFee.member_id)
            .filter(MemberFee.paid_at.is_(None), Member.clube_id == cid)
            .scalar()
            or 0
        )
        ledger = (
            finance_ledger_query(cid)
            .order_by(FinanceLedgerEntry.occurred_at.desc(), FinanceLedgerEntry.id.desc())
            .limit(80)
            .all()
        )
        fees_open = (
            _member_fees_scoped_query()
            .filter(MemberFee.paid_at.is_(None))
            .order_by(MemberFee.due_date.asc(), MemberFee.id.asc())
            .limit(100)
            .all()
        )
        members = _members_scoped_query().order_by(Member.full_name).all()
        pix_key = get_pix_for_club(cid)
    else:
        total_in = total_out = pending = 0
        ledger = []
        fees_open = []
        members = []
        pix_key = ""
    return render_admin_shell(
        "admin/finance_dashboard.html",
        total_in=int(total_in),
        total_out=int(total_out),
        pending_fees=int(pending),
        balance=int(total_in) - int(total_out),
        ledger=ledger,
        fees_open=fees_open,
        members=members,
        today=date.today(),
        format_brl=format_brl_cents,
        pix_key=pix_key,
        admin_scope_clube_id=cid,
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
    row = FinanceLedgerEntry(
        occurred_at=occurred,
        direction=direction,
        amount_cents=amt,
        description=desc[:400],
        category=cat[:120] if cat else None,
        member_id=mid,
        clube_id=write_cid,
    )
    db.session.add(row)
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
    try:
        mid = int(request.form.get("member_id") or 0)
    except (TypeError, ValueError):
        mid = 0
    m = db.session.get(Member, mid)
    if not m or m.clube_id != write_cid:
        flash("Selecione um desbravador deste clube.", "warning")
        return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(write_cid)))
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
    fee = MemberFee(
        member_id=m.id,
        title=title[:200],
        amount_cents=amt,
        due_date=due,
        notes=notes,
    )
    db.session.add(fee)
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
    fee.paid_at = datetime.utcnow()
    db.session.commit()
    flash("Pagamento registrado.", "success")
    m = db.session.get(Member, fee.member_id)
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))


@bp.route("/financeiro/mensalidade/<int:fid>/excluir", methods=["POST"])
def finance_fee_delete(fid):
    perms = get_admin_panel_permissions()
    if not perms.get("can_write_finance"):
        flash("Seu cargo não permite alterar finanças.", "warning")
        return redirect(route_for_user(current_user))
    fee = _member_fee_for_admin(fid)
    m = db.session.get(Member, fee.member_id)
    db.session.delete(fee)
    db.session.commit()
    flash("Cobrança removida.", "info")
    return redirect(url_for("admin.finance_dashboard", **_scope_kw_for_redirect(m.clube_id if m else None)))
