from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.agenda_calendar_util import (
    MONTH_NAMES_PT,
    agenda_add_months,
    agenda_clamp_day_in_month,
    agenda_month_bounds,
    agenda_resolve_selected_day,
    agenda_sort_day_events,
    agenda_weeks,
)
from app.access import parent_area_required
from app.club_services import get_pix_for_club
from sqlalchemy import and_, false, func, or_

from app.extensions import db
from app.finance_util import format_brl_cents
from app.models import (
    ActivityRecord,
    AgendaEvent,
    Attendance,
    BoardPost,
    DirectorateMember,
    MeetingDuque,
    Member,
    MemberFee,
    POST_KIND_COMUNICADO,
    POST_KIND_NOTICIA,
)

bp = Blueprint("parent", __name__)


def _format_date_long_pt(d: date) -> str:
    return f"{d.day} de {MONTH_NAMES_PT[d.month]} de {d.year}"


NEWS_LABELS = {
    "local": "Local",
    "regional": "Regional",
    "estadual": "Estadual",
    "mundial": "Mundial",
}


@bp.before_request
@login_required
@parent_area_required
def _parent_guard():
    pass


@bp.route("/")
def home():
    children = list(current_user.children)
    duques_by_member = {}
    if children:
        ids = [c.id for c in children]
        q = (
            db.session.query(MeetingDuque.member_id, func.sum(MeetingDuque.duques))
            .filter(MeetingDuque.member_id.in_(ids))
            .group_by(MeetingDuque.member_id)
            .all()
        )
        duques_by_member = {mid: int(t or 0) for mid, t in q}
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    if club_ids:
        feed_posts = (
            BoardPost.query.filter(BoardPost.clube_id.in_(club_ids))
            .order_by(BoardPost.created_at.desc())
            .limit(24)
            .all()
        )
    else:
        feed_posts = []

    primary_child = children[0] if children else None
    recent_activity = None
    last_duques_delta = None
    if primary_child:
        recent_activity = (
            ActivityRecord.query.filter_by(member_id=primary_child.id)
            .order_by(ActivityRecord.recorded_at.desc(), ActivityRecord.id.desc())
            .first()
        )
        last_duque_row = (
            MeetingDuque.query.filter_by(member_id=primary_child.id)
            .order_by(MeetingDuque.meeting_date.desc(), MeetingDuque.id.desc())
            .first()
        )
        if last_duque_row and (last_duque_row.duques or 0) > 0:
            last_duques_delta = int(last_duque_row.duques)

    greeting_first = (
        (current_user.full_name or "").strip().split()[0]
        if (current_user.full_name or "").strip()
        else "Responsável"
    )

    return render_template(
        "parent/home.html",
        children=children,
        primary_child=primary_child,
        duques_by_member=duques_by_member,
        feed_posts=feed_posts,
        news_labels=NEWS_LABELS,
        post_kind_comunicado=POST_KIND_COMUNICADO,
        post_kind_noticia=POST_KIND_NOTICIA,
        recent_activity=recent_activity,
        last_duques_delta=last_duques_delta,
        greeting_first=greeting_first,
        format_date_long_pt=_format_date_long_pt,
    )


@bp.route("/agenda")
def parent_agenda():
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
    children = list(current_user.children)
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    aq = AgendaEvent.query.filter(AgendaEvent.event_date >= start, AgendaEvent.event_date <= end)
    if club_ids:
        aq = aq.filter(AgendaEvent.clube_id.in_(club_ids))
    else:
        aq = aq.filter(AgendaEvent.id == -1)
    month_events = aq.order_by(AgendaEvent.event_date.asc(), AgendaEvent.id.asc()).all()
    events_by_date = {}
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

    return render_template(
        "parent/agenda_calendar.html",
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


@bp.route("/clube/membros")
def club_directory():
    children = list(current_user.children)
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    mq = Member.query
    if club_ids:
        mq = mq.filter(Member.clube_id.in_(club_ids))
    else:
        mq = mq.filter(Member.id == -1)
    members = mq.order_by(Member.full_name).all()
    return render_template("parent/club_directory.html", members=members)


@bp.route("/clube/diretoria")
def club_directorate():
    children = list(current_user.children)
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    dq = DirectorateMember.query
    if club_ids:
        dq = dq.filter(DirectorateMember.clube_id.in_(club_ids))
    else:
        dq = dq.filter(DirectorateMember.id == -1)
    team = dq.order_by(DirectorateMember.display_order, DirectorateMember.full_name).all()
    return render_template("parent/club_directorate.html", team=team)


@bp.route("/noticias")
def news_feed():
    level = (request.args.get("nivel") or "").strip()
    tipo = (request.args.get("tipo") or "").strip().lower()
    active_level = level if level in NEWS_LABELS else None
    active_type = tipo if tipo in {"todos", "avisos", "noticias"} else "todos"

    children = list(current_user.children)
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    q = BoardPost.query
    if club_ids:
        q = q.filter(BoardPost.clube_id.in_(club_ids))
    else:
        q = q.filter(false())

    if active_type == "avisos":
        q = q.filter(BoardPost.post_kind == POST_KIND_COMUNICADO)
    elif active_type == "noticias":
        q = q.filter(BoardPost.post_kind == POST_KIND_NOTICIA)
    else:
        # todos
        if active_level:
            q = q.filter(
                or_(
                    BoardPost.post_kind == POST_KIND_COMUNICADO,
                    and_(
                        BoardPost.post_kind == POST_KIND_NOTICIA,
                        BoardPost.level == active_level,
                    ),
                )
            )
    if active_type == "noticias" and active_level:
        q = q.filter(BoardPost.level == active_level)

    rows = q.order_by(BoardPost.created_at.desc()).limit(80).all()

    merged_items = []
    for p in rows:
        if p.post_kind == POST_KIND_NOTICIA:
            label = NEWS_LABELS.get(p.level or "local", "Notícia")
        else:
            label = "Comunicado"
        merged_items.append(
            {
                "post_kind": p.post_kind,
                "title": p.title,
                "body": p.body,
                "created_at": p.created_at,
                "label": label,
                "level": p.level,
                "image_filename": p.image_filename,
            }
        )

    return render_template(
        "parent/news_feed.html",
        items=merged_items,
        active_level=active_level,
        active_type=active_type,
        news_labels=NEWS_LABELS,
    )


@bp.route("/conta", methods=["GET", "POST"])
def account():
    from app.auth import _ensure_profile_for_user

    _ensure_profile_for_user(current_user)
    db.session.commit()
    if request.method == "POST":
        from app.auth import process_account_form

        process_account_form()
        return redirect(url_for("parent.account"))
    return render_template("parent/account.html")


@bp.route("/financeiro")
def parent_finance():
    children = list(current_user.children)
    by_member = {c.id: c for c in children}
    cid = None
    if children and getattr(children[0], "clube_id", None):
        cid = children[0].clube_id
    elif getattr(current_user, "perfil", None) and current_user.perfil.clube_id:
        cid = current_user.perfil.clube_id
    pix_key = get_pix_for_club(cid) if cid else ""
    if not children:
        return render_template(
            "parent/finance.html",
            children=[],
            fees=[],
            by_member=by_member,
            today=date.today(),
            format_brl=format_brl_cents,
            pix_key=pix_key,
        )
    ids = [c.id for c in children]
    fees = (
        MemberFee.query.filter(MemberFee.member_id.in_(ids))
        .order_by(MemberFee.due_date.desc(), MemberFee.id.desc())
        .all()
    )
    return render_template(
        "parent/finance.html",
        children=children,
        fees=fees,
        by_member=by_member,
        today=date.today(),
        format_brl=format_brl_cents,
        pix_key=pix_key,
    )


@bp.route("/filho/<int:member_id>")
def child_detail(member_id):
    m = Member.query.get_or_404(member_id)
    if m.parent_id != current_user.id:
        flash("Você não tem permissão para ver este perfil.", "danger")
        return redirect(url_for("parent.home"))

    activities = (
        ActivityRecord.query.filter_by(member_id=m.id)
        .order_by(ActivityRecord.recorded_at.desc())
        .limit(40)
        .all()
    )
    done = [a for a in activities if a.completed]
    open_act = [a for a in activities if not a.completed]
    attendances = (
        Attendance.query.filter_by(member_id=m.id)
        .order_by(Attendance.meeting_date.desc())
        .limit(40)
        .all()
    )
    pr, tot_all, att_rate = m.attendance_stats()
    act_avg = m.activity_progress_avg()
    duques_total = (
        db.session.query(func.coalesce(func.sum(MeetingDuque.duques), 0))
        .filter(MeetingDuque.member_id == m.id)
        .scalar()
        or 0
    )
    duques_rows = (
        MeetingDuque.query.filter_by(member_id=m.id)
        .order_by(MeetingDuque.meeting_date.desc(), MeetingDuque.id.desc())
        .limit(24)
        .all()
    )
    fees = (
        MemberFee.query.filter_by(member_id=m.id)
        .order_by(MemberFee.due_date.desc(), MemberFee.id.desc())
        .all()
    )
    return render_template(
        "parent/child_detail.html",
        member=m,
        activities_open=open_act,
        activities_done=done,
        attendances=attendances,
        present_count=pr,
        attendance_total=tot_all,
        attendance_rate=att_rate if tot_all else None,
        activity_avg=act_avg,
        duques_total=int(duques_total),
        duques_rows=duques_rows,
        notebook_checklist_pct=m.notebook_checklist_progress_percent(),
        fees=fees,
        today=date.today(),
        format_brl=format_brl_cents,
    )
