"""Gestão da liderança — métricas, serialização, permissões e auditoria."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from flask import url_for
from flask_login import current_user

from app.extensions import db
from app.models import (
    CARGO_CONSELHEIRO,
    CARGO_DIRETOR,
    CARGO_SECRETARIO,
    CARGO_TESOUREIRO,
    Club,
    ClubSetting,
    DirectorateMember,
    LeadershipAuditLog,
    LeadershipDelegation,
    Profile,
    User,
)

LEADERSHIP_ROLE_SLOTS = (
    CARGO_DIRETOR,
    CARGO_SECRETARIO,
    CARGO_TESOUREIRO,
    CARGO_CONSELHEIRO,
)

ROLE_LABELS = {
    CARGO_DIRETOR: "Diretor Geral",
    CARGO_SECRETARIO: "Secretário(a)",
    CARGO_TESOUREIRO: "Tesoureiro(a)",
    CARGO_CONSELHEIRO: "Conselheiro(a)",
}

ROLE_TAG_CSS = {
    CARGO_DIRETOR: "ld-tag--violet",
    CARGO_SECRETARIO: "ld-tag--blue",
    CARGO_TESOUREIRO: "ld-tag--green",
    CARGO_CONSELHEIRO: "ld-tag--amber",
}

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    CARGO_DIRETOR: {
        "finance": True,
        "members": True,
        "agenda": True,
        "reports": True,
        "warehouse": True,
        "directorate": True,
        "delegate": True,
        "view_only": False,
    },
    CARGO_SECRETARIO: {
        "finance": False,
        "members": True,
        "agenda": True,
        "reports": True,
        "warehouse": True,
        "directorate": False,
        "delegate": False,
        "view_only": False,
    },
    CARGO_TESOUREIRO: {
        "finance": True,
        "members": False,
        "agenda": False,
        "reports": True,
        "warehouse": False,
        "directorate": False,
        "delegate": False,
        "view_only": False,
    },
    CARGO_CONSELHEIRO: {
        "finance": False,
        "members": False,
        "agenda": False,
        "reports": False,
        "warehouse": False,
        "directorate": False,
        "delegate": False,
        "view_only": True,
    },
}

PERMISSION_LABELS = {
    "finance": "Financeiro",
    "members": "Membros e vínculos",
    "agenda": "Agenda e eventos",
    "reports": "Relatórios",
    "warehouse": "Almoxarifado",
    "directorate": "Gestão da diretoria",
    "delegate": "Delegar funções",
    "view_only": "Somente visualização",
}


def _perms_setting_key(clube_id: str) -> str:
    return f"leadership_role_permissions:{clube_id}"


def get_role_permissions(clube_id: str | None) -> dict[str, dict[str, bool]]:
    base = {k: dict(v) for k, v in DEFAULT_ROLE_PERMISSIONS.items()}
    if not clube_id:
        return base
    row = db.session.get(ClubSetting, _perms_setting_key(clube_id))
    if not row or not row.value:
        return base
    try:
        custom = json.loads(row.value)
        if isinstance(custom, dict):
            for role, perms in custom.items():
                if role in base and isinstance(perms, dict):
                    base[role].update({k: bool(v) for k, v in perms.items() if k in base[role]})
    except (TypeError, ValueError):
        pass
    return base


def save_role_permissions(clube_id: str, data: dict) -> None:
    cleaned: dict[str, dict[str, bool]] = {}
    defaults = DEFAULT_ROLE_PERMISSIONS
    for role in LEADERSHIP_ROLE_SLOTS:
        src = data.get(role) if isinstance(data.get(role), dict) else {}
        cleaned[role] = {
            k: bool(src.get(k, defaults[role].get(k, False))) for k in defaults[role]
        }
    key = _perms_setting_key(clube_id)
    row = db.session.get(ClubSetting, key)
    payload = json.dumps(cleaned, ensure_ascii=False)
    if row:
        row.value = payload
    else:
        db.session.add(ClubSetting(key=key, value=payload))


def initials_for(name: str | None) -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _photo_url(rel: str | None) -> str | None:
    if not rel:
        return None
    try:
        return url_for("uploaded_file", rel_path=rel)
    except Exception:
        return None


def log_leadership_action(
    clube_id: str | None,
    action: str,
    summary: str,
    *,
    target_user_id: int | None = None,
    target_member_id: int | None = None,
    details: dict | None = None,
    performed_by_id: int | None = None,
) -> None:
    pid = performed_by_id
    if pid is None and current_user and getattr(current_user, "is_authenticated", False):
        pid = current_user.id
    db.session.add(
        LeadershipAuditLog(
            clube_id=clube_id,
            action=action,
            summary=summary[:500],
            target_user_id=target_user_id,
            target_member_id=target_member_id,
            performed_by_id=pid,
            details_json=json.dumps(details or {}, ensure_ascii=False) if details else None,
        )
    )


def leadership_metrics(clube_id: str | None) -> dict:
    from app.access import cargos_for_profile

    dm_q = DirectorateMember.query
    if clube_id:
        dm_q = dm_q.filter(DirectorateMember.clube_id == clube_id)
    members = dm_q.all()
    n_members = len(members)

    occupied_roles: set[str] = set()
    for m in members:
        if m.system_role and m.effective_status() == "ativo":
            occupied_roles.add(m.system_role)
        elif m.system_role:
            occupied_roles.add(m.system_role)

    users_q = (
        db.session.query(User, Profile)
        .join(Profile, Profile.id == User.id)
        .filter(Profile.cargo.in_(LEADERSHIP_ROLE_SLOTS))
    )
    if clube_id:
        users_q = users_q.filter(Profile.clube_id == clube_id)
    for _user, profile in users_q.all():
        for c in cargos_for_profile(profile):
            if c in LEADERSHIP_ROLE_SLOTS:
                occupied_roles.add(c)

    n_occupied = len(occupied_roles)
    n_available = max(0, len(LEADERSHIP_ROLE_SLOTS) - n_occupied)

    month_ago = datetime.utcnow() - timedelta(days=30)
    recent = sum(1 for m in members if m.created_at and m.created_at >= month_ago)

    last_log = (
        LeadershipAuditLog.query.filter(LeadershipAuditLog.clube_id == clube_id)
        if clube_id
        else LeadershipAuditLog.query
    )
    last_row = last_log.order_by(LeadershipAuditLog.created_at.desc()).first()
    last_member = max(
        (m.updated_at or m.created_at for m in members if m.updated_at or m.created_at),
        default=None,
    )
    last_change = last_row.created_at if last_row else last_member

    return {
        "n_members": n_members,
        "n_occupied_roles": n_occupied,
        "n_available_roles": n_available,
        "recent_entries": recent,
        "last_change": last_change,
    }


def serialize_directorate_member(m: DirectorateMember) -> dict:
    role = m.system_role or ""
    return {
        "id": m.id,
        "user_id": m.user_id,
        "full_name": m.full_name,
        "cargo": m.cargo,
        "system_role": role,
        "role_label": ROLE_LABELS.get(role, m.cargo),
        "role_tag_css": ROLE_TAG_CSS.get(role, "ld-tag--slate"),
        "email": m.email or m.email_public or "",
        "email_public": m.email_public or "",
        "phone": m.phone or "",
        "whatsapp": m.whatsapp or "",
        "unit": m.unit or "",
        "city": m.address_city or "",
        "status": m.effective_status(),
        "status_label": "Ativo" if m.is_active() else "Inativo",
        "delegation_start": m.delegation_start.isoformat() if m.delegation_start else "",
        "delegation_start_fmt": _fmt_date(m.delegation_start),
        "entry_date_fmt": _fmt_date(m.entry_date or m.delegation_start),
        "photo_url": _photo_url(m.photo_filename),
        "initials": initials_for(m.full_name),
        "created_at_fmt": _fmt_datetime(m.created_at),
        "updated_at_fmt": _fmt_datetime(m.updated_at),
        "show_phone_public": bool(m.show_phone_public),
        "show_email_public": bool(m.show_email_public),
        "show_social_public": bool(m.show_social_public),
        "show_bio_public": bool(m.show_bio_public),
    }


def serialize_member_detail(m: DirectorateMember) -> dict:
    base = serialize_directorate_member(m)
    base.update(
        {
            "birth_date": m.birth_date.isoformat() if m.birth_date else "",
            "sex": m.sex or "",
            "cpf": m.cpf or "",
            "rg": m.rg or "",
            "address_cep": m.address_cep or "",
            "address_street": m.address_street or "",
            "address_neighborhood": m.address_neighborhood or "",
            "address_city": m.address_city or "",
            "address_state": m.address_state or "",
            "notes": m.notes or "",
            "responsible_area": m.responsible_area or "",
            "specialties": m.specialties or "",
            "bio": m.bio or "",
            "delegation_end": m.delegation_end.isoformat() if m.delegation_end else "",
            "social_links_json": m.social_links_json or "[]",
            "display_order": m.display_order or 0,
        }
    )
    return base


def _fmt_date(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _fmt_datetime(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")


def filter_team_rows(
    rows: list[dict],
    *,
    q: str = "",
    cargo: str = "",
    status: str = "",
    sort: str = "name",
) -> list[dict]:
    out = list(rows)
    ql = q.strip().lower()
    if ql:
        out = [
            r
            for r in out
            if ql in (r.get("full_name") or "").lower()
            or ql in (r.get("email") or "").lower()
            or ql in (r.get("phone") or "").lower()
            or ql in (r.get("cargo") or "").lower()
        ]
    if cargo:
        out = [r for r in out if r.get("system_role") == cargo or r.get("cargo") == cargo]
    if status:
        out = [r for r in out if r.get("status") == status]
    if sort == "cargo":
        out.sort(key=lambda r: (r.get("cargo") or "", r.get("full_name") or ""))
    elif sort == "recent":
        out.sort(key=lambda r: r.get("id") or 0, reverse=True)
    else:
        out.sort(key=lambda r: (r.get("full_name") or "").lower())
    return out


def paginate_rows(rows: list[dict], page: int, per_page: int = 8) -> tuple[list[dict], dict]:
    page = max(1, page)
    per_page = max(4, min(per_page, 50))
    total = len(rows)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    start = (page - 1) * per_page
    return rows[start : start + per_page], {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }


def search_users_for_delegation(clube_id: str | None, query: str, *, limit: int = 12) -> list[dict]:
    if not clube_id:
        return []
    q = (query or "").strip()
    if len(q) < 2:
        return []
    from sqlalchemy import or_

    like = f"%{q}%"
    rows = (
        db.session.query(User, Profile)
        .join(Profile, Profile.id == User.id)
        .filter(Profile.clube_id == clube_id)
        .filter(or_(User.email.ilike(like), User.full_name.ilike(like)))
        .order_by(User.full_name.asc(), User.email.asc())
        .limit(limit)
        .all()
    )
    out = []
    for user, profile in rows:
        dm = DirectorateMember.query.filter_by(clube_id=clube_id, user_id=user.id).first()
        out.append(
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name or profile.nome_completo or user.email,
                "initials": initials_for(user.full_name),
                "photo_url": _photo_url(dm.photo_filename) if dm else None,
                "current_role": profile.cargo,
                "has_directorate_row": dm is not None,
                "directorate_id": dm.id if dm else None,
            }
        )
    return out


def audit_log_for_club(clube_id: str | None, *, limit: int = 20) -> list[dict]:
    q = LeadershipAuditLog.query
    if clube_id:
        q = q.filter(LeadershipAuditLog.clube_id == clube_id)
    rows = q.order_by(LeadershipAuditLog.created_at.desc()).limit(limit).all()
    out = []
    for row in rows:
        who = "Sistema"
        if row.performed_by:
            who = row.performed_by.full_name or row.performed_by.email or who
        out.append(
            {
                "id": row.id,
                "summary": row.summary,
                "action": row.action,
                "who": who,
                "when": _fmt_datetime(row.created_at),
            }
        )
    return out


def recent_registrations(clube_id: str | None, *, limit: int = 4) -> list[dict]:
    q = DirectorateMember.query
    if clube_id:
        q = q.filter(DirectorateMember.clube_id == clube_id)
    rows = q.order_by(DirectorateMember.created_at.desc()).limit(limit).all()
    return [serialize_directorate_member(m) for m in rows]


def delegation_history_for_member(member_id: int) -> list[dict]:
    rows = (
        LeadershipDelegation.query.filter_by(directorate_member_id=member_id)
        .order_by(LeadershipDelegation.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "role_label": r.role_label or ROLE_LABELS.get(r.role_code, r.role_code),
            "start": _fmt_date(r.start_date),
            "end": _fmt_date(r.end_date) or "—",
            "active": bool(r.is_active),
            "when": _fmt_datetime(r.created_at),
        }
        for r in rows
    ]


def validate_role_assignment(clube_id: str, role_code: str, *, exclude_user_id: int | None = None) -> str | None:
    if role_code not in LEADERSHIP_ROLE_SLOTS:
        return "Função inválida."
    if role_code != CARGO_DIRETOR:
        return None
    from app.access import cargos_for_profile

    q = (
        db.session.query(User, Profile)
        .join(Profile, Profile.id == User.id)
        .filter(Profile.clube_id == clube_id)
    )
    for user, profile in q.all():
        if exclude_user_id and user.id == exclude_user_id:
            continue
        if CARGO_DIRETOR in cargos_for_profile(profile):
            return "Já existe um Diretor Geral ativo neste clube. Remova ou altere o cargo antes de delegar outro."
    active_dm = DirectorateMember.query.filter_by(
        clube_id=clube_id, system_role=CARGO_DIRETOR, status="ativo"
    ).all()
    for dm in active_dm:
        if exclude_user_id and dm.user_id == exclude_user_id:
            continue
        if dm.user_id:
            return "Já existe um Diretor Geral cadastrado na equipe."
    return None


def apply_directorate_from_form(m: DirectorateMember, form, files) -> None:
    from app.uploads_util import save_upload
    from flask import current_app

    def _s(key: str) -> str | None:
        v = (form.get(key) or "").strip()
        return v or None

    m.full_name = _s("full_name") or m.full_name
    m.cargo = _s("cargo") or m.cargo
    m.phone = _s("phone")
    m.whatsapp = _s("whatsapp")
    m.email = _s("email")
    m.email_public = _s("email_public")
    m.bio = _s("bio")
    m.sex = _s("sex")
    m.cpf = _s("cpf")
    m.rg = _s("rg")
    m.address_cep = _s("address_cep")
    m.address_street = _s("address_street")
    m.address_neighborhood = _s("address_neighborhood")
    m.address_city = _s("address_city")
    m.address_state = (_s("address_state") or "")[:2] or None
    m.unit = _s("unit")
    m.notes = _s("notes")
    m.responsible_area = _s("responsible_area")
    m.specialties = _s("specialties")
    m.social_links_json = (form.get("social_links_json") or "").strip() or None
    m.system_role = _s("system_role") or m.system_role
    m.status = (_s("status") or "ativo").lower()
    m.show_phone_public = form.get("show_phone_public") == "1"
    m.show_email_public = form.get("show_email_public") == "1"
    m.show_social_public = form.get("show_social_public") == "1"
    m.show_bio_public = form.get("show_bio_public") == "1"

    for field in ("birth_date", "entry_date", "delegation_start", "delegation_end"):
        raw = _s(field)
        if raw:
            try:
                setattr(m, field, date.fromisoformat(raw))
            except ValueError:
                pass
        elif form.get(field) == "":
            setattr(m, field, None)

    try:
        m.display_order = int(form.get("display_order") or 0)
    except ValueError:
        m.display_order = 0

    uid_raw = form.get("user_id")
    if uid_raw:
        try:
            m.user_id = int(uid_raw)
        except ValueError:
            pass

    upload_root = current_app.config["UPLOAD_FOLDER"]
    from app.uploads_util import safe_remove_upload

    if form.get("remove_photo") == "1":
        safe_remove_upload(upload_root, m.photo_filename)
        m.photo_filename = None
    else:
        f = files.get("photo") if files else None
        if f and getattr(f, "filename", None):
            saved = save_upload(f, upload_root, "directorate")
            if saved:
                safe_remove_upload(upload_root, m.photo_filename)
                m.photo_filename = saved

    m.updated_at = datetime.utcnow()


def public_team_for_parents(clube_id: str) -> list[DirectorateMember]:
    return (
        DirectorateMember.query.filter_by(clube_id=clube_id, status="ativo")
        .order_by(DirectorateMember.display_order, DirectorateMember.full_name)
        .all()
    )
