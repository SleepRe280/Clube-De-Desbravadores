"""Agenda premium — categorias, status, serialização e RSVPs."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from app.member_wizard import CLUB_UNIT_OPTIONS

EVENT_CATEGORIES: dict[str, dict[str, str]] = {
    "reuniao": {"label": "Reunião", "color": "#f9bc15", "icon": "🔥"},
    "acampamento": {"label": "Acampamento", "color": "#ef4444", "icon": "⛺"},
    "classe_biblica": {"label": "Classe Bíblica", "color": "#3b82f6", "icon": "📖"},
    "campori": {"label": "Campori", "color": "#a855f7", "icon": "🏕️"},
    "especialidade": {"label": "Especialidade", "color": "#22c55e", "icon": "🎖️"},
    "diretoria": {"label": "Diretoria", "color": "#1e3a5f", "icon": "📋"},
    "passeio": {"label": "Passeio", "color": "#14b8a6", "icon": "🚌"},
    "investidura": {"label": "Investidura", "color": "#f97316", "icon": "🎓"},
}

EVENT_TYPE_CARDS: list[dict[str, str]] = [
    {"id": "acampamento", "label": "Acampamento", "icon": "⛺"},
    {"id": "classe_biblica", "label": "Classe Bíblica", "icon": "📖"},
    {"id": "investidura", "label": "Investidura", "icon": "🎓"},
    {"id": "campori", "label": "Campori", "icon": "🏕️"},
    {"id": "reuniao", "label": "Reunião", "icon": "🔥"},
    {"id": "passeio", "label": "Passeio", "icon": "🚌"},
    {"id": "especialidade", "label": "Especialidade", "icon": "🎖️"},
]

EVENT_COLOR_PALETTE: list[dict[str, str]] = [
    {"id": "red", "hex": "#ef4444", "label": "Vermelho"},
    {"id": "blue", "hex": "#3b82f6", "label": "Azul"},
    {"id": "green", "hex": "#22c55e", "label": "Verde"},
    {"id": "yellow", "hex": "#f9bc15", "label": "Amarelo"},
    {"id": "purple", "hex": "#a855f7", "label": "Roxo"},
    {"id": "orange", "hex": "#f97316", "label": "Laranja"},
]

EVENT_TEMPLATES: dict[str, dict] = {
    "acampamento_regional": {
        "label": "Acampamento Regional",
        "category": "acampamento",
        "title": "Acampamento Regional",
        "body": "Acampamento com programação completa, devocionais e atividades de unidade.",
        "duration_days": 2,
        "start_time": "08:00",
        "end_time": "18:00",
        "status": "planejado",
        "checklist": [
            "Reservar local",
            "Confirmar cozinha",
            "Separar transporte",
            "Autorizações dos pais",
            "Equipe médica",
            "Lista de presença",
        ],
    },
    "classe_biblica": {
        "label": "Classe Bíblica",
        "category": "classe_biblica",
        "title": "Classe Bíblica",
        "body": "Estudo bíblico com os desbravadores.",
        "duration_days": 0,
        "start_time": "19:00",
        "end_time": "21:00",
        "status": "planejado",
        "checklist": ["Preparar lição", "Materiais impressos", "Sala reservada"],
    },
    "campori": {
        "label": "Campori",
        "category": "campori",
        "title": "Campori",
        "body": "Encontro regional de clubes com competições e culto.",
        "duration_days": 3,
        "start_time": "07:00",
        "end_time": "22:00",
        "status": "em_breve",
        "checklist": [
            "Inscrição no campo",
            "Transporte do clube",
            "Uniformes e bandeiras",
            "Alimentação",
        ],
    },
    "investidura": {
        "label": "Investidura",
        "category": "investidura",
        "title": "Cerimônia de Investidura",
        "body": "Cerimônia oficial de classes e especialidades.",
        "duration_days": 0,
        "start_time": "19:30",
        "end_time": "21:30",
        "status": "confirmado",
        "checklist": [
            "Lista de investidos",
            "Insígnias e lenços",
            "Roteiro da cerimônia",
            "Ensaio prévio",
        ],
    },
}

EVENT_CHECKLISTS: dict[str, list[str]] = {
    "acampamento": EVENT_TEMPLATES["acampamento_regional"]["checklist"],
    "classe_biblica": EVENT_TEMPLATES["classe_biblica"]["checklist"],
    "campori": EVENT_TEMPLATES["campori"]["checklist"],
    "investidura": EVENT_TEMPLATES["investidura"]["checklist"],
    "reuniao": ["Confirmar programa", "Lista de presença", "Materiais da unidade"],
    "passeio": ["Autorização", "Transporte", "Seguro / primeiros socorros"],
    "especialidade": ["Materiais da especialidade", "Instrutor confirmado"],
}

EVENT_STATUSES: dict[str, dict[str, str]] = {
    "confirmado": {"label": "Confirmado", "variant": "success"},
    "em_breve": {"label": "Em breve", "variant": "warning"},
    "planejado": {"label": "Planejado", "variant": "info"},
    "rascunho": {"label": "Rascunho", "variant": "muted"},
    "cancelado": {"label": "Cancelado", "variant": "muted"},
    "finalizado": {"label": "Finalizado", "variant": "muted"},
    "lotado": {"label": "Lotado", "variant": "danger"},
}

CATEGORY_IDS = tuple(EVENT_CATEGORIES.keys())
STATUS_IDS = tuple(EVENT_STATUSES.keys())


def _time_display(t: str | None) -> str:
    if not t:
        return ""
    return t[:5] if len(t) >= 5 else t


def event_category_meta(cat: str | None, color_hex: str | None = None) -> dict[str, str]:
    meta = dict(EVENT_CATEGORIES.get((cat or "reuniao").strip(), EVENT_CATEGORIES["reuniao"]))
    if color_hex and color_hex.startswith("#"):
        meta["color"] = color_hex
    return meta


def parse_event_meta(ev) -> dict[str, Any]:
    raw = getattr(ev, "meta_json", None) or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def event_display_color(ev) -> str:
    if getattr(ev, "color_hex", None):
        return ev.color_hex
    return event_category_meta(ev.category).get("color", "#f9bc15")


def event_status_meta(st: str | None) -> dict[str, str]:
    return EVENT_STATUSES.get((st or "planejado").strip(), EVENT_STATUSES["planejado"])


def serialize_event(
    ev,
    *,
    rsvp_count: int | None = None,
    user_rsvp: dict | None = None,
    banner_url: str | None = None,
) -> dict[str, Any]:
    cat = event_category_meta(ev.category, getattr(ev, "color_hex", None))
    st = event_status_meta(ev.status)
    confirmed = rsvp_count if rsvp_count is not None else ev.confirmed_rsvp_count()
    cap = ev.max_capacity
    spots_left = None if not cap else max(0, cap - confirmed)
    meta = parse_event_meta(ev)
    end_d = getattr(ev, "event_end_date", None)
    return {
        "id": ev.id,
        "title": ev.title,
        "body": ev.body or "",
        "date": ev.event_date.isoformat(),
        "end_date": end_d.isoformat() if end_d else "",
        "time": _time_display(ev.event_time),
        "end_time": _time_display(getattr(ev, "event_end_time", None)),
        "category": ev.category or "reuniao",
        "category_label": cat["label"],
        "category_color": cat["color"],
        "category_icon": cat["icon"],
        "color_hex": getattr(ev, "color_hex", None) or cat["color"],
        "meta": meta,
        "location": ev.location or "",
        "unit": ev.unit or "",
        "status": ev.status or "planejado",
        "status_label": st["label"],
        "status_variant": st["variant"],
        "banner_url": banner_url,
        "max_capacity": cap,
        "confirmed_count": confirmed,
        "spots_left": spots_left,
        "responsible_name": ev.responsible_name or "",
        "user_rsvp": user_rsvp,
    }


def month_stats(events: list, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    total = len(events)
    confirmed = sum(1 for e in events if (e.status or "") == "confirmado")
    upcoming = sum(1 for e in events if e.event_date >= today)
    participants = 0
    for e in events:
        participants += e.confirmed_rsvp_count()
    return {
        "total": total,
        "confirmed": confirmed,
        "upcoming": upcoming,
        "participants": participants,
    }


def featured_upcoming(events: list, today: date | None = None, limit: int = 1) -> list:
    today = today or date.today()
    big_cats = {"acampamento", "campori", "passeio", "investidura"}
    candidates = [
        e
        for e in events
        if e.event_date >= today and (e.category or "") in big_cats and (e.status or "") != "cancelado"
    ]
    if not candidates:
        candidates = [e for e in events if e.event_date >= today and (e.status or "") != "cancelado"]
    candidates.sort(key=lambda e: (e.event_date, e.event_time or ""))
    return candidates[:limit]


def timeline_events(events: list, today: date | None = None, limit: int = 8) -> list:
    today = today or date.today()
    upcoming = [e for e in events if e.event_date >= today and (e.status or "") != "cancelado"]
    upcoming.sort(key=lambda e: (e.event_date, e.event_time or ""))
    return upcoming[:limit]


def reminder_for_events(events: list, today: date | None = None) -> dict | None:
    today = today or date.today()
    for e in sorted(events, key=lambda x: x.event_date):
        if e.event_date < today or (e.status or "") == "cancelado":
            continue
        delta = (e.event_date - today).days
        if 0 < delta <= 7:
            cat = event_category_meta(e.category)
            return {
                "title": e.title,
                "days": delta,
                "icon": cat["icon"],
                "date": e.event_date.strftime("%d/%m"),
            }
    return None


def apply_agenda_form(ev, form, files=None) -> None:
    """Aplica formulário (drawer ou legado) ao evento."""
    save_action = (form.get("save_action") or "publish").strip().lower()
    title = (form.get("title") or "").strip()
    if not title and save_action != "draft":
        raise ValueError("Nome do evento é obrigatório.")
    ev.title = title or "Evento sem título"

    ev.body = (form.get("body") or "").strip() or None

    d_raw = (form.get("event_date") or "").strip()
    if not d_raw:
        raise ValueError("Data de início é obrigatória.")
    try:
        ev.event_date = date.fromisoformat(d_raw[:10])
    except ValueError:
        raise ValueError("Data de início inválida.")

    end_raw = (form.get("event_end_date") or "").strip()
    if end_raw:
        try:
            ev.event_end_date = date.fromisoformat(end_raw[:10])
        except ValueError:
            raise ValueError("Data de fim inválida.")
    else:
        ev.event_end_date = None

    tm = (form.get("event_time") or "").strip() or None
    if tm and len(tm) > 8:
        tm = tm[:8]
    ev.event_time = tm

    etm = (form.get("event_end_time") or "").strip() or None
    if etm and len(etm) > 8:
        etm = etm[:8]
    ev.event_end_time = etm

    cat = (form.get("category") or "reuniao").strip()
    if cat not in CATEGORY_IDS:
        raise ValueError("Tipo de evento inválido.")
    ev.category = cat

    color = (form.get("color_hex") or "").strip()
    if color and not color.startswith("#"):
        color = "#" + color
    ev.color_hex = color if color and len(color) <= 7 else None

    st = (form.get("status") or "planejado").strip()
    if save_action == "draft":
        st = "rascunho"
    elif st not in STATUS_IDS:
        st = "planejado"
    if st not in STATUS_IDS:
        raise ValueError("Status inválido.")
    ev.status = st

    ev.location = (form.get("location") or "").strip() or None
    unit = (form.get("unit") or "").strip() or None
    if unit and unit not in CLUB_UNIT_OPTIONS:
        raise ValueError("Unidade inválida.")
    ev.unit = unit
    ev.responsible_name = (form.get("responsible_name") or "").strip() or None

    cap_raw = (form.get("max_capacity") or "").strip()
    if cap_raw:
        try:
            cap = int(cap_raw)
            if cap < 0:
                raise ValueError()
            ev.max_capacity = cap if cap > 0 else None
        except ValueError:
            raise ValueError("Limite de vagas inválido.")
    else:
        ev.max_capacity = None

    meta_raw = (form.get("meta_json") or "").strip()
    if meta_raw:
        try:
            parsed = json.loads(meta_raw)
            if not isinstance(parsed, dict):
                raise ValueError()
            ev.meta_json = json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            raise ValueError("Dados extras do evento inválidos.")
    elif form.get("audience") is not None:
        ev.meta_json = json.dumps(_meta_from_form_fields(form), ensure_ascii=False)


def _meta_from_form_fields(form) -> dict[str, Any]:
    audience = form.getlist("audience") if hasattr(form, "getlist") else []
    if not audience and form.get("audience"):
        audience = [form.get("audience")]
    checklist_done = form.getlist("checklist_done") if hasattr(form, "getlist") else []
    return {
        "audience": [a for a in audience if a],
        "require_rsvp": (form.get("require_rsvp") or "") in ("1", "on", "true"),
        "allow_guests": (form.get("allow_guests") or "") in ("1", "on", "true"),
        "send_notification": (form.get("send_notification") or "") in ("1", "on", "true"),
        "qr_checkin": (form.get("qr_checkin") or "") in ("1", "on", "true"),
        "auto_reminder": (form.get("auto_reminder") or "") in ("1", "on", "true"),
        "responsible_id": (form.get("responsible_id") or "").strip() or None,
        "template_id": (form.get("template_id") or "").strip() or None,
        "checklist": form.getlist("checklist") if hasattr(form, "getlist") else [],
        "checklist_done": checklist_done,
    }


def batch_confirmed_counts(event_ids: list[int]) -> dict[int, int]:
    if not event_ids:
        return {}
    from sqlalchemy import func

    from app.extensions import db
    from app.models import AgendaEventRSVP

    rows = (
        db.session.query(AgendaEventRSVP.event_id, func.count(AgendaEventRSVP.id))
        .filter(
            AgendaEventRSVP.event_id.in_(event_ids),
            AgendaEventRSVP.status == "confirmed",
        )
        .group_by(AgendaEventRSVP.event_id)
        .all()
    )
    return {int(eid): int(cnt) for eid, cnt in rows}


def user_rsvp_map(event_ids: list[int], user_id: int) -> dict[int, dict]:
    if not event_ids:
        return {}
    from app.models import AgendaEventRSVP

    rows = AgendaEventRSVP.query.filter(
        AgendaEventRSVP.event_id.in_(event_ids),
        AgendaEventRSVP.user_id == user_id,
        AgendaEventRSVP.status == "confirmed",
    ).all()
    out = {}
    for r in rows:
        out[r.event_id] = {
            "id": r.id,
            "member_id": r.member_id,
            "status": r.status,
        }
    return out


def toggle_rsvp(event_id: int, user_id: int, member_id: int | None = None) -> tuple[str, int]:
    from app.extensions import db
    from app.models import AgendaEvent, AgendaEventRSVP

    ev = db.session.get(AgendaEvent, event_id)
    if not ev:
        raise ValueError("Evento não encontrado.")
    if (ev.status or "") == "cancelado":
        raise ValueError("Este evento foi cancelado.")
    if ev.event_date < date.today():
        raise ValueError("Não é possível confirmar presença em eventos passados.")

    q = AgendaEventRSVP.query.filter_by(
        event_id=event_id, user_id=user_id, member_id=member_id
    )
    existing = q.first()
    if existing and existing.status == "confirmed":
        existing.status = "cancelled"
        db.session.commit()
        return "cancelled", ev.confirmed_rsvp_count()

    if ev.max_capacity and ev.confirmed_rsvp_count() >= ev.max_capacity:
        raise ValueError("Evento lotado — não há mais vagas.")

    if existing:
        existing.status = "confirmed"
        existing.updated_at = datetime.utcnow()
    else:
        db.session.add(
            AgendaEventRSVP(
                event_id=event_id,
                user_id=user_id,
                member_id=member_id,
                status="confirmed",
            )
        )
    db.session.commit()
    return "confirmed", ev.confirmed_rsvp_count()
