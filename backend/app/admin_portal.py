"""Helpers visuais do painel da diretoria (sem alterar regras de negócio)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import extract, func, or_

from app.extensions import db
from app.models import (
    ActivityRecord,
    AgendaEvent,
    Attendance,
    BoardPost,
    Member,
    MemberFee,
    POST_KIND_COMUNICADO,
)
from app.template_filters import fmt_date


def admin_time_greeting() -> str:
    h = datetime.now().hour
    if h < 12:
        return "Bom dia"
    if h < 18:
        return "Boa tarde"
    return "Boa noite"


def _week_attendance_rate(clube_id: str) -> int:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    rows = (
        db.session.query(Attendance.present, func.count(Attendance.id))
        .join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id)
        .filter(Attendance.meeting_date >= start)
        .filter(Attendance.meeting_date <= today)
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


def _events_today(clube_id: str) -> list[AgendaEvent]:
    today = date.today()
    return (
        AgendaEvent.query.filter(
            AgendaEvent.clube_id == clube_id,
            AgendaEvent.event_date == today,
        )
        .order_by(AgendaEvent.event_time.asc(), AgendaEvent.id.asc())
        .all()
    )


def _birthdays_this_month(clube_id: str, limit: int = 6) -> list[Member]:
    today = date.today()
    return (
        Member.query.filter(
            Member.clube_id == clube_id,
            Member.birth_date.isnot(None),
            extract("month", Member.birth_date) == today.month,
        )
        .order_by(extract("day", Member.birth_date))
        .limit(limit)
        .all()
    )


def _pending_fees_count(clube_id: str) -> int:
    return (
        db.session.query(func.count(MemberFee.id))
        .join(Member, Member.id == MemberFee.member_id)
        .filter(Member.clube_id == clube_id, MemberFee.paid_at.is_(None))
        .scalar()
        or 0
    )


def _build_activity_feed(
    clube_id: str,
    *,
    recent_members: list,
    recent_activities: list[dict],
    recent_posts: list,
    upcoming_events: list,
    limit: int = 12,
) -> list[dict]:
    items: list[dict] = []
    for m in recent_members[:4]:
        items.append(
            {
                "kind": "member",
                "icon": "👤",
                "color": "violet",
                "title": f"{m.full_name} no clube",
                "subtitle": m.unit or "Sem unidade",
                "time": "cadastro recente",
            }
        )
    for act in recent_activities[:5]:
        items.append(
            {
                "kind": "activity",
                "icon": "📘",
                "color": "emerald",
                "title": act.get("title") or "Atividade",
                "subtitle": act.get("member_name") or "",
                "time": act.get("ago") or "",
            }
        )
    for p in recent_posts[:3]:
        kind = "comunicado" if getattr(p, "post_kind", None) == POST_KIND_COMUNICADO else "noticia"
        items.append(
            {
                "kind": kind,
                "icon": "📢" if kind == "comunicado" else "📰",
                "color": "amber",
                "title": p.title,
                "subtitle": "Publicação no mural",
                "time": p.created_at.strftime("%d/%m") if p.created_at else "",
            }
        )
    for ev in upcoming_events[:3]:
        items.append(
            {
                "kind": "event",
                "icon": "📅",
                "color": "sky",
                "title": ev.title,
                "subtitle": (ev.body or ev.event_time or "Agenda do clube")[:80],
                "time": fmt_date(ev.event_date, "%d/%m"),
            }
        )
    return items[:limit]


def admin_dashboard_portal(
    clube_id: str | None,
    *,
    dash: dict,
    n_parents: int,
    finance_pending_fees: int,
    recent_posts: list,
) -> dict:
    """Dados extras para o dashboard moderno da diretoria."""
    if not clube_id:
        return {
            "greeting": admin_time_greeting(),
            "week_attendance": 0,
            "events_today": [],
            "n_events_today": 0,
            "birthdays": [],
            "pending_fees": 0,
            "n_parents": 0,
            "today_summary": [],
            "activity_feed": [],
            "challenge_points": 0,
            "challenge_goal": 500,
        }

    events_today = _events_today(clube_id)
    pending = _pending_fees_count(clube_id)
    week_att = _week_attendance_rate(clube_id)

    today_summary = [
        {
            "icon": "📅",
            "label": "Reuniões hoje",
            "value": str(len(events_today)),
            "hint": "na agenda",
        },
        {
            "icon": "👪",
            "label": "Responsáveis",
            "value": str(n_parents),
            "hint": "cadastrados",
        },
        {
            "icon": "💳",
            "label": "Mensalidades",
            "value": str(pending),
            "hint": "em aberto",
        },
        {
            "icon": "📢",
            "label": "Comunicados",
            "value": str(dash.get("n_posts", 0)),
            "hint": "no mural",
        },
        {
            "icon": "✓",
            "label": "Presença semana",
            "value": f"{week_att}%",
            "hint": "média geral",
        },
        {
            "icon": "🎯",
            "label": "Próximos eventos",
            "value": str(dash.get("n_upcoming", 0)),
            "hint": "agendados",
        },
    ]

    feed = _build_activity_feed(
        clube_id,
        recent_members=dash.get("recent_members") or [],
        recent_activities=dash.get("recent_activities") or [],
        recent_posts=recent_posts or [],
        upcoming_events=dash.get("upcoming_events") or [],
    )

    # desafio da semana: proxy de engajamento (presença + membros)
    challenge_points = min(500, week_att * 5 + (dash.get("n_members") or 0))

    return {
        "greeting": admin_time_greeting(),
        "week_attendance": week_att,
        "events_today": events_today,
        "n_events_today": len(events_today),
        "birthdays": _birthdays_this_month(clube_id),
        "pending_fees": pending,
        "n_parents": n_parents,
        "today_summary": today_summary,
        "activity_feed": feed,
        "challenge_points": challenge_points,
        "challenge_goal": 500,
    }


def admin_activities_timeline(clube_id: str, limit: int = 40) -> list[dict]:
    rows = (
        db.session.query(ActivityRecord, Member)
        .join(Member, Member.id == ActivityRecord.member_id)
        .filter(Member.clube_id == clube_id)
        .order_by(ActivityRecord.recorded_at.desc(), ActivityRecord.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    today = date.today()
    for ar, mem in rows:
        rd = ar.recorded_at or today
        delta = (today - rd).days if isinstance(rd, date) else 0
        if delta <= 0:
            ago = "hoje"
        elif delta == 1:
            ago = "ontem"
        else:
            ago = f"há {delta} dias"
        out.append(
            {
                "member_name": mem.full_name,
                "member_id": mem.id,
                "title": ar.title,
                "progress": ar.progress_percent or 0,
                "completed": bool(ar.completed),
                "ago": ago,
                "unit": mem.unit or "—",
            }
        )
    return out


def admin_units_overview(clube_id: str) -> list[dict]:
    rows = (
        db.session.query(Member.unit, func.count(Member.id))
        .filter(Member.clube_id == clube_id)
        .group_by(Member.unit)
        .order_by(func.count(Member.id).desc())
        .all()
    )
    units = []
    for u, cnt in rows:
        label = (u or "").strip() or "Sem unidade"
        mq = Member.query.filter(Member.clube_id == clube_id)
        if u:
            mq = mq.filter(Member.unit == u)
        else:
            mq = mq.filter(or_(Member.unit.is_(None), Member.unit == ""))
        members = mq.order_by(Member.full_name).limit(8).all()
        units.append({"label": label, "count": int(cnt), "members": members})
    return units
