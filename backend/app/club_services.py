"""Consultas e validações com escopo por clube (multi-clube)."""
from __future__ import annotations

from flask import abort
from app.extensions import db
from app.models import (
    AgendaEvent,
    BoardPost,
    Club,
    DirectorateMember,
    FinanceLedgerEntry,
    Member,
    Profile,
    User,
)


def club_or_404(clube_id: str) -> Club:
    c = db.session.get(Club, clube_id)
    if not c:
        abort(404)
    return c


def member_in_clube(clube_id: str, member_id: int) -> Member | None:
    return (
        Member.query.filter_by(id=member_id, clube_id=clube_id).first()
        if clube_id
        else None
    )


def members_query(clube_id: str):
    return Member.query.filter(Member.clube_id == clube_id)


def billable_members_query(clube_id: str):
    """Desbravadores ativos elegíveis para mensalidades e cobranças em lote."""
    from sqlalchemy import or_

    return members_query(clube_id).filter(
        or_(Member.member_status.is_(None), Member.member_status == "", Member.member_status == "ativo"),
        or_(Member.unit_role.is_(None), Member.unit_role == "", Member.unit_role == "desbravador"),
    )


def agenda_query(clube_id: str):
    return AgendaEvent.query.filter(AgendaEvent.clube_id == clube_id)


def board_posts_query(clube_id: str):
    return BoardPost.query.filter(BoardPost.clube_id == clube_id)


def directorate_query(clube_id: str):
    return DirectorateMember.query.filter(DirectorateMember.clube_id == clube_id)


def finance_ledger_query(clube_id: str):
    return FinanceLedgerEntry.query.filter(FinanceLedgerEntry.clube_id == clube_id)


def parents_in_club_query(clube_id: str):
    return (
        db.session.query(User, Profile)
        .join(Profile, Profile.id == User.id)
        .filter(Profile.clube_id == clube_id, User.role == "parent")
        .order_by(User.full_name.asc(), User.email.asc())
    )


def pix_setting_key(clube_id: str) -> str:
    return f"pix_key:{clube_id}"


def get_pix_for_club(clube_id: str) -> str:
    from app.models import ClubSetting

    row = db.session.get(ClubSetting, pix_setting_key(clube_id))
    if row and row.value:
        return str(row.value).strip()
    legacy = db.session.get(ClubSetting, "pix_key")
    return (legacy.value or "").strip() if legacy else ""


def set_pix_for_club(clube_id: str, value: str) -> None:
    from app.models import ClubSetting

    key = pix_setting_key(clube_id)
    row = db.session.get(ClubSetting, key)
    if row is None:
        row = ClubSetting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value


def director_dashboard_stats(clube_id: str) -> dict:
    """Métricas e séries para o painel escuro do diretor (gráficos e cartões)."""
    from calendar import monthrange
    from datetime import date, timedelta

    from sqlalchemy import func

    from app.models import ActivityRecord, AgendaEvent, Attendance, Member

    today = date.today()
    start_month = today.replace(day=1)
    _, last_day = monthrange(today.year, today.month)
    end_month = today.replace(day=last_day)

    n_members = members_query(clube_id).count()

    agenda_q = agenda_query(clube_id)
    upcoming_events = (
        agenda_q.filter(AgendaEvent.event_date >= today)
        .order_by(AgendaEvent.event_date.asc(), AgendaEvent.event_time.asc())
        .limit(6)
        .all()
    )
    n_upcoming = agenda_q.filter(AgendaEvent.event_date >= today).count()

    n_posts = board_posts_query(clube_id).count()
    n_directorate = directorate_query(clube_id).count()

    att_rows = (
        db.session.query(Attendance.meeting_date, func.count(Attendance.id))
        .join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id)
        .filter(Attendance.meeting_date >= start_month)
        .filter(Attendance.meeting_date <= end_month)
        .filter(Attendance.present.is_(True))
        .group_by(Attendance.meeting_date)
        .all()
    )
    att_map = {row[0]: int(row[1]) for row in att_rows}

    attendance_labels = []
    attendance_counts = []
    d = start_month
    while d <= end_month:
        attendance_labels.append(d.strftime("%d/%m"))
        attendance_counts.append(att_map.get(d, 0))
        d += timedelta(days=1)

    unit_rows = (
        db.session.query(Member.unit, func.count(Member.id))
        .filter(Member.clube_id == clube_id)
        .group_by(Member.unit)
        .all()
    )
    unit_labels = []
    unit_counts = []
    for u, cnt in unit_rows:
        label = (u or "").strip() or "Sem unidade"
        unit_labels.append(label)
        unit_counts.append(int(cnt))

    recent_members = members_query(clube_id).order_by(Member.id.desc()).limit(8).all()

    act_rows = (
        db.session.query(ActivityRecord, Member)
        .join(Member, Member.id == ActivityRecord.member_id)
        .filter(Member.clube_id == clube_id)
        .order_by(ActivityRecord.recorded_at.desc(), ActivityRecord.id.desc())
        .limit(8)
        .all()
    )
    recent_activities = []
    for ar, mem in act_rows:
        rd = ar.recorded_at or today
        delta = (today - rd).days if isinstance(rd, date) else 0
        if delta <= 0:
            ago = "hoje"
        elif delta == 1:
            ago = "ontem"
        else:
            ago = f"há {delta} dias"
        recent_activities.append(
            {
                "member_name": mem.full_name,
                "title": ar.title,
                "ago": ago,
                "progress": ar.progress_percent or 0,
            }
        )

    return {
        "n_members": n_members,
        "n_upcoming": n_upcoming,
        "n_posts": n_posts,
        "n_directorate": n_directorate,
        "upcoming_events": upcoming_events,
        "attendance_labels": attendance_labels,
        "attendance_counts": attendance_counts,
        "unit_labels": unit_labels,
        "unit_counts": unit_counts,
        "recent_members": recent_members,
        "recent_activities": recent_activities,
    }
