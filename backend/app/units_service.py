"""Unidades do clube — dashboard premium, cargos e membros."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from sqlalchemy import func, or_

from app.extensions import db
from app.member_wizard import CLUB_UNIT_OPTIONS
from app.models import (
    Attendance,
    ClubUnit,
    ClubUnitRole,
    Member,
    UNIT_ROLE_COLOR_KEYS,
    UNIT_STATUS_ATIVA,
    UNIT_STATUS_OPTIONS,
    UNIT_THEME_COLORS,
)
from app.template_filters import fmt_date

DEFAULT_UNIT_ROLES: tuple[tuple[str, str], ...] = (
    ("Capitã", "purple"),
    ("Vice-capitã", "blue"),
    ("Secretária", "mint"),
    ("Tesoureira", "amber"),
    ("Instrutora", "pink"),
    ("Conselheira de Classe", "teal"),
    ("Membro", "gray"),
)

LEGACY_ROLE_MAP = {
    "desbravador": "Membro",
    "lider": "Capitã",
    "secretario_unidade": "Secretária",
    "instrutor": "Instrutora",
}

STATUS_BADGE_EXCELLENT = "excelente"
STATUS_BADGE_ATTENTION = "atencao"
STATUS_BADGE_LOW = "baixa"


def slugify_unit_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", (name or "").strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "unidade"


def unit_options_for_club(clube_id: str | None = None) -> list[str]:
    """Lista de nomes de unidades do clube (para selects em agenda, wizard, etc.)."""
    if not clube_id:
        return list(CLUB_UNIT_OPTIONS)
    ensure_club_units(clube_id)
    rows = (
        ClubUnit.query.filter_by(clube_id=clube_id, status=UNIT_STATUS_ATIVA)
        .order_by(ClubUnit.sort_order, ClubUnit.name)
        .all()
    )
    names = [u.name for u in rows]
    return names if names else list(CLUB_UNIT_OPTIONS)


def _default_initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return "U"
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][:2].upper()


def _infer_unit_type(name: str) -> str | None:
    n = (name or "").lower()
    if "embaixadora" in n or "reais" in n and "femin" not in n:
        return "Unidade Feminina"
    if "exército" in n or "exercito" in n:
        return "Unidade Masculina"
    return None


def ensure_default_roles(unit: ClubUnit) -> None:
    if unit.roles:
        return
    for i, (rname, color) in enumerate(DEFAULT_UNIT_ROLES):
        db.session.add(
            ClubUnitRole(unit_id=unit.id, name=rname, color_key=color, sort_order=i)
        )


def ensure_club_units(clube_id: str) -> None:
    """Garante unidades no banco a partir do catálogo fixo e membros existentes."""
    names: set[str] = set(CLUB_UNIT_OPTIONS)
    for row in db.session.query(Member.unit).filter(Member.clube_id == clube_id).distinct():
        u = (row[0] or "").strip()
        if u:
            names.add(u)

    for sort_i, name in enumerate(sorted(names, key=lambda x: (x not in CLUB_UNIT_OPTIONS, x))):
        slug = slugify_unit_name(name)
        unit = ClubUnit.query.filter_by(clube_id=clube_id, slug=slug).first()
        if not unit:
            unit = ClubUnit.query.filter_by(clube_id=clube_id, name=name).first()
        if not unit:
            unit = ClubUnit(
                clube_id=clube_id,
                name=name,
                slug=slug,
                initials=_default_initials(name),
                description=_infer_unit_type(name),
                unit_type=_infer_unit_type(name),
                status=UNIT_STATUS_ATIVA,
                theme_color="gold" if "embaixadora" in name.lower() else "purple",
                sort_order=sort_i,
            )
            db.session.add(unit)
            db.session.flush()
        ensure_default_roles(unit)
    db.session.commit()


def get_unit_for_club(unit_id: int, clube_id: str) -> ClubUnit | None:
    return ClubUnit.query.filter_by(id=unit_id, clube_id=clube_id).first()


def _members_in_unit(clube_id: str, unit_name: str) -> list[Member]:
    return (
        Member.query.filter(Member.clube_id == clube_id, Member.unit == unit_name)
        .order_by(Member.full_name)
        .all()
    )


def _unit_attendance_rate_month(clube_id: str, unit_name: str) -> int:
    today = date.today()
    start = today.replace(day=1)
    members = _members_in_unit(clube_id, unit_name)
    if not members:
        return 0
    ids = [m.id for m in members]
    rows = (
        db.session.query(Attendance.present, func.count(Attendance.id))
        .filter(
            Attendance.member_id.in_(ids),
            Attendance.meeting_date >= start,
            Attendance.meeting_date <= today,
        )
        .group_by(Attendance.present)
        .all()
    )
    present = absent = 0
    for is_present, cnt in rows:
        if is_present:
            present += int(cnt)
        else:
            absent += int(cnt)
    total = present + absent
    return round(100 * present / total) if total else 0


def _unit_attendance_trend(clube_id: str, unit_name: str, weeks: int = 4) -> list[int]:
    members = _members_in_unit(clube_id, unit_name)
    if not members:
        return [0] * weeks
    ids = [m.id for m in members]
    today = date.today()
    rates = []
    for w in range(weeks - 1, -1, -1):
        end = today - timedelta(days=today.weekday() + 7 * w)
        start = end - timedelta(days=6)
        rows = (
            db.session.query(Attendance.present, func.count(Attendance.id))
            .filter(
                Attendance.member_id.in_(ids),
                Attendance.meeting_date >= start,
                Attendance.meeting_date <= end,
            )
            .group_by(Attendance.present)
            .all()
        )
        present = absent = 0
        for is_present, cnt in rows:
            if is_present:
                present += int(cnt)
            else:
                absent += int(cnt)
        total = present + absent
        rates.append(round(100 * present / total) if total else 0)
    return rates


def _avg_metric(members: list[Member], getter) -> int:
    if not members:
        return 0
    vals = [getter(m) for m in members]
    return round(sum(vals) / len(vals))


def _status_badge(rate: int) -> tuple[str, str]:
    if rate >= 90:
        return STATUS_BADGE_EXCELLENT, "Excelente"
    if rate >= 70:
        return STATUS_BADGE_ATTENTION, "Atenção"
    return STATUS_BADGE_LOW, "Baixa"


def _counselor_name(clube_id: str, unit_name: str, members: list[Member]) -> str:
    for m in members:
        role = (m.unit_role or "").lower()
        if "conselheir" in role or role in ("lider", "líder de unidade"):
            return m.full_name
    for m in members:
        r = (m.unit_role or "").strip()
        if r and r.lower() not in ("membro", "desbravador", ""):
            return m.full_name
    from app.models import DirectorateMember

    dm = (
        DirectorateMember.query.filter_by(clube_id=clube_id, unit=unit_name)
        .order_by(DirectorateMember.id)
        .first()
    )
    if dm:
        return dm.full_name
    return "—"


def _role_display(member: Member, roles_by_name: dict[str, ClubUnitRole]) -> dict:
    raw = (member.unit_role or "").strip()
    if raw in LEGACY_ROLE_MAP:
        raw = LEGACY_ROLE_MAP[raw]
    role = roles_by_name.get(raw)
    color = role.color_key if role else "gray"
    label = role.name if role else (raw or "Membro")
    return {"label": label, "color_key": color, "role_id": role.id if role else None}


def _photo_url(rel: str | None, photo_url_builder) -> str | None:
    """photo_url_builder: callable(rel_path) -> url, ex. admin._unit_photo_url."""
    if not rel or not photo_url_builder:
        return None
    return photo_url_builder(rel)


def build_unit_card(unit: ClubUnit, clube_id: str, photo_url_fn) -> dict:
    members = _members_in_unit(clube_id, unit.name)
    att = _unit_attendance_rate_month(clube_id, unit.name)
    badge_key, badge_label = _status_badge(att)
    classes_pct = _avg_metric(members, lambda m: m.notebook_checklist_progress_percent())
    spec_pct = _avg_metric(members, lambda m: m.specialty_completion_percent())
    trend = _unit_attendance_trend(clube_id, unit.name)
    avatars = []
    for m in members[:5]:
        avatars.append(
            {
                "name": m.full_name,
                "initial": (m.full_name or "?")[0].upper(),
                "photo_url": _photo_url(m.photo_filename, photo_url_fn),
            }
        )
    logo_url = _photo_url(unit.logo_filename, photo_url_fn)
    return {
        "id": unit.id,
        "name": unit.name,
        "initials": unit.initials or _default_initials(unit.name),
        "logo_url": logo_url,
        "theme_color": unit.theme_color or "gold",
        "description": unit.description or unit.unit_type or "",
        "status": unit.status,
        "member_count": len(members),
        "counselor": _counselor_name(clube_id, unit.name, members),
        "attendance_pct": att,
        "classes_pct": classes_pct,
        "specialties_pct": spec_pct,
        "status_badge": badge_key,
        "status_label": badge_label,
        "trend": trend,
        "avatars": avatars,
        "extra_avatars": max(0, len(members) - 5),
        "detail_url": None,
        "edit_url": None,
    }


def units_dashboard_payload(clube_id: str, photo_url_fn) -> dict:
    ensure_club_units(clube_id)
    units = (
        ClubUnit.query.filter_by(clube_id=clube_id)
        .filter(ClubUnit.status != "arquivada")
        .order_by(ClubUnit.sort_order, ClubUnit.name)
        .all()
    )
    cards = []
    total_members = 0
    att_rates = []
    best = None
    for unit in units:
        card = build_unit_card(unit, clube_id, photo_url_fn)
        total_members += card["member_count"]
        if card["member_count"]:
            att_rates.append(card["attendance_pct"])
        if best is None or card["attendance_pct"] > best["attendance_pct"]:
            best = card
        cards.append(card)

    avg_att = round(sum(att_rates) / len(att_rates)) if att_rates else 0
    active_count = sum(1 for u in units if u.status == UNIT_STATUS_ATIVA)

    return {
        "kpis": {
            "total_units": len(units),
            "total_members": total_members,
            "avg_attendance": avg_att,
            "featured_unit": best["name"] if best else "—",
            "active_units": active_count,
        },
        "cards": cards,
        "tip": (
            "Unidades com frequência acima de 90% têm 2x mais chances "
            "de completar especialidades no ano."
        ),
    }


def unit_detail_payload(unit_id: int, clube_id: str, photo_url_fn) -> dict | None:
    unit = get_unit_for_club(unit_id, clube_id)
    if not unit:
        return None
    ensure_default_roles(unit)
    members = _members_in_unit(clube_id, unit.name)
    roles = list(unit.roles)
    roles_by_name = {r.name: r for r in roles}
    role_counts: dict[str, int] = {r.name: 0 for r in roles}
    member_rows = []
    for m in members:
        rd = _role_display(m, roles_by_name)
        role_counts[rd["label"]] = role_counts.get(rd["label"], 0) + 1
        member_rows.append(
            {
                "id": m.id,
                "full_name": m.full_name,
                "initial": (m.full_name or "?")[0].upper(),
                "photo_url": _photo_url(m.photo_filename, photo_url_fn),
                "role_label": rd["label"],
                "role_color": rd["color_key"],
                "role_id": rd["role_id"],
                "joined_at": fmt_date(m.joined_at) if m.joined_at else "—",
                "joined_at_raw": m.joined_at.isoformat() if m.joined_at else "",
                "edit_url": None,
            }
        )

    att = _unit_attendance_rate_month(clube_id, unit.name)
    roles_sidebar = [
        {
            "id": r.id,
            "name": r.name,
            "color_key": r.color_key,
            "count": role_counts.get(r.name, 0),
        }
        for r in roles
    ]

    return {
        "unit": {
            "id": unit.id,
            "name": unit.name,
            "initials": unit.initials or _default_initials(unit.name),
            "logo_url": _photo_url(unit.logo_filename, photo_url_fn),
            "description": unit.description or unit.unit_type or "",
            "unit_type": unit.unit_type or "",
            "status": unit.status,
            "status_label": dict(UNIT_STATUS_OPTIONS).get(unit.status, unit.status),
            "theme_color": unit.theme_color,
            "founded_at": fmt_date(unit.founded_at) if unit.founded_at else "—",
            "founded_at_raw": unit.founded_at.isoformat() if unit.founded_at else "",
            "member_count": len(members),
            "counselor": _counselor_name(clube_id, unit.name, members),
            "attendance_pct": att,
        },
        "members": member_rows,
        "roles": roles_sidebar,
        "role_options": [{"id": r.id, "name": r.name} for r in roles],
        "available_members": _available_members_for_unit(clube_id, unit.name),
    }


def _available_members_for_unit(clube_id: str, unit_name: str) -> list[dict]:
    rows = (
        Member.query.filter(Member.clube_id == clube_id)
        .filter(or_(Member.unit.is_(None), Member.unit == "", Member.unit != unit_name))
        .order_by(Member.full_name)
        .limit(200)
        .all()
    )
    return [{"id": m.id, "full_name": m.full_name} for m in rows]


def apply_unit_form(unit: ClubUnit, form, clube_id: str) -> str | None:
    name = (form.get("name") or "").strip()
    if not name:
        return "Informe o nome da unidade."
    slug = slugify_unit_name(name)
    conflict = (
        ClubUnit.query.filter(
            ClubUnit.clube_id == clube_id,
            ClubUnit.slug == slug,
            ClubUnit.id != unit.id,
        )
        .first()
        if unit.id
        else ClubUnit.query.filter_by(clube_id=clube_id, slug=slug).first()
    )
    if conflict:
        return "Já existe uma unidade com esse nome."
    unit.name = name
    unit.slug = slug
    unit.initials = (form.get("initials") or "").strip() or _default_initials(name)
    unit.description = (form.get("description") or "").strip() or None
    unit.unit_type = (form.get("unit_type") or "").strip() or None
    unit.status = (form.get("status") or UNIT_STATUS_ATIVA).strip()
    if unit.status not in {s[0] for s in UNIT_STATUS_OPTIONS}:
        unit.status = UNIT_STATUS_ATIVA
    theme = (form.get("theme_color") or "gold").strip()
    if theme in {t[0] for t in UNIT_THEME_COLORS}:
        unit.theme_color = theme
    founded = (form.get("founded_at") or "").strip()
    if founded:
        try:
            unit.founded_at = date.fromisoformat(founded)
        except ValueError:
            return "Data de fundação inválida."
    else:
        unit.founded_at = None
    return None


def rename_unit_members(clube_id: str, old_name: str, new_name: str) -> None:
    if old_name == new_name:
        return
    Member.query.filter_by(clube_id=clube_id, unit=old_name).update({"unit": new_name})
    from app.models import AgendaEvent, DirectorateMember

    AgendaEvent.query.filter_by(clube_id=clube_id, unit=old_name).update({"unit": new_name})
    DirectorateMember.query.filter_by(clube_id=clube_id, unit=old_name).update({"unit": new_name})


def create_unit(clube_id: str, form) -> tuple[ClubUnit | None, str | None]:
    unit = ClubUnit(clube_id=clube_id, name="", slug="")
    err = apply_unit_form(unit, form, clube_id)
    if err:
        return None, err
    db.session.add(unit)
    db.session.flush()
    ensure_default_roles(unit)
    db.session.commit()
    return unit, None


def update_unit(unit: ClubUnit, form, clube_id: str) -> str | None:
    old_name = unit.name
    err = apply_unit_form(unit, form, clube_id)
    if err:
        return err
    if old_name != unit.name:
        rename_unit_members(clube_id, old_name, unit.name)
    db.session.commit()
    return None


def delete_unit(unit: ClubUnit, clube_id: str) -> None:
    Member.query.filter_by(clube_id=clube_id, unit=unit.name).update({"unit": None, "unit_role": None})
    db.session.delete(unit)
    db.session.commit()


def create_unit_role(unit: ClubUnit, name: str, color_key: str) -> str | None:
    name = (name or "").strip()
    if not name:
        return "Informe o nome do cargo."
    if ClubUnitRole.query.filter_by(unit_id=unit.id, name=name).first():
        return "Este cargo já existe na unidade."
    if color_key not in UNIT_ROLE_COLOR_KEYS:
        color_key = "gray"
    max_order = (
        db.session.query(func.max(ClubUnitRole.sort_order)).filter_by(unit_id=unit.id).scalar() or 0
    )
    db.session.add(
        ClubUnitRole(unit_id=unit.id, name=name, color_key=color_key, sort_order=max_order + 1)
    )
    db.session.commit()
    return None


def update_unit_role(role: ClubUnitRole, name: str, color_key: str) -> str | None:
    name = (name or "").strip()
    if not name:
        return "Informe o nome do cargo."
    old_name = role.name
    conflict = ClubUnitRole.query.filter(
        ClubUnitRole.unit_id == role.unit_id,
        ClubUnitRole.name == name,
        ClubUnitRole.id != role.id,
    ).first()
    if conflict:
        return "Já existe um cargo com esse nome."
    if color_key not in UNIT_ROLE_COLOR_KEYS:
        color_key = role.color_key
    role.name = name
    role.color_key = color_key
    if old_name != name:
        unit = role.unit
        Member.query.filter_by(clube_id=unit.clube_id, unit=unit.name, unit_role=old_name).update(
            {"unit_role": name}
        )
    db.session.commit()
    return None


def delete_unit_role(role: ClubUnitRole) -> str | None:
    unit = role.unit
    cnt = Member.query.filter_by(clube_id=unit.clube_id, unit=unit.name, unit_role=role.name).count()
    if cnt:
        membro = ClubUnitRole.query.filter_by(unit_id=unit.id, name="Membro").first()
        fallback = membro.name if membro else None
        if fallback:
            Member.query.filter_by(
                clube_id=unit.clube_id, unit=unit.name, unit_role=role.name
            ).update({"unit_role": fallback})
        else:
            return f"Não é possível excluir: {cnt} membro(s) possuem este cargo."
    db.session.delete(role)
    db.session.commit()
    return None


def assign_member_to_unit(
    member: Member, unit: ClubUnit, role_name: str | None, clube_id: str
) -> str | None:
    if member.clube_id != clube_id:
        return "Membro não pertence a este clube."
    member.unit = unit.name
    if role_name:
        role = ClubUnitRole.query.filter_by(unit_id=unit.id, name=role_name).first()
        if role:
            member.unit_role = role.name
        else:
            member.unit_role = role_name
    else:
        membro = ClubUnitRole.query.filter_by(unit_id=unit.id, name="Membro").first()
        member.unit_role = membro.name if membro else "Membro"
    db.session.commit()
    return None


def remove_member_from_unit(member: Member) -> None:
    member.unit = None
    member.unit_role = None
    db.session.commit()


def update_member_unit_role(member: Member, unit: ClubUnit, role_name: str) -> str | None:
    if member.unit != unit.name:
        return "Membro não está nesta unidade."
    role = ClubUnitRole.query.filter_by(unit_id=unit.id, name=role_name).first()
    if not role:
        return "Cargo inválido."
    member.unit_role = role.name
    db.session.commit()
    return None
