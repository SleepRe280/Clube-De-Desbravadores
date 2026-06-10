"""Comunicados da diretoria — consultas, serialização e widgets."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from flask import url_for
from sqlalchemy import false, func

from app.extensions import db
from app.models import (
    POST_CATEGORY_AVISO,
    POST_CATEGORY_LABELS,
    POST_CATEGORY_CSS,
    POST_CATEGORIES,
    POST_KIND_COMUNICADO,
    POST_KIND_NOTICIA,
    AgendaEvent,
    BoardPost,
    BoardPostRead,
)
from app.uploads_util import attachment_display_name, attachment_ext

DEFAULT_HERO_IMAGE = "img/login-nature.jpg"

AUDIENCE_OPTIONS = (
    ("clube", "Clube inteiro"),
    ("pais", "Pais"),
    ("responsaveis", "Responsáveis"),
    ("diretoria", "Diretoria"),
)

FILTER_CHIPS = (
    ("todos", "Todos"),
    (POST_CATEGORY_AVISO, "Avisos"),
    ("evento", "Eventos"),
    ("reuniao", "Reuniões"),
    ("espiritual", "Espiritual"),
    ("financeiro", "Financeiro"),
    ("mais", "Mais categorias"),
)


def _chip_to_category(chip: str) -> str | None:
    if chip in ("todos", "mais", ""):
        return None
    if chip in POST_CATEGORIES:
        return chip
    return None


def posts_query_comunicados(clube_ids: set[str] | None = None, clube_id: str | None = None):
    q = BoardPost.query.filter(BoardPost.post_kind == POST_KIND_COMUNICADO)
    if clube_id:
        q = q.filter(BoardPost.clube_id == clube_id)
    elif clube_ids:
        q = q.filter(BoardPost.clube_id.in_(clube_ids))
    else:
        q = q.filter(false())
    return q


def apply_category_filter(q, chip: str):
    cat = _chip_to_category(chip)
    if cat:
        q = q.filter(BoardPost.category == cat)
    elif chip == "mais":
        q = q.filter(
            BoardPost.category.in_(
                [c for c in POST_CATEGORIES if c not in (POST_CATEGORY_AVISO,)]
            )
        )
    return q


def featured_post(posts: list[BoardPost]) -> BoardPost | None:
    for p in posts:
        if p.is_featured or p.is_urgent:
            return p
    return posts[0] if posts else None


def excerpt(text: str, max_len: int = 160) -> str:
    s = (text or "").strip().replace("\r\n", "\n")
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def format_event_date(d: date | None, t: str | None = None) -> str:
    if not d:
        return ""
    months = (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )
    label = f"{d.day} de {months[d.month - 1]}"
    if d.year != date.today().year:
        label += f" de {d.year}"
    if t:
        label += f" · {t[:5]}"
    return label


def relative_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    now = datetime.utcnow()
    diff = now - dt
    if diff.days == 0:
        if diff.seconds < 3600:
            mins = max(1, diff.seconds // 60)
            return f"Há {mins} min"
        h = diff.seconds // 3600
        return f"Hoje, {dt.strftime('%H:%M')}" if h < 6 else f"Hoje, {dt.strftime('%H:%M')}"
    if diff.days == 1:
        return f"Ontem, {dt.strftime('%H:%M')}"
    if diff.days < 7:
        return f"{diff.days} dias atrás"
    return dt.strftime("%d/%m/%Y")


def image_url(image_filename: str | None) -> str:
    if image_filename:
        return url_for("uploaded_file", rel_path=image_filename)
    return url_for("static", filename=DEFAULT_HERO_IMAGE)


def parse_audience_from_form(form) -> list[str]:
    raw = form.getlist("audience")
    allowed = {a[0] for a in AUDIENCE_OPTIONS}
    units = []
    audience = []
    for v in raw:
        s = (v or "").strip()
        if not s:
            continue
        if s.startswith("unidade:"):
            units.append(s)
        elif s in allowed:
            audience.append(s)
    audience.extend(units)
    return audience or ["clube"]


def apply_comunicado_form(post: BoardPost, form, files, *, remove_image: bool = False, remove_attachment: bool = False) -> None:
    from app.models import POST_CATEGORY_AVISO

    post.title = (form.get("title") or "").strip()
    post.body = (form.get("body") or "").strip()
    post.post_kind = POST_KIND_COMUNICADO
    cat = (form.get("category") or POST_CATEGORY_AVISO).strip()
    post.category = cat if cat in POST_CATEGORIES else POST_CATEGORY_AVISO
    post.level = None

    ed = (form.get("event_date") or "").strip()
    post.event_date = date.fromisoformat(ed) if ed else None
    post.event_time = (form.get("event_time") or "").strip() or None
    post.location = (form.get("location") or "").strip() or None
    post.is_featured = form.get("is_featured") == "1"
    post.is_urgent = form.get("is_urgent") == "1"
    post.audience_json = json.dumps(parse_audience_from_form(form))

    from flask import current_app
    from app.uploads_util import safe_remove_upload, save_document_upload, save_upload

    upload_root = current_app.config["UPLOAD_FOLDER"]

    if remove_image:
        safe_remove_upload(upload_root, post.image_filename)
        post.image_filename = None
    img = files.get("image") or files.get("banner")
    if img and getattr(img, "filename", None):
        saved = save_upload(img, upload_root, "comms")
        if saved:
            safe_remove_upload(upload_root, post.image_filename)
            post.image_filename = saved

    if remove_attachment:
        safe_remove_upload(upload_root, post.attachment_filename)
        post.attachment_filename = None
    att = files.get("attachment")
    if att and getattr(att, "filename", None):
        saved = save_document_upload(att, upload_root, "comms")
        if saved:
            safe_remove_upload(upload_root, post.attachment_filename)
            post.attachment_filename = saved


def serialize_post(
    post: BoardPost,
    *,
    user_id: int | None = None,
    read_counts: dict[int, int] | None = None,
) -> dict[str, Any]:
    cat = post.category or POST_CATEGORY_AVISO
    read_n = (read_counts or {}).get(post.id, post.read_count())
    return {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "excerpt": excerpt(post.body),
        "category": cat,
        "category_label": POST_CATEGORY_LABELS.get(cat, "Comunicado"),
        "category_css": POST_CATEGORY_CSS.get(cat, "cm-tag--aviso"),
        "image_url": image_url(post.image_filename),
        "has_attachment": bool(post.attachment_filename),
        "attachment_url": (
            url_for("uploaded_file", rel_path=post.attachment_filename)
            if post.attachment_filename
            else None
        ),
        "attachment_name": attachment_display_name(post.attachment_filename),
        "attachment_ext": attachment_ext(post.attachment_filename),
        "event_date": post.event_date.isoformat() if post.event_date else None,
        "event_date_label": format_event_date(post.event_date, post.event_time),
        "event_time": post.event_time,
        "location": post.location or "",
        "is_featured": bool(post.is_featured),
        "is_urgent": bool(post.is_urgent),
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "relative_time": relative_time(post.created_at),
        "read_count": read_n,
        "is_read": post.is_read_by(user_id) if user_id else False,
        "audience": post.audience_list(),
    }


def batch_read_counts(post_ids: list[int]) -> dict[int, int]:
    if not post_ids:
        return {}
    rows = (
        db.session.query(BoardPostRead.post_id, func.count(BoardPostRead.id))
        .filter(BoardPostRead.post_id.in_(post_ids))
        .group_by(BoardPostRead.post_id)
        .all()
    )
    return {pid: cnt for pid, cnt in rows}


def mark_post_read(post_id: int, user_id: int) -> bool:
    post = db.session.get(BoardPost, post_id)
    if not post:
        return False
    existing = BoardPostRead.query.filter_by(post_id=post_id, user_id=user_id).first()
    if existing:
        return True
    db.session.add(BoardPostRead(post_id=post_id, user_id=user_id))
    db.session.commit()
    return True


def sidebar_upcoming_events(clube_ids: set[str], limit: int = 4) -> list[dict]:
    if not clube_ids:
        return []
    today = date.today()
    rows = (
        AgendaEvent.query.filter(
            AgendaEvent.clube_id.in_(clube_ids),
            AgendaEvent.event_date >= today,
        )
        .order_by(AgendaEvent.event_date.asc(), AgendaEvent.id.asc())
        .limit(limit)
        .all()
    )
    out = []
    for ev in rows:
        out.append(
            {
                "id": ev.id,
                "title": ev.title,
                "date": ev.event_date,
                "day": ev.event_date.day,
                "month": ev.event_date.strftime("%b").upper()[:3],
                "time": (ev.event_time or "")[:5],
                "location": ev.location or "",
            }
        )
    return out


def sidebar_urgent_posts(posts: list[BoardPost], limit: int = 2) -> list[dict]:
    urgent = [p for p in posts if p.is_urgent]
    if not urgent:
        urgent = [p for p in posts if p.category == POST_CATEGORY_AVISO][:limit]
    return [serialize_post(p) for p in urgent[:limit]]


def sidebar_recent_documents(posts: list[BoardPost], limit: int = 4) -> list[dict]:
    docs = []
    for p in posts:
        if not p.attachment_filename:
            continue
        docs.append(
            {
                "title": p.title,
                "name": attachment_display_name(p.attachment_filename),
                "ext": attachment_ext(p.attachment_filename),
                "url": url_for("uploaded_file", rel_path=p.attachment_filename),
            }
        )
        if len(docs) >= limit:
            break
    return docs


def sidebar_reminders(clube_ids: set[str]) -> list[dict]:
    """Lembretes leves derivados de eventos e comunicados urgentes."""
    if not clube_ids:
        return []
    today = date.today()
    soon = today + timedelta(days=7)
    events = (
        AgendaEvent.query.filter(
            AgendaEvent.clube_id.in_(clube_ids),
            AgendaEvent.event_date >= today,
            AgendaEvent.event_date <= soon,
        )
        .order_by(AgendaEvent.event_date.asc())
        .limit(2)
        .all()
    )
    items = []
    for ev in events:
        days = (ev.event_date - today).days
        when = "hoje" if days == 0 else f"em {days} dia(s)"
        items.append(
            {
                "icon": "📅",
                "text": f"{ev.title} — {when}",
            }
        )
    return items[:3]


def build_communications_page(
    *,
    clube_ids: set[str] | None,
    clube_id: str | None,
    active_filter: str,
    user_id: int | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    chip = active_filter if active_filter else "todos"
    q = posts_query_comunicados(clube_ids=clube_ids, clube_id=clube_id)
    q = apply_category_filter(q, chip)
    rows = q.order_by(BoardPost.created_at.desc()).limit(limit).all()
    counts = batch_read_counts([p.id for p in rows])
    items = [serialize_post(p, user_id=user_id, read_counts=counts) for p in rows]
    hero_src = featured_post(rows)
    hero = serialize_post(hero_src, user_id=user_id, read_counts=counts) if hero_src else None
    carousel_src = [p for p in rows if p.is_featured or p.is_urgent][:3]
    if not carousel_src and rows:
        carousel_src = rows[:3]
    hero_carousel = [
        serialize_post(p, user_id=user_id, read_counts=counts) for p in carousel_src
    ]
    club_set = clube_ids or ({clube_id} if clube_id else set())
    return {
        "posts_raw": rows,
        "items": items,
        "hero": hero,
        "hero_carousel": hero_carousel,
        "active_filter": chip,
        "filter_chips": FILTER_CHIPS,
        "sidebar_events": sidebar_upcoming_events(club_set),
        "sidebar_urgent": sidebar_urgent_posts(rows),
        "sidebar_documents": sidebar_recent_documents(rows),
        "sidebar_reminders": sidebar_reminders(club_set),
        "audience_options": AUDIENCE_OPTIONS,
        "post_categories": POST_CATEGORIES,
        "category_labels": POST_CATEGORY_LABELS,
    }
