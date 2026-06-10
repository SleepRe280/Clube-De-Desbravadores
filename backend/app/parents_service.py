"""Métricas, busca e serialização — página Responsáveis e vínculos."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.extensions import db
from app.member_parent_link import children_for_parent, is_registered_parent_account
from app.models import (
    PARENT_LINK_TYPE_LABELS,
    Member,
    ParentLinkHistory,
    Profile,
    User,
)


def initials_for(name: str | None, fallback: str = "?") -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return fallback[:1].upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def parent_phone_for_user(user: User) -> str | None:
    profile = db.session.get(Profile, user.id)
    if profile and profile.phone:
        return profile.phone.strip() or None
    for child in children_for_parent(user.id):
        raw = child.guardians_json
        if not raw:
            continue
        try:
            guardians = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(guardians, list):
            continue
        email_l = (user.email or "").lower()
        for g in guardians:
            if not isinstance(g, dict):
                continue
            g_email = (g.get("email") or "").strip().lower()
            if g_email and g_email == email_l:
                ph = (g.get("phone") or "").strip()
                if ph:
                    return ph
    return None


def account_status(user: User) -> str:
    if not user.email_verified:
        return "pendente"
    return "ativo"


def parents_metrics(clube_id: str | None) -> dict:
    """KPIs do painel de responsáveis."""
    month_start = datetime.utcnow() - timedelta(days=30)

    parents_q = (
        db.session.query(User)
        .join(Profile, Profile.id == User.id)
        .filter(User.role == "parent")
    )
    members_q = Member.query
    if clube_id:
        parents_q = parents_q.filter(Profile.clube_id == clube_id)
        members_q = members_q.filter(Member.clube_id == clube_id)

    parent_users = [p for p in parents_q.all() if is_registered_parent_account(p)]
    n_parents = len(parent_users)

    unlinked_q = members_q.filter(Member.parent_id.is_(None))
    n_unlinked = unlinked_q.count()

    hist_q = ParentLinkHistory.query.filter(
        ParentLinkHistory.action == "link",
        ParentLinkHistory.created_at >= month_start,
    )
    if clube_id:
        hist_q = hist_q.filter(ParentLinkHistory.clube_id == clube_id)
    links_month = hist_q.count()

    # Contas sem filhos ou e-mail não verificado
    n_pending = 0
    for p in parent_users:
        kids = children_for_parent(p.id)
        if clube_id:
            kids = [k for k in kids if k.clube_id == clube_id]
        if not kids or not p.email_verified:
            n_pending += 1

    return {
        "n_parents": n_parents,
        "n_unlinked": n_unlinked,
        "links_month": links_month,
        "n_pending": n_pending,
    }


def serialize_parent_row(user: User, clube_id: str | None) -> dict:
    kids = children_for_parent(user.id)
    if clube_id:
        kids = [k for k in kids if k.clube_id == clube_id]
    phone = parent_phone_for_user(user)
    status = account_status(user)
    return {
        "user": user,
        "children": kids,
        "n_children": len(kids),
        "phone": phone,
        "initials": initials_for(user.full_name or user.email),
        "status": status,
        "last_seen": user.last_seen_at,
    }


def serialize_member_card(member: Member) -> dict:
    has_parent = member.parent_id is not None
    link_label = None
    if has_parent and member.parent_link_type:
        link_label = PARENT_LINK_TYPE_LABELS.get(
            member.parent_link_type, member.parent_link_type
        )
    return {
        "id": member.id,
        "full_name": member.full_name,
        "unit": member.unit,
        "age": member.age_years,
        "initials": initials_for(member.full_name),
        "photo_url": None,
        "has_parent": has_parent,
        "link_type_label": link_label,
        "status": "vinculado" if has_parent else "sem_responsavel",
    }


def search_parents(clube_id: str | None, query: str, *, limit: int = 12) -> list[dict]:
    q = (query or "").strip().lower()
    parents_q = (
        db.session.query(User)
        .join(Profile, Profile.id == User.id)
        .filter(User.role == "parent")
    )
    if clube_id:
        parents_q = parents_q.filter(Profile.clube_id == clube_id)
    rows = []
    for user in parents_q.order_by(User.full_name.asc()).all():
        if not is_registered_parent_account(user):
            continue
        label = f"{user.full_name or 'Sem nome'} — {user.email}"
        if q and q not in label.lower() and q not in (user.email or "").lower():
            continue
        kids = children_for_parent(user.id)
        if clube_id:
            kids = [k for k in kids if k.clube_id == clube_id]
        rows.append(
            {
                "id": user.id,
                "name": user.full_name or "Sem nome",
                "email": user.email,
                "initials": initials_for(user.full_name or user.email),
                "n_children": len(kids),
                "status": account_status(user),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def search_unlinked_members(clube_id: str | None, query: str, *, limit: int = 12) -> list[dict]:
    q = (query or "").strip().lower()
    mq = Member.query.filter(Member.parent_id.is_(None))
    if clube_id:
        mq = mq.filter(Member.clube_id == clube_id)
    rows = []
    for m in mq.order_by(Member.full_name.asc()).all():
        label = m.full_name.lower()
        if m.unit:
            label += f" {m.unit.lower()}"
        if q and q not in label:
            continue
        rows.append(serialize_member_card(m))
        if len(rows) >= limit:
            break
    return rows


def suggest_parents_for_member(member: Member, clube_id: str | None) -> list[dict]:
    """Sugere contas de responsável com base nos contatos da ficha."""
    raw = member.guardians_json
    if not raw:
        return []
    try:
        guardians = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(guardians, list):
        return []

    suggestions: list[dict] = []
    seen: set[int] = set()
    for g in guardians:
        if not isinstance(g, dict):
            continue
        email = (g.get("email") or "").strip().lower()
        if not email:
            continue
        user = User.query.filter_by(email=email).first()
        if not user or not is_registered_parent_account(user):
            continue
        profile = db.session.get(Profile, user.id)
        if clube_id and profile and profile.clube_id != clube_id:
            continue
        if user.id in seen:
            continue
        seen.add(user.id)
        relation = (g.get("relation") or g.get("role") or "Responsável").strip()
        suggestions.append(
            {
                "id": user.id,
                "name": user.full_name or g.get("name") or "Sem nome",
                "email": user.email,
                "initials": initials_for(user.full_name or user.email),
                "relation": relation,
                "n_children": len(children_for_parent(user.id)),
            }
        )
    return suggestions[:5]


def link_history_for_club(clube_id: str | None, *, limit: int = 20) -> list[ParentLinkHistory]:
    from sqlalchemy.orm import joinedload

    q = ParentLinkHistory.query.options(
        joinedload(ParentLinkHistory.performed_by)
    ).order_by(ParentLinkHistory.created_at.desc())
    if clube_id:
        q = q.filter(ParentLinkHistory.clube_id == clube_id)
    return q.limit(limit).all()
