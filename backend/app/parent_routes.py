import json
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
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
from app.agenda_service import (
    EVENT_CATEGORIES,
    batch_confirmed_counts,
    featured_upcoming,
    month_stats,
    reminder_for_events,
    serialize_event,
    timeline_events,
    toggle_rsvp,
    user_rsvp_map,
)
from app.member_wizard import CLUB_UNIT_OPTIONS
from app.access import parent_area_required
from app.finance_service import build_parent_finance_context, log_finance_action
from app.member_parent_link import children_for_parent
from app.parent_portal import (
    NEWS_LABELS,
    child_first_name,
    child_stats,
    club_ids_for_children,
    comunicados_count,
    feed_posts,
    gallery_images,
    monthly_attendance_chart,
    build_parent_club_directory,
    motivacional_message,
    notification_badges,
    parent_first_name,
    event_status_tag,
    journey_progress,
    recent_achievements,
    recent_fees_summary,
    resolve_children,
    safe_child_stats,
    time_greeting,
    upcoming_events,
    upcoming_events_count,
)
from sqlalchemy import and_, false, func, or_

from app.extensions import db
from app.finance_util import format_brl_cents
from app.activities_service import (
    build_parent_activities_page,
    ensure_member_notebook,
)
from app.models import (
    AgendaEvent,
    Attendance,
    BoardPost,
    DirectorateMember,
    HomeworkAssignment,
    HomeworkSubmission,
    HW_STATUS_SUBMITTED,
    MeetingDuque,
    Member,
    Club,
    MemberFee,
    PaymentProof,
    POST_KIND_COMUNICADO,
    POST_KIND_NOTICIA,
    PROOF_STATUS_PENDING,
)
from app.uploads_util import save_document_upload

bp = Blueprint("parent", __name__)


def _safe_url(endpoint: str, **values) -> str:
    """Gera URL sem derrubar o template se o endpoint ainda não estiver registrado."""
    try:
        return url_for(endpoint, **values)
    except Exception:
        return url_for("parent.home")


def _parent_nav_urls(child: Member | None = None) -> dict[str, str]:
    """URLs da sidebar — perfil usa ficha do filho quando existir."""
    profile = (
        url_for("parent.child_detail", member_id=child.id)
        if child
        else _safe_url("parent.home")
    )
    return {
        "home": _safe_url("parent.home"),
        "profile": profile,
        "progress": _safe_url("parent.parent_progress"),
        "specialties": _safe_url("parent.parent_specialties"),
        "activities": _safe_url("parent.parent_activities"),
        "agenda": _safe_url("parent.parent_agenda"),
        "gallery": _safe_url("parent.parent_gallery"),
        "finance": _safe_url("parent.parent_finance"),
        "communications": _safe_url("parent.parent_communications"),
        "members": _safe_url("parent.club_directory"),
        "directorate": _safe_url("parent.club_directorate"),
        "account": _safe_url("parent.account"),
    }


def _format_date_long_pt(d: date) -> str:
    return f"{d.day} de {MONTH_NAMES_PT[d.month]} de {d.year}"


def _member_id_from_request() -> int | None:
    raw = (request.args.get("filho") or request.args.get("member_id") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _empty_portal_stats() -> dict:
    return {
        "performance": 0,
        "attendance_rate": 0,
        "attendance_present": 0,
        "attendance_total": 0,
        "month_attendance_rate": 0,
        "notebook_pct": 0,
        "notebook_remaining": 30,
        "activities_done": 0,
        "activities_total": 0,
        "duques_total": 0,
        "class_label": "—",
        "unit": "—",
        "fees_pending": 0,
        "fees_overdue": 0,
        "finance_ok": True,
    }


def _portal_base_context():
    from app.member_parent_link import children_for_parent

    mid = _member_id_from_request()
    children = children_for_parent(current_user.id)
    child, _all = resolve_children(current_user, mid)
    if not child and children:
        child = children[0]
    club_ids = club_ids_for_children(children)
    stats = safe_child_stats(child)
    badges = notification_badges(current_user, club_ids, child)
    return {
        "portal_child": child,
        "portal_children": children,
        "portal_stats": stats,
        "portal_club_ids": club_ids,
        "portal_badges": badges,
        "portal_greeting": time_greeting(),
        "portal_parent_name": parent_first_name(current_user),
        "portal_comunicados_n": comunicados_count(club_ids, current_user.id),
        "portal_events_n": upcoming_events_count(club_ids),
        "news_labels": NEWS_LABELS,
    }


@bp.context_processor
def inject_parent_portal():
    if not request.endpoint or not str(request.endpoint).startswith("parent."):
        return {}
    try:
        from flask_login import current_user

        if not getattr(current_user, "is_authenticated", False):
            base = {
                "portal_child": None,
                "portal_children": [],
                "portal_stats": _empty_portal_stats(),
                "portal_badges": {"bell": 0, "chat": 0},
                "portal_greeting": time_greeting(),
                "portal_parent_name": "Responsável",
                "portal_comunicados_n": 0,
                "portal_events_n": 0,
                "news_labels": NEWS_LABELS,
            }
            base["portal_nav"] = _parent_nav_urls(None)
            return base
        from app.access import user_has_leadership_portal_access

        ctx = _portal_base_context()
        ctx["portal_nav"] = _parent_nav_urls(ctx.get("portal_child"))
        ctx["portal_show_admin_link"] = user_has_leadership_portal_access()
        return ctx
    except Exception:
        from flask import current_app

        from app.member_parent_link import children_for_parent as _children_for_parent

        current_app.logger.exception("Falha ao montar contexto do portal família")
        children = []
        child = None
        try:
            if getattr(current_user, "is_authenticated", False):
                children = _children_for_parent(current_user.id)
                child = children[0] if children else None
        except Exception:
            pass
        stats = safe_child_stats(child)
        base = {
            "portal_child": child,
            "portal_children": children,
            "portal_stats": stats,
            "portal_badges": {"bell": 0, "chat": 0},
            "portal_greeting": "Olá",
            "portal_parent_name": parent_first_name(current_user)
            if getattr(current_user, "is_authenticated", False)
            else "Responsável",
            "portal_comunicados_n": 0,
            "portal_events_n": 0,
            "news_labels": NEWS_LABELS,
        }
        base["portal_nav"] = _parent_nav_urls(child)
        base["portal_show_admin_link"] = False
        return base


@bp.before_request
@login_required
@parent_area_required
def _parent_guard():
    pass


@bp.route("/")
def home():
    ctx = _portal_base_context()
    child = ctx["portal_child"]
    club_ids = ctx["portal_club_ids"]
    stats = ctx["portal_stats"]
    posts = feed_posts(club_ids, 8)
    comunicados_posts = [p for p in posts if p.post_kind == POST_KIND_COMUNICADO]
    events = upcoming_events(club_ids, 5)
    achievements = recent_achievements(child, 5) if child else []
    chart = monthly_attendance_chart(child) if child else []
    motivacional = motivacional_message(child, stats) if child else None
    journey = journey_progress(stats, child) if child else None
    recent_fees = recent_fees_summary(child, 3) if child else []

    return render_template(
        "parent/home.html",
        feed_posts=posts,
        comunicados_posts=comunicados_posts,
        upcoming_events=events,
        achievements=achievements,
        portal_journey=journey,
        recent_fees=recent_fees,
        event_status_tag=event_status_tag,
        format_brl=format_brl_cents,
        chart_labels=json.dumps([p["label"] for p in chart]),
        chart_values=json.dumps([p["value"] for p in chart]),
        motivacional=motivacional,
        post_kind_comunicado=POST_KIND_COMUNICADO,
        post_kind_noticia=POST_KIND_NOTICIA,
        format_date_long_pt=_format_date_long_pt,
        **ctx,
    )


@bp.route("/agenda")
def parent_agenda():
    ctx = _portal_base_context()
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
    club_ids = ctx.get("portal_club_ids") or set()
    aq = AgendaEvent.query.filter(AgendaEvent.event_date >= start, AgendaEvent.event_date <= end)
    aq = aq.filter(AgendaEvent.status != "rascunho")
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

    event_ids = [e.id for e in month_events]
    rsvps = user_rsvp_map(event_ids, current_user.id)
    rsvp_counts = batch_confirmed_counts(event_ids)

    def _banner(ev):
        if ev.banner_filename:
            from flask import url_for

            return url_for("uploaded_file", rel_path=ev.banner_filename)
        return None

    serialized = [
        serialize_event(
            e,
            user_rsvp=rsvps.get(e.id),
            rsvp_count=rsvp_counts.get(e.id, 0),
            banner_url=_banner(e),
        )
        for e in month_events
    ]
    featured = featured_upcoming(month_events, today)
    featured_data = None
    if featured:
        fe = featured[0]
        featured_data = serialize_event(
            fe,
            rsvp_count=rsvp_counts.get(fe.id, 0),
            banner_url=_banner(fe),
        )
        featured_data["countdown_target"] = fe.event_date.isoformat()

    import json

    view = (request.args.get("view") or "month").strip().lower()
    if view not in ("month", "week", "day"):
        view = "month"

    month_names_short = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]

    return render_template(
        "parent/agenda_calendar.html",
        year=year,
        month=month,
        month_label=month_label,
        greeting_month=month_names_short[month - 1],
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
        agenda_events_json=json.dumps(serialized, ensure_ascii=False),
        month_stats=month_stats(month_events, today),
        featured_event=featured_data,
        timeline_events=[
            serialize_event(e, banner_url=_banner(e)) for e in timeline_events(month_events, today)
        ],
        agenda_reminder=reminder_for_events(month_events, today),
        agenda_categories=EVENT_CATEGORIES,
        agenda_units=CLUB_UNIT_OPTIONS,
        can_write_agenda=False,
        agenda_view=view,
        rsvp_child_id=ctx["portal_child"].id if ctx.get("portal_child") else None,
        **ctx,
    )


@bp.route("/agenda/<int:eid>/presenca", methods=["POST"])
@login_required
def parent_agenda_rsvp(eid):
    ctx = _portal_base_context()
    club_ids = ctx.get("portal_club_ids") or set()
    ev = db.session.get(AgendaEvent, eid)
    if not ev or (club_ids and ev.clube_id not in club_ids):
        flash("Evento não encontrado.", "warning")
        return redirect(url_for("parent.parent_agenda"))
    if (ev.status or "") == "rascunho":
        flash("Este evento não está disponível.", "warning")
        return redirect(url_for("parent.parent_agenda"))

    member_id = request.form.get("member_id", type=int)
    child = ctx.get("portal_child")
    if child and not member_id:
        member_id = child.id
    if member_id:
        allowed = {c.id for c in ctx.get("portal_children") or []}
        if member_id not in allowed:
            flash("Desbravador inválido.", "warning")
            return redirect(url_for("parent.parent_agenda"))
    try:
        status, count = toggle_rsvp(eid, current_user.id, member_id)
        if status == "confirmed":
            flash("Presença confirmada! Nos vemos no evento.", "success")
        else:
            flash("Confirmação cancelada.", "info")
    except ValueError as e:
        flash(str(e), "warning")
    ref = request.referrer or url_for("parent.parent_agenda")
    return redirect(ref)


@bp.route("/clube/membros")
def club_directory():
    children = children_for_parent(current_user.id)
    club_ids = club_ids_for_children(children)

    def _photo_url(rel: str | None) -> str | None:
        if not rel:
            return None
        return url_for("uploaded_file", rel_path=rel)

    directory = build_parent_club_directory(club_ids, _photo_url)
    return render_template("parent/club_directory.html", directory=directory)


@bp.route("/clube/diretoria")
def club_directorate():
    children = children_for_parent(current_user.id)
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    dq = DirectorateMember.query
    if club_ids:
        dq = dq.filter(DirectorateMember.clube_id.in_(club_ids))
    else:
        dq = dq.filter(DirectorateMember.id == -1)
    team = (
        dq.filter(DirectorateMember.status == "ativo")
        .order_by(DirectorateMember.display_order, DirectorateMember.full_name)
        .all()
    )
    return render_template("parent/club_directorate.html", team=team)


@bp.route("/noticias")
def news_feed():
    """Legado — redireciona para comunicados unificados."""
    return redirect(url_for("parent.parent_communications", **request.args))


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
    portal = _portal_base_context()
    all_children = portal.get("portal_children") or children_for_parent(current_user.id)
    active_child = portal.get("portal_child")
    children = [active_child] if active_child else all_children
    cid = None
    if children and getattr(children[0], "clube_id", None):
        cid = children[0].clube_id
    elif getattr(current_user, "perfil", None) and current_user.perfil.clube_id:
        cid = current_user.perfil.clube_id
    club_name = "Clube"
    if cid:
        club = db.session.get(Club, cid)
        if club:
            club_name = club.nome
    pf = build_parent_finance_context(children, cid, club_name)
    return render_template(
        "parent/finance.html",
        pf=pf,
        format_brl=format_brl_cents,
        **portal,
    )


@bp.route("/financeiro/comprovante/<int:fee_id>", methods=["POST"])
def parent_finance_proof(fee_id):
    children = children_for_parent(current_user.id)
    child_ids = {c.id for c in children}
    fee = db.session.get(MemberFee, fee_id)
    if not fee or fee.member_id not in child_ids:
        abort(404)
    if fee.paid_at:
        flash("Esta cobrança já está paga.", "info")
        return redirect(url_for("parent.parent_finance"))
    pending = (
        PaymentProof.query.filter_by(member_fee_id=fee.id, status=PROOF_STATUS_PENDING)
        .first()
    )
    if pending:
        flash("Já existe um comprovante em análise para esta cobrança.", "warning")
        return redirect(url_for("parent.parent_finance"))
    f = request.files.get("proof_file")
    saved = save_document_upload(f, current_app.config["UPLOAD_FOLDER"], "proofs")
    if not saved:
        flash("Envie uma imagem ou PDF válido.", "warning")
        return redirect(url_for("parent.parent_finance"))
    note = (request.form.get("note") or "").strip() or None
    proof = PaymentProof(
        member_fee_id=fee.id,
        user_id=current_user.id,
        filename=saved,
        note=note,
        status=PROOF_STATUS_PENDING,
    )
    db.session.add(proof)
    m = db.session.get(Member, fee.member_id)
    log_finance_action(
        m.clube_id if m else None,
        "proof_upload",
        user_id=current_user.id,
        entity_type="proof",
        entity_id=None,
        details={"fee_id": fee.id},
    )
    db.session.commit()
    flash("Comprovante enviado! A diretoria irá validar em breve.", "success")
    return redirect(url_for("parent.parent_finance"))


def _require_child():
    ctx = _portal_base_context()
    child = ctx["portal_child"]
    if not child:
        flash("Nenhum desbravador vinculado à sua conta.", "warning")
        return None, ctx
    return child, ctx


@bp.route("/perfil")
def parent_profile():
    child, ctx = _require_child()
    if not child:
        return redirect(url_for("parent.home"))
    return redirect(url_for("parent.child_detail", member_id=child.id))


@bp.route("/progresso")
def parent_progress():
    child, ctx = _require_child()
    if not child:
        return render_template("parent/progress.html", progress_page=None, **ctx)
    from app.progress_service import build_parent_progress_page

    stats = child_stats(child)
    progress_page = build_parent_progress_page(child, stats)
    return render_template(
        "parent/progress.html",
        progress_page=progress_page,
        **ctx,
    )


@bp.route("/especialidades")
def parent_specialties():
    child, ctx = _require_child()

    def _icon_url(rel: str | None) -> str | None:
        if not rel:
            return None
        return url_for("uploaded_file", rel_path=rel)

    from app.specialties_service import build_parent_specialties_album

    album = (
        build_parent_specialties_album(child, photo_url_builder=_icon_url)
        if child
        else {
            "cards": [],
            "categories": [],
            "stats": {
                "completed": 0,
                "in_progress": 0,
                "available": 0,
                "total": 512,
                "percent": 0,
                "progress_label": "0 / 512",
            },
        }
    )
    return render_template("parent/specialties.html", album=album, **ctx)


@bp.route("/atividades")
def parent_activities():
    child, ctx = _require_child()
    act_page = None
    if child:
        ensure_member_notebook(child)
        db.session.commit()
        act_page = build_parent_activities_page(child)
        if act_page:
            act_page["homework_submit_url"] = url_for("parent.parent_activities_submit")
            act_page["achievements"]["progress_url"] = url_for("parent.parent_progress")
            act_page["communications_url"] = url_for("parent.parent_communications")
    return render_template(
        "parent/activities.html",
        act_page=act_page,
        **ctx,
    )


@bp.route("/atividades/enviar", methods=["POST"])
def parent_activities_submit():
    child, ctx = _require_child()
    if not child:
        flash("Selecione um desbravador.", "warning")
        return redirect(url_for("parent.parent_activities"))
    hw_id = request.form.get("assignment_id", type=int)
    if not hw_id:
        flash("Tarefa inválida.", "warning")
        return redirect(url_for("parent.parent_activities"))
    hw = HomeworkAssignment.query.filter_by(id=hw_id, clube_id=child.clube_id, active=True).first_or_404()
    existing = HomeworkSubmission.query.filter_by(assignment_id=hw.id, member_id=child.id).first()
    evidence_type = (request.form.get("evidence_type") or "texto").strip()
    text_content = (request.form.get("text_content") or "").strip()
    filename = None
    f = request.files.get("evidence_file")
    if f and f.filename:
        filename = save_document_upload(f, current_app.config["UPLOAD_FOLDER"], "homework_evidence")
        if not evidence_type or evidence_type == "texto":
            ext = f.filename.rsplit(".", 1)[-1].lower()
            if ext in ("jpg", "jpeg", "png", "webp", "gif"):
                evidence_type = "foto"
            elif ext in ("mp4", "webm", "mov"):
                evidence_type = "video"
            elif ext == "pdf":
                evidence_type = "pdf"
            else:
                evidence_type = "arquivo"
    if existing:
        existing.status = HW_STATUS_SUBMITTED
        existing.evidence_type = evidence_type
        existing.text_content = text_content or existing.text_content
        if filename:
            existing.filename = filename
        existing.submitted_at = datetime.utcnow()
    else:
        db.session.add(
            HomeworkSubmission(
                assignment_id=hw.id,
                member_id=child.id,
                status=HW_STATUS_SUBMITTED,
                evidence_type=evidence_type,
                text_content=text_content or None,
                filename=filename,
            )
        )
    db.session.commit()
    flash("Evidência enviada! Aguarde avaliação da diretoria.", "success")
    return redirect(url_for("parent.parent_activities"))


@bp.route("/eventos")
def parent_events():
    return redirect(url_for("parent.parent_agenda"))


@bp.route("/galeria")
def parent_gallery():
    ctx = _portal_base_context()
    imgs = gallery_images(ctx["portal_club_ids"], ctx["portal_child"])
    return render_template("parent/gallery.html", gallery_images=imgs, **ctx)


@bp.route("/comunicados")
def parent_communications():
    filt = (request.args.get("filtro") or "todos").strip().lower()
    ctx = _portal_base_context()
    club_ids = ctx.get("portal_club_ids") or set()
    from app.communications_service import build_communications_page

    page = build_communications_page(
        clube_ids=club_ids,
        clube_id=None,
        active_filter=filt,
        user_id=current_user.id,
    )
    return render_template(
        "parent/communications.html",
        **ctx,
        **page,
    )


@bp.route("/comunicados/<int:post_id>/lido", methods=["POST"])
def parent_mark_comunicado_read(post_id):
    children = children_for_parent(current_user.id)
    club_ids = {c.clube_id for c in children if getattr(c, "clube_id", None)}
    post = BoardPost.query.filter_by(id=post_id, post_kind=POST_KIND_COMUNICADO).first_or_404()
    if post.clube_id not in club_ids:
        flash("Comunicado não encontrado.", "warning")
        return redirect(url_for("parent.parent_communications"))
    from app.communications_service import mark_post_read

    mark_post_read(post_id, current_user.id)
    nxt = request.form.get("next") or request.referrer
    if nxt:
        return redirect(nxt)
    return redirect(url_for("parent.parent_communications"))


@bp.route("/documentos")
def parent_documents():
    """Legado — redireciona para o perfil do desbravador."""
    child, _ctx = _require_child()
    if child:
        return redirect(url_for("parent.child_detail", member_id=child.id))
    return redirect(url_for("parent.home"))


@bp.route("/filho/<int:member_id>")
def child_detail(member_id):
    from app.member_profile import build_member_profile_context

    m = Member.query.get_or_404(member_id)
    if m.parent_id != current_user.id:
        flash("Você não tem permissão para ver este perfil.", "danger")
        return redirect(url_for("parent.home"))

    ctx = _portal_base_context()
    ctx["portal_child"] = m
    ctx["portal_stats"] = safe_child_stats(m)
    ctx["portal_nav"] = _parent_nav_urls(m)
    profile_ctx = build_member_profile_context(
        m, mode="parent", linked_parent=current_user
    )
    return render_template(
        "parent/child_detail.html",
        member=m,
        **ctx,
        **profile_ctx,
    )
