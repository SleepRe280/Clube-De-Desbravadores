"""Dados e utilitários para o portal moderno dos responsáveis."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import (
    ActivityRecord,
    AgendaEvent,
    Attendance,
    BoardPost,
    ClubUnit,
    ClubUnitRole,
    Member,
    MemberFee,
    MeetingDuque,
    POST_KIND_COMUNICADO,
    POST_KIND_NOTICIA,
    User,
)

NEWS_LABELS = {
    "local": "Local",
    "regional": "Regional",
    "estadual": "Estadual",
    "mundial": "Mundial",
}


def time_greeting() -> str:
    h = datetime.now().hour
    if h < 12:
        return "Bom dia"
    if h < 18:
        return "Boa tarde"
    return "Boa noite"


def parent_first_name(user: User) -> str:
    name = (user.full_name or "").strip()
    return name.split()[0] if name else "Responsável"


def child_first_name(member: Member) -> str:
    return (member.full_name or "").strip().split()[0] or "Desbravador"


def resolve_children(user: User, member_id: int | None = None) -> tuple[Member | None, list[Member]]:
    from app.member_parent_link import portal_children_for_user

    return portal_children_for_user(user, member_id)


def safe_child_stats(member: Member | None) -> dict:
    """Estatísticas do filho sem derrubar o portal se algum dado estiver incompleto."""
    if not member:
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
    try:
        return child_stats(member)
    except Exception:
        return {
            "performance": member.computed_overall_performance()
            if hasattr(member, "computed_overall_performance")
            else 0,
            "attendance_rate": 0,
            "attendance_present": 0,
            "attendance_total": 0,
            "month_attendance_rate": 0,
            "notebook_pct": member.notebook_checklist_progress_percent()
            if hasattr(member, "notebook_checklist_progress_percent")
            else 0,
            "notebook_remaining": 30,
            "activities_done": 0,
            "activities_total": 0,
            "duques_total": 0,
            "class_label": member.notebook_current or "—",
            "unit": member.unit or "—",
            "fees_pending": 0,
            "fees_overdue": 0,
            "finance_ok": True,
        }


def club_ids_for_children(children: list[Member]) -> set[str]:
    return {c.clube_id for c in children if getattr(c, "clube_id", None)}


def child_stats(member: Member) -> dict:
    pr, tot, att_rate = member.attendance_stats()
    perf = member.computed_overall_performance()
    notebook_pct = member.notebook_checklist_progress_percent()
    activities = list(member.activities)
    done_acts = [a for a in activities if a.completed]
    duques_total = (
        db.session.query(func.coalesce(func.sum(MeetingDuque.duques), 0))
        .filter(MeetingDuque.member_id == member.id)
        .scalar()
        or 0
    )
    month_start = date.today().replace(day=1)
    month_att = (
        Attendance.query.filter(
            Attendance.member_id == member.id,
            Attendance.meeting_date >= month_start,
        ).all()
    )
    month_present = sum(1 for a in month_att if a.present)
    month_total = len(month_att)
    month_rate = round(100 * month_present / month_total) if month_total else att_rate

    fees = list(member.fees.order_by(MemberFee.due_date.desc()).limit(12))
    pending = [f for f in fees if not f.paid_at]
    overdue = [f for f in pending if f.due_date < date.today()]

    sp_summary = {}
    try:
        from app.specialties_service import member_progress_summary

        sp_summary = member_progress_summary(member, member.clube_id)
    except Exception:
        sp_summary = {}

    return {
        "performance": perf,
        "attendance_rate": att_rate if tot else month_rate,
        "attendance_present": pr,
        "attendance_total": tot,
        "month_attendance_rate": month_rate,
        "notebook_pct": notebook_pct,
        "notebook_remaining": max(0, 30 - round(30 * notebook_pct / 100)),
        "activities_done": len(done_acts),
        "activities_total": len(activities),
        "duques_total": int(duques_total),
        "class_label": member.notebook_current or "Classe em progresso",
        "unit": member.unit or "Unidade",
        "fees_pending": len(pending),
        "fees_overdue": len(overdue),
        "finance_ok": len(overdue) == 0 and len(pending) == 0,
        "specialties_completed": sp_summary.get("completed_count", 0),
        "specialties_in_progress": sp_summary.get("in_progress_count", 0),
        "specialties_pending": sp_summary.get("pending_count", 0),
        "specialties_progress_label": sp_summary.get("progress_label", "0 / 512"),
        "specialties_progress_percent": sp_summary.get("progress_percent", 0),
        "specialties_points": sp_summary.get("points_total", 0),
        "specialties_categories": sp_summary.get("categories_label", "0 / 8"),
    }


def upcoming_events_count(club_ids: set[str], within_days: int = 60) -> int:
    if not club_ids:
        return 0
    today = date.today()
    until = today + timedelta(days=within_days)
    return (
        AgendaEvent.query.filter(
            AgendaEvent.clube_id.in_(club_ids),
            AgendaEvent.event_date >= today,
            AgendaEvent.event_date <= until,
        ).count()
    )


def upcoming_events(club_ids: set[str], limit: int = 6) -> list[AgendaEvent]:
    if not club_ids:
        return []
    today = date.today()
    return (
        AgendaEvent.query.filter(
            AgendaEvent.clube_id.in_(club_ids),
            AgendaEvent.event_date >= today,
        )
        .order_by(AgendaEvent.event_date.asc(), AgendaEvent.id.asc())
        .limit(limit)
        .all()
    )


def feed_posts(club_ids: set[str], limit: int = 12) -> list[BoardPost]:
    if not club_ids:
        return []
    return (
        BoardPost.query.filter(BoardPost.clube_id.in_(club_ids))
        .order_by(BoardPost.created_at.desc())
        .limit(limit)
        .all()
    )


def comunicados_count(club_ids: set[str], user_id: int | None = None) -> int:
    if not club_ids:
        return 0
    week_ago = datetime.utcnow() - timedelta(days=14)
    q = BoardPost.query.filter(
        BoardPost.clube_id.in_(club_ids),
        BoardPost.post_kind == POST_KIND_COMUNICADO,
        BoardPost.created_at >= week_ago,
    )
    if user_id:
        from app.models import BoardPostRead

        read_ids = select(BoardPostRead.post_id).where(BoardPostRead.user_id == user_id)
        q = q.filter(~BoardPost.id.in_(read_ids))
    return q.count()


def recent_achievements(member: Member, limit: int = 5) -> list[dict]:
    items = []
    try:
        from app.specialties_service import recent_specialty_achievements

        for sp in recent_specialty_achievements(member, limit=limit):
            items.append(
                {
                    "title": sp["title"],
                    "date": sp["date"],
                    "kind": "especialidade",
                    "icon": "medal",
                }
            )
    except Exception:
        pass
    for a in (
        ActivityRecord.query.filter_by(member_id=member.id, completed=True)
        .order_by(ActivityRecord.recorded_at.desc())
        .limit(limit)
        .all()
    ):
        items.append(
            {
                "title": a.title,
                "date": a.recorded_at,
                "kind": "atividade",
                "icon": "trophy",
            }
        )
    if len(items) < limit:
        for d in (
            MeetingDuque.query.filter_by(member_id=member.id)
            .order_by(MeetingDuque.meeting_date.desc())
            .limit(limit - len(items))
            .all()
        ):
            if (d.duques or 0) > 0:
                items.append(
                    {
                        "title": f"+{d.duques} duques na reunião",
                        "date": d.meeting_date,
                        "kind": "duques",
                        "icon": "star",
                    }
                )
    return items[:limit]


def monthly_attendance_chart(member: Member) -> list[dict]:
    """Últimos 5 meses — taxa de presença por mês."""
    today = date.today()
    points = []
    for i in range(4, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(y, m + 1, 1) - timedelta(days=1)
        rows = Attendance.query.filter(
            Attendance.member_id == member.id,
            Attendance.meeting_date >= start,
            Attendance.meeting_date <= end,
        ).all()
        rate = round(100 * sum(1 for r in rows if r.present) / len(rows)) if rows else 0
        labels = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")
        points.append({"label": labels[m - 1], "value": rate})
    return points


def specialty_cards(member: Member, *, photo_url_builder=None) -> list[dict]:
    """Cards gamificados do catálogo de especialidades (portal dos pais)."""
    from app.specialties_service import specialty_cards_for_member

    raw = specialty_cards_for_member(member, photo_url_builder=photo_url_builder)
    cards = []
    for c in raw:
        status = c.get("status", "nao_iniciada")
        if status == "concluida":
            st = "concluida"
        elif status == "bloqueada":
            st = "bloqueada"
        elif status in ("em_andamento", "aguardando_aprovacao"):
            st = "em_andamento"
        else:
            st = "bloqueada"
        cards.append(
            {
                "name": c["name"],
                "category": c["category"],
                "status": st,
                "progress": c.get("progress", 0),
                "icon": c.get("icon_emoji", "🎖️"),
                "icon_emoji": c.get("icon_emoji", "🎖️"),
                "icon_url": c.get("icon_url"),
                "color_hex": c.get("color_hex", "#3b82f6"),
                "locked": c.get("locked", False),
                "points": c.get("points", 0),
            }
        )
    return cards


def gallery_images(club_ids: set[str], member: Member | None = None, limit: int = 24) -> list[dict]:
    if not club_ids:
        return []
    from app.models import GalleryPhoto

    photos = (
        GalleryPhoto.query.filter(
            GalleryPhoto.clube_id.in_(club_ids),
            GalleryPhoto.is_trashed.is_(False),
        )
        .order_by(GalleryPhoto.created_at.desc())
        .limit(limit)
        .all()
    )
    if photos:
        out = []
        for p in photos:
            out.append(
                {
                    "src": p.filename or "",
                    "title": p.title or (p.album.title if p.album else ""),
                    "date": p.created_at,
                    "post_kind": "galeria",
                }
            )
        return out
    q = BoardPost.query.filter(
        BoardPost.clube_id.in_(club_ids),
        BoardPost.image_filename.isnot(None),
    ).order_by(BoardPost.created_at.desc())
    out = []
    for p in q.limit(limit * 2):
        out.append(
            {
                "src": p.image_filename,
                "title": p.title,
                "date": p.created_at,
                "post_kind": p.post_kind,
            }
        )
        if len(out) >= limit:
            break
    return out


def notification_badges(user: User, club_ids: set[str], child: Member | None) -> dict:
    badges = {"bell": 0, "chat": 0}
    badges["bell"] = comunicados_count(club_ids, getattr(user, "id", None))
    if child:
        st = child_stats(child)
        if st["fees_overdue"]:
            badges["bell"] += st["fees_overdue"]
        if st["fees_pending"]:
            badges["chat"] += min(st["fees_pending"], 3)
    return badges


JOURNEY_LEVELS = (
    {"id": "aspirante", "label": "Aspirante", "min_xp": 0},
    {"id": "explorador", "label": "Explorador", "min_xp": 200},
    {"id": "guardiao", "label": "Guardião", "min_xp": 450},
    {"id": "elite", "label": "Elite", "min_xp": 750},
    {"id": "lendario", "label": "Lendário", "min_xp": 1000},
)


def journey_xp(stats: dict, member: Member | None = None) -> int:
    """Pontos de experiência gamificados para a jornada do desbravador."""
    if member:
        try:
            from app.progress_service import compute_xp

            return compute_xp(member, sp_completed=stats.get("specialties_completed", 0))["total"]
        except Exception:
            pass
    from app.progress_service import journey_xp_from_stats

    return journey_xp_from_stats(stats)


def journey_progress(stats: dict, member: Member | None = None) -> dict:
    """Estado da trilha de níveis para o dashboard (compatível com progress_service)."""
    if member:
        try:
            from app.progress_service import build_parent_progress_page

            page = build_parent_progress_page(member, stats)
            hero = page["hero"]
            return {
                "xp": hero["xp"],
                "level_index": hero["level"] - 1,
                "level_label": hero["level_title"],
                "level_number": hero["level"],
                "xp_in_level": hero["xp"] - ((hero["level"] - 1) * 120),
                "xp_to_next": hero["xp_to_next"],
                "xp_level_max": hero["xp_level_max"],
                "xp_level_start": (hero["level"] - 1) * 120,
                "progress_pct": hero["progress_pct"],
                "levels": [
                    {
                        "id": f"n{m['level']}",
                        "label": m["label"],
                        "min_xp": (m["level"] - 1) * 120,
                        "next_xp": m["level"] * 120,
                        "state": m["state"],
                    }
                    for m in page["journey"]["milestones"]
                ],
                "next_goal_label": page["next_objective"]["headline"],
            }
        except Exception:
            pass

    xp = journey_xp(stats, member)
    levels = []
    current_idx = 0
    for i, lv in enumerate(JOURNEY_LEVELS):
        nxt = JOURNEY_LEVELS[i + 1]["min_xp"] if i + 1 < len(JOURNEY_LEVELS) else lv["min_xp"] + 250
        if xp >= lv["min_xp"]:
            current_idx = i
        levels.append(
            {
                "id": lv["id"],
                "label": lv["label"],
                "min_xp": lv["min_xp"],
                "next_xp": nxt,
            }
        )

    cur = levels[current_idx]
    nxt_xp = cur["next_xp"]
    span = max(1, nxt_xp - cur["min_xp"])
    in_level = min(span, max(0, xp - cur["min_xp"]))
    pct = round(100 * in_level / span)

    for i, row in enumerate(levels):
        if i < current_idx:
            row["state"] = "done"
        elif i == current_idx:
            row["state"] = "current"
        else:
            row["state"] = "locked"

    return {
        "xp": xp,
        "level_index": current_idx,
        "level_label": cur["label"],
        "level_number": current_idx + 1,
        "xp_in_level": in_level,
        "xp_to_next": max(0, nxt_xp - xp),
        "xp_level_max": nxt_xp,
        "xp_level_start": cur["min_xp"],
        "progress_pct": pct,
        "levels": levels,
        "next_goal_label": _journey_next_goal(stats),
    }


def _journey_next_goal(stats: dict) -> str:
    remaining = int(stats.get("notebook_remaining", 0) or 0)
    if remaining > 0:
        return f"Concluir {min(2, remaining)} itens do caderno"
    sp = int(stats.get("specialties_pending", 0) or 0)
    if sp > 0:
        return f"Iniciar {min(2, sp)} especialidades"
    return "Participar do próximo evento do clube"


_MONTH_PT = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


def recent_fees_summary(member: Member | None, limit: int = 3) -> list[dict]:
    if not member:
        return []
    fees = member.fees.order_by(MemberFee.due_date.desc()).limit(limit).all()
    out = []
    for f in fees:
        d = f.due_date
        label = f"{_MONTH_PT[d.month - 1]} {d.year}" if d else "Cobrança"
        out.append(
            {
                "label": label,
                "amount_cents": f.amount_cents,
                "paid": bool(f.paid_at),
                "paid_at": f.paid_at,
                "due_date": d,
            }
        )
    return out


def event_status_tag(
    event_date: date, index: int = 0, status: str | None = None
) -> tuple[str, str]:
    """Retorna (rótulo, classe CSS) para tags de eventos."""
    st = (status or "").strip().lower()
    if st in ("confirmado", "confirmed"):
        return ("Confirmado", "ok")
    if st in ("em_breve", "soon"):
        return ("Em breve", "warn")
    if st in ("planejado", "planned", "rascunho"):
        return ("Planejado", "info")
    today = date.today()
    delta = (event_date - today).days if event_date else 99
    if delta <= 7:
        return ("Confirmado", "ok")
    if delta <= 21:
        return ("Em breve", "warn")
    return ("Planejado", "info")


def motivacional_message(child: Member, stats: dict) -> str:
    name = child_first_name(child)
    if stats["activities_done"] >= 4:
        return f"Parabéns! {name} participou de {stats['activities_done']} atividades registradas."
    if stats["month_attendance_rate"] >= 90:
        return f"Excelente! {name} está com {stats['month_attendance_rate']}% de frequência."
    if stats["notebook_pct"] >= 50:
        return f"{name} já completou {stats['notebook_pct']}% do caderno — continue assim!"
    return f"Acompanhe a evolução de {name} e celebre cada conquista no clube."


def build_parent_club_directory(
    club_ids: set[str],
    photo_url_builder,
) -> dict:
    """Lista pública de membros do clube — somente dados básicos para responsáveis."""
    from app.units_service import _role_display

    mq = Member.query
    if club_ids:
        mq = mq.filter(Member.clube_id.in_(club_ids))
    else:
        mq = mq.filter(Member.id == -1)
    mq = mq.filter(
        or_(
            Member.member_status.is_(None),
            Member.member_status == "",
            Member.member_status == "ativo",
        )
    )
    members = mq.order_by(Member.full_name).all()

    roles_cache: dict[tuple[str, str], dict[str, ClubUnitRole]] = {}

    def roles_for(clube_id: str | None, unit_name: str | None) -> dict[str, ClubUnitRole]:
        cid = clube_id or ""
        uname = (unit_name or "").strip()
        key = (cid, uname)
        if key not in roles_cache:
            unit = (
                ClubUnit.query.filter_by(clube_id=cid, name=uname).first()
                if cid and uname
                else None
            )
            if unit:
                roles = ClubUnitRole.query.filter_by(unit_id=unit.id).all()
                roles_cache[key] = {r.name: r for r in roles}
            else:
                roles_cache[key] = {}
        return roles_cache[key]

    cards: list[dict] = []
    unit_options: set[str] = set()
    role_options: set[str] = set()

    for member in members:
        unit_name = (member.unit or "").strip() or "Sem unidade"
        rd = _role_display(member, roles_for(member.clube_id, member.unit))
        role_label = rd["label"]
        unit_options.add(unit_name)
        role_options.add(role_label)

        photo_url = None
        if member.photo_filename and photo_url_builder:
            photo_url = photo_url_builder(member.photo_filename)

        cards.append(
            {
                "full_name": member.full_name,
                "initial": (member.full_name or "?")[0].upper(),
                "photo_url": photo_url,
                "age_years": member.age_years,
                "unit_name": unit_name,
                "role_label": role_label,
                "role_color": rd["color_key"],
            }
        )

    total = len(cards)
    return {
        "members": cards,
        "total": total,
        "total_label": f"{total} desbravador{'es' if total != 1 else ''}",
        "unit_options": sorted(unit_options, key=lambda s: s.lower()),
        "role_options": sorted(role_options, key=lambda s: s.lower()),
    }
