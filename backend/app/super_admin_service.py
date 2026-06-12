"""Dados agregados para o painel Super Admin."""

from __future__ import annotations

from calendar import month_abbr
from datetime import datetime, timedelta

from sqlalchemy import func, or_

from app.access import cargos_for_profile
from app.extensions import db
from app.models import (
    AgendaEvent,
    BoardPost,
    CARGO_DIRETOR,
    CARGO_PAI,
    CARGO_SUPER_ADMIN,
    Club,
    LeadershipAuditLog,
    Member,
    Profile,
    User,
)

CARGO_LABELS = {
    CARGO_SUPER_ADMIN: "Super Admin",
    CARGO_DIRETOR: "Diretor",
    CARGO_PAI: "Responsável",
    "tesoureiro": "Tesoureiro",
    "secretario": "Secretário",
    "conselheiro": "Conselheiro",
}


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _ago_label(dt: datetime | None) -> str:
    if not dt:
        return "—"
    delta = datetime.utcnow() - dt
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "agora"
    if mins < 60:
        return f"há {mins} min"
    hours = mins // 60
    if hours < 24:
        return f"há {hours}h"
    days = hours // 24
    if days < 30:
        return f"há {days} dia{'s' if days > 1 else ''}"
    return dt.strftime("%d/%m/%Y")


def _cargo_label(profile: Profile | None) -> str:
    if not profile:
        return "—"
    return CARGO_LABELS.get(profile.cargo, profile.cargo.replace("_", " ").title())


def global_counts() -> dict:
    profiles = Profile.query.all()
    now = datetime.utcnow()
    month_start = _month_start(now)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    clubs_total = Club.query.count()
    clubs_this_month = Club.query.filter(Club.criado_em >= month_start).count()
    clubs_prev_month = Club.query.filter(
        Club.criado_em >= prev_month_start, Club.criado_em < month_start
    ).count()

    users_total = User.query.count()
    users_this_month = User.query.filter(User.created_at >= month_start).count()
    users_prev_month = User.query.filter(
        User.created_at >= prev_month_start, User.created_at < month_start
    ).count()

    diretores = sum(1 for p in profiles if p.cargo == CARGO_DIRETOR)
    diretores_this = sum(
        1 for p in profiles if p.cargo == CARGO_DIRETOR and p.criado_em and p.criado_em >= month_start
    )
    diretores_prev = sum(
        1
        for p in profiles
        if p.cargo == CARGO_DIRETOR
        and p.criado_em
        and prev_month_start <= p.criado_em < month_start
    )

    pais = sum(1 for p in profiles if p.cargo == CARGO_PAI)
    pais_this = sum(
        1 for p in profiles if p.cargo == CARGO_PAI and p.criado_em and p.criado_em >= month_start
    )
    pais_prev = sum(
        1
        for p in profiles
        if p.cargo == CARGO_PAI and p.criado_em and prev_month_start <= p.criado_em < month_start
    )

    desbravadores = Member.query.count()
    desb_this = Member.query.filter(Member.joined_at.isnot(None)).count()  # fallback
    try:
        desb_this = (
            db.session.query(func.count(Member.id))
            .filter(Member.joined_at >= month_start.date())
            .scalar()
            or 0
        )
    except Exception:
        pass

    return {
        "clubes": clubs_total,
        "clubes_delta": clubs_this_month,
        "clubes_delta_label": f"+{clubs_this_month} este mês" if clubs_this_month else "estável",
        "users": users_total,
        "users_delta": users_this_month,
        "users_delta_label": f"+{users_this_month} este mês" if users_this_month else "estável",
        "diretores": diretores,
        "diretores_delta": diretores_this,
        "diretores_delta_label": f"+{diretores_this} este mês" if diretores_this else "estável",
        "pais": pais,
        "pais_delta": pais_this,
        "pais_delta_label": f"+{pais_this} este mês" if pais_this else "estável",
        "desbravadores": desbravadores,
        "desbravadores_delta": desb_this,
        "desbravadores_delta_label": f"+{desb_this} este mês" if desb_this else "estável",
        "_clubs_prev": clubs_prev_month,
        "_users_prev": users_prev_month,
        "_diretores_prev": diretores_prev,
        "_pais_prev": pais_prev,
    }


def club_growth_series(months: int = 6) -> dict:
    now = datetime.utcnow()
    labels = []
    values = []
    for i in range(months - 1, -1, -1):
        ref = _month_start(now)
        for _ in range(i):
            ref = (ref - timedelta(days=1)).replace(day=1)
        end = (ref + timedelta(days=32)).replace(day=1)
        count = Club.query.filter(Club.criado_em < end).count()
        labels.append(month_abbr[ref.month].capitalize())
        values.append(count)
    return {"labels": labels, "values": values}


def _club_has_director(club_id: str, director_club_ids: set[str]) -> bool:
    return club_id in director_club_ids


def _club_last_activity(club_id: str) -> datetime | None:
    last_event = (
        AgendaEvent.query.filter_by(clube_id=club_id)
        .order_by(AgendaEvent.event_date.desc())
        .first()
    )
    last_post = (
        BoardPost.query.filter_by(clube_id=club_id)
        .order_by(BoardPost.created_at.desc())
        .first()
    )
    candidates = []
    if last_event and last_event.event_date:
        candidates.append(datetime.combine(last_event.event_date, datetime.min.time()))
    if last_post and getattr(last_post, "created_at", None):
        candidates.append(last_post.created_at)
    return max(candidates) if candidates else None


def club_health_summary() -> dict:
    clubs = Club.query.all()
    director_ids = {
        p.clube_id
        for p in Profile.query.filter(Profile.cargo == CARGO_DIRETOR).all()
        if p.clube_id
    }
    now = datetime.utcnow()
    cutoff = now - timedelta(days=60)

    excellent = good = attention = critical = 0
    for club in clubs:
        has_dir = _club_has_director(club.id, director_ids)
        n_members = Member.query.filter_by(clube_id=club.id).count()
        last_act = _club_last_activity(club.id)
        inactive = last_act is None or last_act < cutoff

        if not has_dir and n_members == 0:
            critical += 1
        elif not has_dir or (inactive and n_members > 0):
            attention += 1
        elif inactive:
            good += 1
        else:
            excellent += 1

    total = len(clubs) or 1
    return {
        "total": len(clubs),
        "excellent": excellent,
        "good": good,
        "attention": attention,
        "critical": critical,
        "pct_excellent": round(excellent / total * 100),
        "pct_good": round(good / total * 100),
        "pct_attention": round(attention / total * 100),
        "pct_critical": round(critical / total * 100),
    }


def recent_activities(limit: int = 8) -> list[dict]:
    items: list[dict] = []

    for club in Club.query.order_by(Club.criado_em.desc()).limit(5).all():
        items.append(
            {
                "kind": "club",
                "icon": "club",
                "text": f"Novo clube criado: {club.nome}",
                "ago": _ago_label(club.criado_em),
                "ts": club.criado_em or datetime.utcnow(),
            }
        )

    logs = LeadershipAuditLog.query.order_by(LeadershipAuditLog.created_at.desc()).limit(limit).all()
    for row in logs:
        who = "Sistema"
        if row.performed_by:
            who = row.performed_by.full_name or row.performed_by.email or who
        items.append(
            {
                "kind": "audit",
                "icon": "audit",
                "text": row.summary,
                "ago": _ago_label(row.created_at),
                "ts": row.created_at,
                "who": who,
            }
        )

    for user in User.query.order_by(User.created_at.desc()).limit(3).all():
        items.append(
            {
                "kind": "user",
                "icon": "user",
                "text": f"Usuário criado: {user.full_name or user.email}",
                "ago": _ago_label(user.created_at),
                "ts": user.created_at or datetime.utcnow(),
            }
        )

    items.sort(key=lambda x: x["ts"], reverse=True)
    return items[:limit]


def system_alerts() -> list[dict]:
    alerts: list[dict] = []
    clubs = Club.query.all()
    director_club_ids = {
        p.clube_id
        for p in Profile.query.filter(Profile.cargo == CARGO_DIRETOR).all()
        if p.clube_id
    }
    now = datetime.utcnow()
    cutoff = now - timedelta(days=60)

    no_director = [c for c in clubs if c.id not in director_club_ids]
    if no_director:
        alerts.append(
            {
                "level": "warning",
                "title": f"{len(no_director)} clube(s) sem diretor",
                "detail": "Vincule um diretor para habilitar a gestão completa.",
            }
        )

    inactive = []
    critical = []
    for club in clubs:
        last = _club_last_activity(club.id)
        n_members = Member.query.filter_by(clube_id=club.id).count()
        if last is None or last < cutoff:
            inactive.append(club)
        if club.id not in director_club_ids and n_members == 0 and club.template_slug != "duque_de_caxias":
            critical.append(club)

    if critical:
        alerts.append(
            {
                "level": "danger",
                "title": f"{len(critical)} clube(s) precisam de atenção imediata",
                "detail": "Sem diretor e sem membros cadastrados.",
            }
        )

    if inactive:
        alerts.append(
            {
                "level": "info",
                "title": f"{len(inactive)} clube(s) sem atividade recente",
                "detail": "Nenhum evento ou publicação nos últimos 60 dias.",
            }
        )

    pending_email = User.query.filter(User.email_verified.is_(False)).count()
    if pending_email:
        alerts.append(
            {
                "level": "warning",
                "title": f"{pending_email} usuário(s) com e-mail pendente",
                "detail": "Contas aguardando verificação de e-mail.",
            }
        )

    alerts.append(
        {
            "level": "success",
            "title": "Sistema operacional",
            "detail": "Plataforma funcionando corretamente.",
        }
    )
    return alerts


def clubs_table_data() -> list[dict]:
    director_map: dict[str, tuple[User, Profile]] = {}
    rows = (
        db.session.query(User, Profile, Club)
        .join(Profile, Profile.id == User.id)
        .join(Club, Club.id == Profile.clube_id)
        .filter(Profile.cargo == CARGO_DIRETOR)
        .all()
    )
    for user, profile, club in rows:
        if club.id not in director_map:
            director_map[club.id] = (user, profile)

    result = []
    for club in Club.query.order_by(Club.nome.asc()).all():
        dir_pair = director_map.get(club.id)
        n_members = Member.query.filter_by(clube_id=club.id).count()
        n_users = Profile.query.filter_by(clube_id=club.id).count()
        last_act = _club_last_activity(club.id)
        has_dir = club.id in director_map

        if not has_dir:
            status, status_class = "Sem diretor", "warning"
        elif last_act and last_act >= datetime.utcnow() - timedelta(days=60):
            status, status_class = "Ativo", "success"
        elif n_members > 0:
            status, status_class = "Atenção", "warning"
        else:
            status, status_class = "Inativo", "muted"

        result.append(
            {
                "club": club,
                "director_user": dir_pair[0] if dir_pair else None,
                "director_profile": dir_pair[1] if dir_pair else None,
                "n_members": n_members,
                "n_users": n_users,
                "status": status,
                "status_class": status_class,
                "director_user_id": dir_pair[0].id if dir_pair else None,
            }
        )
    return result


def users_list(*, search: str = "", cargo_filter: str = "", clube_id: str = "") -> list[dict]:
    q = (
        db.session.query(User, Profile, Club)
        .outerjoin(Profile, Profile.id == User.id)
        .outerjoin(Club, Club.id == Profile.clube_id)
    )
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if cargo_filter:
        q = q.filter(Profile.cargo == cargo_filter)
    if clube_id:
        q = q.filter(Profile.clube_id == clube_id)
    q = q.order_by(User.full_name.asc(), User.email.asc())
    out = []
    for user, profile, club in q.all():
        verified = user.email_verified
        if profile and not profile.email_verificado:
            verified = False
        out.append(
            {
                "user": user,
                "profile": profile,
                "club": club,
                "cargo_label": _cargo_label(profile),
                "status": "Ativo" if verified else "Pendente",
                "status_class": "success" if verified else "warning",
            }
        )
    return out


def directors_list(*, clube_id: str = "", search: str = "") -> list[tuple]:
    q = (
        db.session.query(User, Profile, Club)
        .join(Profile, Profile.id == User.id)
        .outerjoin(Club, Club.id == Profile.clube_id)
        .filter(Profile.cargo == CARGO_DIRETOR)
    )
    if clube_id:
        q = q.filter(Profile.clube_id == clube_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.email.ilike(like), User.full_name.ilike(like)))
    return q.order_by(User.full_name.asc(), User.email.asc()).all()


def club_director_user_ids() -> dict[str, int]:
    out: dict[str, int] = {}
    for user, profile, club in directors_list():
        if club and club.id and club.id not in out:
            out[club.id] = user.id
    return out


def global_audit_logs(limit: int = 50) -> list[dict]:
    rows = LeadershipAuditLog.query.order_by(LeadershipAuditLog.created_at.desc()).limit(limit).all()
    out = []
    for row in rows:
        club_name = "—"
        if row.clube_id:
            club = db.session.get(Club, row.clube_id)
            club_name = club.nome if club else row.clube_id
        who = "Sistema"
        if row.performed_by:
            who = row.performed_by.full_name or row.performed_by.email or who
        out.append(
            {
                "id": row.id,
                "summary": row.summary,
                "action": row.action,
                "who": who,
                "club_name": club_name,
                "when": row.created_at.strftime("%d/%m/%Y %H:%M") if row.created_at else "—",
                "ago": _ago_label(row.created_at),
            }
        )
    return out


def template_stats() -> list[dict]:
    rows = (
        db.session.query(Club.template_slug, func.count(Club.id))
        .group_by(Club.template_slug)
        .order_by(func.count(Club.id).desc())
        .all()
    )
    return [{"slug": slug, "count": count} for slug, count in rows]


def communications_stats() -> dict:
    total = BoardPost.query.count()
    by_kind = (
        db.session.query(BoardPost.post_kind, func.count(BoardPost.id))
        .group_by(BoardPost.post_kind)
        .all()
    )
    recent = BoardPost.query.order_by(BoardPost.created_at.desc()).limit(10).all()
    return {
        "total": total,
        "by_kind": {k: c for k, c in by_kind},
        "recent": recent,
    }


def role_distribution() -> list[dict]:
    rows = (
        db.session.query(Profile.cargo, func.count(Profile.id))
        .group_by(Profile.cargo)
        .order_by(func.count(Profile.id).desc())
        .all()
    )
    return [{"cargo": c, "label": CARGO_LABELS.get(c, c), "count": n} for c, n in rows]


def platform_stats() -> dict:
    counts = global_counts()
    health = club_health_summary()
    return {
        **counts,
        "health": health,
        "n_posts": BoardPost.query.count(),
        "n_events": AgendaEvent.query.count(),
        "n_audit_logs": LeadershipAuditLog.query.count(),
        "templates": template_stats(),
        "roles": role_distribution(),
    }
