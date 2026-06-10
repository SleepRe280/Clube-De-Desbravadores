"""Dashboard premium de membros — cards, KPIs, sidebar e gamificação."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from app.extensions import db
from app.member_wizard import NOTEBOOK_ACTIVITY_OPTIONS

_STATUS_LABELS = {
    "ativo": "Ativo",
    "visitante": "Visitante",
    "em_treinamento": "Em treinamento",
    "inativo": "Inativo",
}
from app.models import (
    ActivityRecord,
    Attendance,
    Member,
    MemberSpecialtyProgress,
    MeetingDuque,
    SP_STATUS_COMPLETED,
    ClubUnit,
)
from app.units_service import ensure_club_units, units_dashboard_payload

THEME_UNIT_EMOJI = {
    "gold": "🦅",
    "purple": "🦁",
    "blue": "🦅",
    "emerald": "🌲",
    "rose": "🔥",
    "amber": "⭐",
}

LEVEL_TIERS = (
    (90, "Ouro", "gold"),
    (70, "Prata", "silver"),
    (0, "Bronze", "bronze"),
)


def _photo_url(rel: str | None, builder) -> str | None:
    if not rel or not builder:
        return None
    return builder(rel)


def _unit_by_name(clube_id: str, unit_name: str | None) -> ClubUnit | None:
    if not clube_id or not (unit_name or "").strip():
        return None
    ensure_club_units(clube_id)
    return ClubUnit.query.filter_by(clube_id=clube_id, name=unit_name.strip()).first()


def _gamification_level(performance: int) -> dict:
    for threshold, label, tier in LEVEL_TIERS:
        if performance >= threshold:
            return {"label": label, "tier": tier}
    return {"label": "Bronze", "tier": "bronze"}


def _member_score(member: Member, *, duques: int, performance: int, spec_done: int) -> int:
    base = duques * 450 + performance * 120 + spec_done * 85
    if (member.unit_role or "").lower() in ("lider", "líder", "capitã", "capitao", "instrutor"):
        base += 500
    return max(0, base)


def _specialty_counts(member_id: int) -> tuple[int, int]:
    done = MemberSpecialtyProgress.query.filter_by(
        member_id=member_id, status=SP_STATUS_COMPLETED
    ).count()
    target = min(15, max(done, int(done * 1.2) or 3))
    return done, max(done, target)


def _class_progress(member: Member) -> tuple[int, int, str]:
    pct = member.notebook_checklist_progress_percent()
    done = min(4, max(0, round(pct / 25)))
    label = (member.notebook_current or "Em progresso").strip()
    return done, 4, label


def _events_count(member_id: int) -> int:
    year_start = date.today().replace(month=1, day=1)
    return (
        Attendance.query.filter(
            Attendance.member_id == member_id,
            Attendance.meeting_date >= year_start,
            Attendance.present.is_(True),
        ).count()
    )


def _is_leader(member: Member) -> bool:
    r = (member.unit_role or "").lower()
    return any(x in r for x in ("capit", "lider", "líder", "instrutor", "conselheir"))


def build_member_card(member: Member, clube_id: str, photo_url_fn, *, nav_kw: dict | None = None) -> dict:
    nav_kw = nav_kw or {}
    pr, tot, att_rate = member.attendance_stats()
    performance = member.computed_overall_performance()
    notebook_pct = member.notebook_checklist_progress_percent()
    duques = int(
        db.session.query(func.coalesce(func.sum(MeetingDuque.duques), 0))
        .filter(MeetingDuque.member_id == member.id)
        .scalar()
        or 0
    )
    spec_done, spec_target = _specialty_counts(member.id)
    class_done, class_total, class_label = _class_progress(member)
    level = _gamification_level(performance)
    unit = _unit_by_name(clube_id, member.unit)
    theme = (unit.theme_color if unit else None) or "gold"
    unit_name = (member.unit or "").strip() or "Sem unidade"
    unit_emoji = THEME_UNIT_EMOJI.get(theme, "🛡️")

    parent_label = None
    if member.parent:
        parent_label = member.parent.full_name or member.parent.email
    elif member.father_name:
        parent_label = member.father_name

    birth_display = "—"
    if member.birth_date:
        birth_display = member.birth_date.strftime("%d/%m/%Y")

    role_label = (member.unit_role or "Desbravador").strip()
    if role_label.lower() in ("desbravador", "membro", ""):
        role_label = "Desbravador"

    unit_detail_url = None
    if unit:
        try:
            from flask import url_for

            unit_detail_url = url_for(
                "admin.admin_unit_detail", unit_id=unit.id, **nav_kw
            )
        except Exception:
            unit_detail_url = None

    try:
        from flask import url_for

        profile_url = url_for("admin.member_profile", id=member.id, **nav_kw)
        edit_url = url_for("admin.member_edit", id=member.id, **nav_kw)
        delete_url = url_for("admin.member_delete", id=member.id, **nav_kw)
    except Exception:
        profile_url = edit_url = delete_url = f"/admin/membros/{member.id}/perfil"

    pending_flags = []
    if not member.photo_filename:
        pending_flags.append("foto")
    if not member.cpf:
        pending_flags.append("cpf")
    if not member.parent_id:
        pending_flags.append("responsavel")

    return {
        "id": member.id,
        "full_name": member.full_name,
        "initial": (member.full_name or "?")[0].upper(),
        "photo_url": _photo_url(member.photo_filename, photo_url_fn),
        "unit_name": unit_name,
        "unit_theme": theme,
        "unit_emoji": unit_emoji,
        "unit_logo_url": _photo_url(unit.logo_filename if unit else None, photo_url_fn),
        "unit_initials": (unit.initials if unit else None) or unit_name[:2].upper(),
        "unit_detail_url": unit_detail_url,
        "class_label": class_label,
        "class_badges": [class_label] if class_label else [],
        "role_label": role_label,
        "patrol_label": unit_name,
        "parent_label": parent_label or "Sem responsável vinculado",
        "age_years": member.age_years,
        "birth_display": birth_display,
        "status": (member.member_status or "ativo").strip(),
        "status_label": _STATUS_LABELS.get(
            (member.member_status or "ativo").strip(),
            (member.member_status or "ativo").title(),
        ),
        "is_leader": _is_leader(member),
        "performance": performance,
        "notebook_pct": notebook_pct,
        "att_rate": att_rate if tot else 0,
        "metrics": {
            "specialties_done": spec_done,
            "specialties_target": spec_target,
            "classes_done": class_done,
            "classes_target": class_total,
            "frequency": att_rate if tot else 0,
            "events": _events_count(member.id),
            "score": _member_score(member, duques=duques, performance=performance, spec_done=spec_done),
        },
        "level": level,
        "duques_total": duques,
        "profile_url": profile_url,
        "edit_url": edit_url,
        "delete_url": delete_url,
        "pending_flags": pending_flags,
        "search_blob": " ".join(
            filter(
                None,
                [
                    member.full_name,
                    unit_name,
                    class_label,
                    role_label,
                    parent_label,
                    member.email,
                ],
            )
        ).lower(),
    }


def _members_kpis(members: list[Member]) -> dict:
    today = date.today()
    total = len(members)
    active = sum(1 for m in members if (m.member_status or "ativo") == "ativo")
    leaders = sum(1 for m in members if _is_leader(m))
    pending = 0
    birthdays = 0
    for m in members:
        flags = []
        if not m.photo_filename:
            flags.append(1)
        if not m.cpf:
            flags.append(1)
        if not m.parent_id:
            flags.append(1)
        if len(flags) >= 2:
            pending += 1
        if m.birth_date:
            bday = m.birth_date.replace(year=today.year)
            if bday < today:
                bday = bday.replace(year=today.year + 1)
            delta = (bday - today).days
            if 0 <= delta <= 30:
                birthdays += 1
    return {
        "total": total,
        "active": active,
        "leaders": leaders,
        "pending": pending,
        "birthdays": birthdays,
    }


def _upcoming_birthdays(members: list[Member], limit: int = 6) -> list[dict]:
    today = date.today()
    items = []
    for m in members:
        if not m.birth_date:
            continue
        next_b = m.birth_date.replace(year=today.year)
        if next_b < today:
            next_b = next_b.replace(year=today.year + 1)
        items.append((next_b, m))
    items.sort(key=lambda x: x[0])
    out = []
    for next_b, m in items[:limit]:
        delta = (next_b - today).days
        out.append(
            {
                "id": m.id,
                "name": m.full_name,
                "date_label": next_b.strftime("%d/%m"),
                "when": "Hoje" if delta == 0 else f"Em {delta} dia(s)",
                "initial": m.full_name[0].upper(),
                "photo_url": None,
            }
        )
    return out


def _pending_summary(members: list[Member]) -> list[dict]:
    incomplete = sum(1 for m in members if not m.cpf or not m.photo_filename)
    no_parent = sum(1 for m in members if not m.parent_id)
    training = sum(1 for m in members if (m.member_status or "") == "em_treinamento")
    rows = []
    if incomplete:
        rows.append({"label": "Fichas incompletas", "count": incomplete, "variant": "amber", "icon": "📋"})
    if no_parent:
        rows.append({"label": "Sem responsável no portal", "count": no_parent, "variant": "rose", "icon": "👪"})
    if training:
        rows.append({"label": "Em treinamento", "count": training, "variant": "blue", "icon": "📘"})
    return rows


def _recent_activities(clube_id: str, members_by_id: dict[int, Member], limit: int = 8) -> list[dict]:
    member_ids = list(members_by_id.keys())
    if not member_ids:
        return []
    rows = (
        ActivityRecord.query.filter(
            ActivityRecord.member_id.in_(member_ids), ActivityRecord.completed.is_(True)
        )
        .order_by(ActivityRecord.recorded_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        m = members_by_id.get(r.member_id)
        if not m:
            continue
        when = "Recente"
        if r.recorded_at:
            delta = (date.today() - r.recorded_at.date()).days
            if delta == 0:
                when = "Hoje"
            elif delta == 1:
                when = "Ontem"
            else:
                when = f"Há {delta} dias"
        out.append(
            {
                "member_name": m.full_name,
                "title": r.title,
                "subtitle": "Atividade concluída",
                "when": when,
                "icon": "✅",
            }
        )
    return out


def _unit_ranking(clube_id: str, photo_url_fn, limit: int = 5) -> list[dict]:
    if not clube_id:
        return []
    dash = units_dashboard_payload(clube_id, photo_url_fn)
    cards = sorted(
        dash.get("cards", []),
        key=lambda c: (c.get("attendance_pct", 0), c.get("member_count", 0)),
        reverse=True,
    )
    out = []
    for i, c in enumerate(cards[:limit]):
        score = c.get("member_count", 0) * 120 + c.get("attendance_pct", 0) * 10
        out.append(
            {
                "rank": i + 1,
                "name": c["name"],
                "score": score,
                "logo_url": c.get("logo_url"),
                "theme": c.get("theme_color", "gold"),
                "initials": c.get("initials", "U"),
            }
        )
    return out


def members_page_context(
    members: list[Member],
    clube_id: str | None,
    photo_url_fn,
    *,
    nav_kw: dict | None = None,
) -> dict:
    nav_kw = nav_kw or {}
    cards = [
        build_member_card(m, clube_id or m.clube_id or "", photo_url_fn, nav_kw=nav_kw)
        for m in members
    ]
    by_id = {m.id: m for m in members}
    units_filter = []
    if clube_id:
        ensure_club_units(clube_id)
        for u in ClubUnit.query.filter_by(clube_id=clube_id).order_by(ClubUnit.sort_order, ClubUnit.name):
            units_filter.append({"name": u.name, "theme": u.theme_color, "logo_url": _photo_url(u.logo_filename, photo_url_fn)})

    return {
        "mb_kpis": _members_kpis(members),
        "mb_cards": cards,
        "mb_birthdays": _upcoming_birthdays(members),
        "mb_pending": _pending_summary(members),
        "mb_activities": _recent_activities(clube_id or "", by_id) if clube_id else [],
        "mb_unit_ranking": _unit_ranking(clube_id or "", photo_url_fn),
        "mb_units_filter": units_filter,
        "mb_status_options": [
            ("", "Todos os status"),
            ("ativo", "Ativos"),
            ("em_treinamento", "Em treinamento"),
            ("visitante", "Visitantes"),
            ("inativo", "Inativos"),
        ],
        "mb_class_options": [("", "Todas as classes")] + [(c, c) for c in NOTEBOOK_ACTIVITY_OPTIONS],
    }


def unit_branding_for_member(
    member: Member, clube_id: str, photo_url_fn, *, nav_kw: dict | None = None
) -> dict:
    nav_kw = nav_kw or {}
    unit = _unit_by_name(clube_id, member.unit)
    if not unit:
        return {
            "unit_name": member.unit or "Sem unidade",
            "unit_logo_url": None,
            "unit_theme": "gold",
            "unit_detail_url": None,
        }
    try:
        from flask import url_for

        detail = url_for("admin.admin_unit_detail", unit_id=unit.id, **nav_kw)
    except Exception:
        detail = None
    return {
        "unit_name": unit.name,
        "unit_logo_url": _photo_url(unit.logo_filename, photo_url_fn),
        "unit_theme": unit.theme_color,
        "unit_detail_url": detail,
    }
