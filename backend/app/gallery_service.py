"""Galeria oficial do clube — álbuns, fotos, busca e auditoria."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from flask import url_for
from flask_login import current_user
from sqlalchemy import func, or_

from app.extensions import db
from app.models import (
    GALLERY_ACT_ALBUM,
    GALLERY_ACT_COVER,
    GALLERY_ACT_DELETE,
    GALLERY_ACT_FEATURED,
    GALLERY_ACT_MOVE,
    GALLERY_ACT_UPLOAD,
    GALLERY_CAT_ACAMPAMENTO,
    GALLERY_CAT_ACOES,
    GALLERY_CAT_CAMPORI,
    GALLERY_CAT_INVESTIDURA,
    GALLERY_CAT_REUNIOES,
    GALLERY_CATEGORY_LABELS,
    GALLERY_CATEGORIES,
    GALLERY_CAT_GERAL,
    GalleryActivityLog,
    GalleryAlbum,
    GalleryPhoto,
    User,
)
from app.template_filters import fmt_date
from app.uploads_util import safe_remove_upload, save_gallery_upload


def _upload_url(rel: str | None) -> str:
    if not rel:
        return ""
    return f"/uploads/{rel.lstrip('/')}"


def _ago(dt: datetime | None) -> str:
    if not dt:
        return ""
    delta = datetime.utcnow() - dt
    if delta.days == 0:
        if delta.seconds < 3600:
            m = max(1, delta.seconds // 60)
            return f"há {m} min"
        h = delta.seconds // 3600
        return f"há {h}h"
    if delta.days == 1:
        return "ontem"
    if delta.days < 7:
        return f"há {delta.days} dias"
    return fmt_date(dt.date() if hasattr(dt, "date") else dt)


def _user_label(uid: int | None) -> str:
    if not uid:
        return "Diretoria"
    u = db.session.get(User, uid)
    if not u:
        return "Diretoria"
    return (u.full_name or u.email or "Diretoria").split()[0]


def _parse_tags(raw: str | list | None) -> list[str]:
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()][:12]
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(t).strip() for t in data if str(t).strip()][:12]
    except (TypeError, ValueError):
        pass
    return [t.strip() for t in str(raw).split(",") if t.strip()][:12]


def log_gallery_activity(
    clube_id: str,
    action: str,
    message: str,
    *,
    album_id: int | None = None,
    photo_id: int | None = None,
    details: dict | None = None,
) -> None:
    uid = getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None
    row = GalleryActivityLog(
        clube_id=clube_id,
        action=action,
        album_id=album_id,
        photo_id=photo_id,
        user_id=uid,
        message=message,
        details_json=json.dumps(details or {}, ensure_ascii=False) if details else None,
    )
    db.session.add(row)


def _photo_count_subq():
    return (
        db.session.query(func.count(GalleryPhoto.id))
        .filter(
            GalleryPhoto.album_id == GalleryAlbum.id,
            GalleryPhoto.is_trashed.is_(False),
        )
        .correlate(GalleryAlbum)
        .scalar_subquery()
    )


def _album_cover_url(album: GalleryAlbum) -> str:
    if album.cover_photo_id:
        cp = db.session.get(GalleryPhoto, album.cover_photo_id)
        if cp and not cp.is_trashed and cp.filename:
            return _upload_url(cp.filename)
    latest = (
        GalleryPhoto.query.filter_by(album_id=album.id, is_trashed=False)
        .order_by(GalleryPhoto.created_at.desc())
        .first()
    )
    if latest:
        return _upload_url(latest.filename)
    return url_for("static", filename="img/login-nature.jpg")


def serialize_photo(photo: GalleryPhoto, album: GalleryAlbum | None = None) -> dict:
    alb = album or photo.album
    tags = _parse_tags(photo.tags_json)
    return {
        "id": photo.id,
        "album_id": photo.album_id,
        "album_title": alb.title if alb else "",
        "src": _upload_url(photo.filename),
        "thumb": _upload_url(photo.thumb_filename or photo.filename),
        "title": photo.title or "",
        "description": photo.description or "",
        "tags": tags,
        "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
        "taken_label": fmt_date(photo.taken_at) if photo.taken_at else fmt_date(photo.created_at.date()),
        "created_at": photo.created_at.isoformat() if photo.created_at else None,
        "updated_ago": _ago(photo.updated_at or photo.created_at),
        "width": photo.width,
        "height": photo.height,
        "aspect": "tall" if photo.height and photo.width and photo.height > photo.width * 1.15 else (
            "wide" if photo.width and photo.height and photo.width > photo.height * 1.2 else "square"
        ),
    }


def serialize_album(album: GalleryAlbum, *, photo_count: int | None = None) -> dict:
    if photo_count is None:
        photo_count = (
            GalleryPhoto.query.filter_by(album_id=album.id, is_trashed=False).count()
        )
    return {
        "id": album.id,
        "title": album.title,
        "description": album.description or "",
        "category": album.category,
        "category_label": GALLERY_CATEGORY_LABELS.get(album.category, album.category),
        "event_date": album.event_date.isoformat() if album.event_date else None,
        "event_label": fmt_date(album.event_date) if album.event_date else "",
        "cover_url": _album_cover_url(album),
        "photo_count": photo_count,
        "featured": bool(album.featured),
        "updated_ago": _ago(album.updated_at),
        "responsible": _user_label(album.created_by_id),
    }


def _featured_slides(clube_id: str) -> list[dict]:
    albums = (
        GalleryAlbum.query.filter_by(clube_id=clube_id, is_trashed=False)
        .filter(
            or_(
                GalleryAlbum.featured.is_(True),
                GalleryAlbum.category == "campori",
            )
        )
        .order_by(GalleryAlbum.updated_at.desc())
        .limit(8)
        .all()
    )
    if not albums:
        albums = (
            GalleryAlbum.query.filter_by(clube_id=clube_id, is_trashed=False)
            .order_by(GalleryAlbum.updated_at.desc())
            .limit(5)
            .all()
        )
    slides = []
    for a in albums:
        cnt = GalleryPhoto.query.filter_by(album_id=a.id, is_trashed=False).count()
        slides.append(
            {
                **serialize_album(a, photo_count=cnt),
                "badge": "⭐ DESTAQUE DO MOMENTO" if a.featured else "Álbum em destaque",
                "subtitle": (a.description or "Momentos que ficarão para sempre!")[:140],
            }
        )
    return slides


def recent_activity(clube_id: str, limit: int = 8) -> list[dict]:
    rows = (
        GalleryActivityLog.query.filter_by(clube_id=clube_id)
        .order_by(GalleryActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    icons = {
        GALLERY_ACT_UPLOAD: ("green", "📷"),
        GALLERY_ACT_COVER: ("violet", "🖼"),
        GALLERY_ACT_DELETE: ("orange", "🗑"),
        GALLERY_ACT_ALBUM: ("blue", "📁"),
        GALLERY_ACT_MOVE: ("blue", "↔"),
        GALLERY_ACT_FEATURED: ("gold", "⭐"),
    }
    out = []
    for r in rows:
        color, icon = icons.get(r.action, ("slate", "•"))
        out.append(
            {
                "message": r.message,
                "ago": _ago(r.created_at),
                "color": color,
                "icon": icon,
            }
        )
    return out


def search_albums_and_photos(
    clube_id: str,
    q: str = "",
    category: str = "",
    *,
    photo_limit: int = 48,
    album_limit: int = 12,
) -> tuple[list[GalleryAlbum], list[GalleryPhoto]]:
    aq = GalleryAlbum.query.filter_by(clube_id=clube_id, is_trashed=False)
    pq = (
        GalleryPhoto.query.filter_by(clube_id=clube_id, is_trashed=False)
        .join(GalleryAlbum, GalleryPhoto.album_id == GalleryAlbum.id)
        .filter(GalleryAlbum.is_trashed.is_(False))
    )

    if category and category in GALLERY_CATEGORIES:
        aq = aq.filter(GalleryAlbum.category == category)
        pq = pq.filter(GalleryAlbum.category == category)

    term = (q or "").strip().lower()
    if term:
        like = f"%{term}%"
        aq = aq.filter(
            or_(
                func.lower(GalleryAlbum.title).like(like),
                func.lower(GalleryAlbum.description).like(like),
            )
        )
        pq = pq.filter(
            or_(
                func.lower(GalleryPhoto.title).like(like),
                func.lower(GalleryPhoto.description).like(like),
                func.lower(GalleryPhoto.tags_json).like(like),
                func.lower(GalleryAlbum.title).like(like),
            )
        )

    albums = aq.order_by(GalleryAlbum.updated_at.desc()).limit(album_limit).all()
    photos = pq.order_by(GalleryPhoto.created_at.desc()).limit(photo_limit).all()
    return albums, photos


def build_gallery_page(clube_id: str, q: str = "", category: str = "") -> dict:
    albums, photos = search_albums_and_photos(clube_id, q, category)
    main_albums = (
        GalleryAlbum.query.filter_by(clube_id=clube_id, is_trashed=False)
        .order_by(GalleryAlbum.updated_at.desc())
        .limit(12)
        .all()
    )
    if not main_albums:
        main_albums = albums

    return {
        "filter_chips": [("", "Todas")] + [(c, GALLERY_CATEGORY_LABELS[c]) for c in GALLERY_CATEGORIES if c != GALLERY_CAT_GERAL],
        "active_filter": category,
        "search_q": q,
        "hero_slides": _featured_slides(clube_id),
        "albums": [serialize_album(a) for a in main_albums],
        "photos": [serialize_photo(p) for p in photos],
        "recent_activity": recent_activity(clube_id),
        "album_options": [
            {"id": a.id, "title": a.title}
            for a in GalleryAlbum.query.filter_by(clube_id=clube_id, is_trashed=False)
            .order_by(GalleryAlbum.title)
            .all()
        ],
    }


def get_album_for_club(album_id: int, clube_id: str) -> GalleryAlbum | None:
    return GalleryAlbum.query.filter_by(id=album_id, clube_id=clube_id, is_trashed=False).first()


def get_photo_for_club(photo_id: int, clube_id: str) -> GalleryPhoto | None:
    return GalleryPhoto.query.filter_by(id=photo_id, clube_id=clube_id, is_trashed=False).first()


def create_album(
    clube_id: str,
    *,
    title: str,
    description: str = "",
    category: str = GALLERY_CAT_GERAL,
    event_date: date | None = None,
    featured: bool = False,
) -> GalleryAlbum:
    title = (title or "").strip() or "Novo álbum"
    cat = category if category in GALLERY_CATEGORIES else GALLERY_CAT_GERAL
    uid = getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None
    album = GalleryAlbum(
        clube_id=clube_id,
        title=title,
        description=(description or "").strip() or None,
        category=cat,
        event_date=event_date,
        featured=featured,
        created_by_id=uid,
    )
    db.session.add(album)
    db.session.flush()
    log_gallery_activity(
        clube_id,
        GALLERY_ACT_ALBUM,
        f"Você criou o álbum {title}",
        album_id=album.id,
    )
    return album


def update_album(album: GalleryAlbum, data: dict) -> GalleryAlbum:
    if "title" in data and data["title"]:
        album.title = str(data["title"]).strip()[:160]
    if "description" in data:
        album.description = (data.get("description") or "").strip() or None
    if "category" in data and data["category"] in GALLERY_CATEGORIES:
        album.category = data["category"]
    if "event_date" in data:
        raw = data.get("event_date")
        if raw:
            try:
                album.event_date = date.fromisoformat(str(raw)[:10])
            except ValueError:
                pass
        else:
            album.event_date = None
    if "featured" in data:
        album.featured = bool(data["featured"])
    album.updated_at = datetime.utcnow()
    return album


def trash_album(album: GalleryAlbum, upload_folder: str) -> None:
    album.is_trashed = True
    album.updated_at = datetime.utcnow()
    photos = GalleryPhoto.query.filter_by(album_id=album.id, is_trashed=False).all()
    for p in photos:
        p.is_trashed = True
        p.updated_at = datetime.utcnow()
    log_gallery_activity(
        album.clube_id,
        GALLERY_ACT_DELETE,
        f"Você moveu o álbum {album.title} para a lixeira",
        album_id=album.id,
        details={"count": len(photos)},
    )


def upload_photos(
    clube_id: str,
    album_id: int,
    files: list,
    upload_folder: str,
) -> list[GalleryPhoto]:
    album = get_album_for_club(album_id, clube_id)
    if not album:
        raise ValueError("Álbum não encontrado.")
    created = []
    for f in files:
        meta = save_gallery_upload(f, upload_folder)
        if not meta:
            continue
        photo = GalleryPhoto(
            clube_id=clube_id,
            album_id=album.id,
            filename=meta["filename"],
            thumb_filename=meta.get("thumb_filename"),
            width=meta.get("width"),
            height=meta.get("height"),
            uploaded_by_id=getattr(current_user, "id", None),
        )
        db.session.add(photo)
        created.append(photo)
    if created:
        album.updated_at = datetime.utcnow()
        if not album.cover_photo_id:
            album.cover_photo_id = created[0].id
        db.session.flush()
        log_gallery_activity(
            clube_id,
            GALLERY_ACT_UPLOAD,
            f"Você adicionou {len(created)} fotos no álbum {album.title}",
            album_id=album.id,
            details={"count": len(created)},
        )
    return created


def update_photo(photo: GalleryPhoto, data: dict) -> GalleryPhoto:
    if "title" in data:
        photo.title = (data.get("title") or "").strip()[:200] or None
    if "description" in data:
        photo.description = (data.get("description") or "").strip() or None
    if "tags" in data:
        tags = _parse_tags(data.get("tags"))
        photo.tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
    if "taken_at" in data:
        raw = data.get("taken_at")
        if raw:
            try:
                photo.taken_at = date.fromisoformat(str(raw)[:10])
            except ValueError:
                pass
        else:
            photo.taken_at = None
    photo.updated_at = datetime.utcnow()
    if photo.album:
        photo.album.updated_at = datetime.utcnow()
    return photo


def move_photo_to_album(photo: GalleryPhoto, target_album_id: int, clube_id: str) -> GalleryPhoto:
    target = get_album_for_club(target_album_id, clube_id)
    if not target:
        raise ValueError("Álbum de destino inválido.")
    old_title = photo.album.title if photo.album else ""
    photo.album_id = target.id
    photo.updated_at = datetime.utcnow()
    target.updated_at = datetime.utcnow()
    if photo.album_id == target.id and target.cover_photo_id == photo.id:
        pass
    log_gallery_activity(
        clube_id,
        GALLERY_ACT_MOVE,
        f"Você moveu uma foto de {old_title} para {target.title}",
        album_id=target.id,
        photo_id=photo.id,
    )
    return photo


def set_album_cover(album: GalleryAlbum, photo_id: int) -> None:
    photo = get_photo_for_club(photo_id, album.clube_id)
    if not photo or photo.album_id != album.id:
        raise ValueError("Foto inválida para este álbum.")
    album.cover_photo_id = photo.id
    album.updated_at = datetime.utcnow()
    log_gallery_activity(
        album.clube_id,
        GALLERY_ACT_COVER,
        f"Você definiu uma nova capa para {album.title}",
        album_id=album.id,
        photo_id=photo.id,
    )


def set_featured_album(album: GalleryAlbum) -> None:
    GalleryAlbum.query.filter_by(clube_id=album.clube_id, featured=True).update({"featured": False})
    album.featured = True
    album.updated_at = datetime.utcnow()
    log_gallery_activity(
        album.clube_id,
        GALLERY_ACT_FEATURED,
        f"Você definiu {album.title} como destaque da galeria",
        album_id=album.id,
    )


def trash_photo(photo: GalleryPhoto, upload_folder: str, *, permanent: bool = False) -> None:
    album = photo.album
    clube_id = photo.clube_id
    title = album.title if album else "galeria"
    if permanent:
        safe_remove_upload(upload_folder, photo.filename)
        safe_remove_upload(upload_folder, photo.thumb_filename)
        if album and album.cover_photo_id == photo.id:
            album.cover_photo_id = None
        db.session.delete(photo)
    else:
        photo.is_trashed = True
        photo.updated_at = datetime.utcnow()
        if album and album.cover_photo_id == photo.id:
            nxt = (
                GalleryPhoto.query.filter_by(album_id=album.id, is_trashed=False)
                .filter(GalleryPhoto.id != photo.id)
                .order_by(GalleryPhoto.created_at.desc())
                .first()
            )
            album.cover_photo_id = nxt.id if nxt else None
    if album:
        album.updated_at = datetime.utcnow()
    log_gallery_activity(
        clube_id,
        GALLERY_ACT_DELETE,
        f"Você excluiu 1 foto do álbum {title}",
        album_id=album.id if album else None,
        photo_id=photo.id,
    )


def album_photos_for_lightbox(album_id: int, clube_id: str) -> list[dict]:
    photos = (
        GalleryPhoto.query.filter_by(album_id=album_id, clube_id=clube_id, is_trashed=False)
        .order_by(GalleryPhoto.sort_order, GalleryPhoto.created_at)
        .all()
    )
    album = get_album_for_club(album_id, clube_id)
    return [serialize_photo(p, album) for p in photos]


def trashed_items(clube_id: str) -> dict:
    albums = GalleryAlbum.query.filter_by(clube_id=clube_id, is_trashed=True).order_by(
        GalleryAlbum.updated_at.desc()
    ).all()
    photos = (
        GalleryPhoto.query.filter_by(clube_id=clube_id, is_trashed=True)
        .order_by(GalleryPhoto.updated_at.desc())
        .limit(60)
        .all()
    )
    return {
        "albums": [serialize_album(a) for a in albums],
        "photos": [serialize_photo(p) for p in photos],
    }


def ensure_demo_gallery(clube_id: str, upload_folder: str, *, static_img: str | None = None) -> None:
    """Cria álbuns de exemplo na primeira visita (sem duplicar)."""
    if GalleryAlbum.query.filter_by(clube_id=clube_id).count():
        return
    from pathlib import Path
    import shutil
    import uuid

    src = Path(static_img) if static_img else None
    if not src or not src.is_file():
        return
    dest_dir = Path(upload_folder) / "gallery"
    dest_dir.mkdir(parents=True, exist_ok=True)
    samples = [
        ("Campori APlaC 2026", GALLERY_CAT_CAMPORI, "Um dos maiores eventos do nosso clube.", True),
        ("Acampamento de Inverno", GALLERY_CAT_ACAMPAMENTO, "Noites frias e fogueiras acolhedoras.", False),
        ("Investidura 2025", GALLERY_CAT_INVESTIDURA, "Cerimônia especial de investidura.", False),
        ("Ação Solidária", GALLERY_CAT_ACOES, "Servindo nossa comunidade.", False),
        ("Reuniões Especiais", GALLERY_CAT_REUNIOES, "Momentos do clube em reunião.", False),
    ]
    for title, cat, desc, feat in samples:
        album = create_album(clube_id, title=title, description=desc, category=cat, featured=feat)
        name = f"{uuid.uuid4().hex}.jpg"
        path = dest_dir / name
        shutil.copy(src, path)
        photo = GalleryPhoto(
            clube_id=clube_id,
            album_id=album.id,
            filename=f"gallery/{name}",
            thumb_filename=f"gallery/{name}",
            title=title,
            uploaded_by_id=None,
        )
        db.session.add(photo)
        db.session.flush()
        album.cover_photo_id = photo.id
    db.session.commit()
