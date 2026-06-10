"""Sincroniza catálogo oficial de cadernos com o banco de dados."""

from __future__ import annotations

from app.extensions import db
from app.models import NotebookClass, NotebookClassRequirement
from app.notebook_catalog.amigo import AMIGO
from app.notebook_catalog.companheiro import COMPANHEIRO
from app.notebook_catalog.excursionista import EXCURSIONISTA
from app.notebook_catalog.guia import GUIA
from app.notebook_catalog.pesquisador import PESQUISADOR
from app.notebook_catalog.pioneiro import PIONEIRO

CATALOG_VERSION = 3

ALL_CLASS_CATALOGS = (
    AMIGO,
    COMPANHEIRO,
    PESQUISADOR,
    PIONEIRO,
    EXCURSIONISTA,
    GUIA,
)

CLASS_COLORS = {
    "amigo": "#3b82f6",
    "companheiro": "#22c55e",
    "pesquisador": "#8b5cf6",
    "pioneiro": "#f97316",
    "excursionista": "#6366f1",
    "guia": "#f9bc15",
}


def sync_notebook_catalog(force: bool = False) -> None:
    """Atualiza classes e requisitos oficiais (upsert por req_key)."""
    needs_sync = force
    if not needs_sync:
        for row in ALL_CLASS_CATALOGS:
            nc = NotebookClass.query.filter_by(slug=row["slug"]).first()
            if not nc or (nc.catalog_version or 0) < CATALOG_VERSION:
                needs_sync = True
                break

    if not needs_sync and NotebookClass.query.count() == 0:
        needs_sync = True

    if not needs_sync:
        return

    sort_i = 0
    for row in ALL_CLASS_CATALOGS:
        slug = row["slug"]
        nc = NotebookClass.query.filter_by(slug=slug).first()
        if not nc:
            nc = NotebookClass(slug=slug, name=row["name"])
            db.session.add(nc)
            db.session.flush()
        nc.name = row["name"]
        nc.color_hex = row.get("color_hex") or CLASS_COLORS.get(slug, "#3b82f6")
        nc.icon_key = slug
        nc.min_age = row.get("min_age")
        nc.advanced_title = row.get("advanced_title")
        nc.catalog_version = CATALOG_VERSION
        nc.sort_order = sort_i
        nc.active = True
        sort_i += 1

        seen_keys: set[str] = set()
        order = 0
        for section in row.get("sections", []):
            sec_code = section["code"]
            sec_title = section["title"]
            is_adv = bool(section.get("advanced"))
            for item in section.get("items", []):
                req_key = f"{slug}:{sec_code}:{item['number']}"
                seen_keys.add(req_key)
                existing = NotebookClassRequirement.query.filter_by(
                    class_id=nc.id, req_key=req_key
                ).first()
                if not existing:
                    existing = NotebookClassRequirement(class_id=nc.id, req_key=req_key)
                    db.session.add(existing)
                existing.title = item["title"]
                existing.description = item.get("description") or None
                existing.section_code = sec_code
                existing.section_title = sec_title
                existing.req_number = int(item["number"])
                existing.category = sec_title
                existing.is_advanced = is_adv
                existing.is_optional = bool(item.get("optional"))
                existing.optional_group = item.get("optional_group")
                existing.sort_order = order
                order += 1

        if seen_keys:
            for o in NotebookClassRequirement.query.filter_by(class_id=nc.id).all():
                if (o.req_key or "") not in seen_keys and o.progress_rows.count() == 0:
                    db.session.delete(o)

    db.session.flush()
