"""Almoxarifado — dashboard, itens, movimentações e categorias."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from sqlalchemy import func

from app.extensions import db
from app.finance_util import format_brl_cents, parse_money_brl
from app.models import (
    DEFAULT_WAREHOUSE_CATEGORIES,
    WH_MOVEMENT_IN,
    WH_MOVEMENT_OUT,
    WH_STOCK_LOW,
    WH_STOCK_OK,
    WH_STOCK_OUT,
    WH_UNIT_LABELS,
    WH_UNIT_OPTIONS,
    WarehouseCategory,
    WarehouseItem,
    WarehouseMovement,
)

STOCK_LABELS = {
    WH_STOCK_OK: "Em estoque",
    WH_STOCK_LOW: "Estoque baixo",
    WH_STOCK_OUT: "Sem estoque",
}

STOCK_CSS = {
    WH_STOCK_OK: "wh-badge--ok",
    WH_STOCK_LOW: "wh-badge--low",
    WH_STOCK_OUT: "wh-badge--out",
}


def ensure_default_categories(clube_id: str) -> None:
    existing = WarehouseCategory.query.filter_by(clube_id=clube_id).count()
    if existing:
        return
    for i, name in enumerate(DEFAULT_WAREHOUSE_CATEGORIES):
        db.session.add(WarehouseCategory(clube_id=clube_id, name=name, sort_order=i))
    db.session.flush()


def item_stock_status(item: WarehouseItem) -> str:
    return item.stock_status()


def _month_bounds(ref: date | None = None) -> tuple[datetime, datetime]:
    today = ref or date.today()
    start = datetime(today.year, today.month, 1)
    last_day = monthrange(today.year, today.month)[1]
    end = datetime(today.year, today.month, last_day, 23, 59, 59)
    return start, end


def warehouse_summary(clube_id: str) -> dict:
    items = WarehouseItem.query.filter_by(clube_id=clube_id, active=True).all()
    total_items = len(items)
    low_count = sum(1 for i in items if i.stock_status() == WH_STOCK_LOW)
    out_count = sum(1 for i in items if i.stock_status() == WH_STOCK_OUT)
    value_cents = sum(i.estimated_value_cents() for i in items)

    start, end = _month_bounds()
    month_in = (
        db.session.query(func.coalesce(func.sum(WarehouseMovement.quantity), 0))
        .filter(
            WarehouseMovement.clube_id == clube_id,
            WarehouseMovement.direction == WH_MOVEMENT_IN,
            WarehouseMovement.created_at >= start,
            WarehouseMovement.created_at <= end,
        )
        .scalar()
        or 0
    )
    month_out = (
        db.session.query(func.coalesce(func.sum(WarehouseMovement.quantity), 0))
        .filter(
            WarehouseMovement.clube_id == clube_id,
            WarehouseMovement.direction == WH_MOVEMENT_OUT,
            WarehouseMovement.created_at >= start,
            WarehouseMovement.created_at <= end,
        )
        .scalar()
        or 0
    )

    return {
        "total_items": total_items,
        "low_count": low_count,
        "out_count": out_count,
        "month_in": int(month_in),
        "month_out": int(month_out),
        "value_cents": int(value_cents),
        "value_label": format_brl_cents(value_cents),
    }


def serialize_item(item: WarehouseItem, *, photo_url: str | None = None) -> dict:
    status = item.stock_status()
    cat = item.category.name if item.category else "—"
    return {
        "id": item.id,
        "name": item.name,
        "internal_code": item.internal_code or "—",
        "category": cat,
        "category_id": item.category_id,
        "unit": item.unit,
        "unit_label": WH_UNIT_LABELS.get(item.unit, item.unit),
        "quantity": int(item.quantity or 0),
        "min_stock": int(item.min_stock or 0),
        "location": item.location or "—",
        "notes": item.notes or "",
        "photo": item.photo_filename,
        "photo_url": photo_url,
        "status": status,
        "status_label": STOCK_LABELS[status],
        "status_css": STOCK_CSS[status],
        "unit_price_cents": int(item.unit_price_cents or 0),
        "unit_price_label": format_brl_cents(item.unit_price_cents),
        "value_label": format_brl_cents(item.estimated_value_cents()),
    }


def serialize_movement(
    mv: WarehouseMovement,
    *,
    viewer_id: int | None = None,
    can_write: bool = False,
) -> dict:
    item = mv.item
    user = mv.created_by
    who = ""
    if user:
        who = (user.full_name or user.email or "").strip()
    direction_label = "Entrada" if mv.direction == WH_MOVEMENT_IN else "Saída"
    creator_id = mv.created_by_id
    can_delete = bool(
        can_write
        and (creator_id is None or viewer_id is None or creator_id == viewer_id)
    )
    return {
        "id": mv.id,
        "item_id": mv.item_id,
        "item_name": item.name if item else "—",
        "direction": mv.direction,
        "direction_label": direction_label,
        "quantity": int(mv.quantity or 0),
        "notes": mv.notes or "",
        "balance_after": mv.balance_after,
        "created_by": who or "—",
        "created_by_id": creator_id,
        "can_delete": can_delete,
        "created_label": mv.created_at.strftime("%d/%m/%Y %H:%M") if mv.created_at else "",
        "created_at_iso": mv.created_at.isoformat() if mv.created_at else "",
    }


def build_warehouse_dashboard(
    clube_id: str,
    *,
    photo_url_builder,
    viewer_id: int | None = None,
    can_write: bool = False,
) -> dict:
    ensure_default_categories(clube_id)
    categories = (
        WarehouseCategory.query.filter_by(clube_id=clube_id)
        .order_by(WarehouseCategory.sort_order, WarehouseCategory.name)
        .all()
    )
    items = (
        WarehouseItem.query.filter_by(clube_id=clube_id, active=True)
        .order_by(WarehouseItem.name)
        .all()
    )
    summary = warehouse_summary(clube_id)

    serialized_items = []
    for item in items:
        photo_url = photo_url_builder(item.photo_filename) if item.photo_filename else None
        serialized_items.append(serialize_item(item, photo_url=photo_url))

    movements = (
        WarehouseMovement.query.filter_by(clube_id=clube_id)
        .order_by(WarehouseMovement.created_at.desc())
        .limit(200)
        .all()
    )
    all_movements = [
        serialize_movement(m, viewer_id=viewer_id, can_write=can_write) for m in movements
    ]
    month_in_list = [m for m in all_movements if m["direction"] == WH_MOVEMENT_IN]
    month_out_list = [m for m in all_movements if m["direction"] == WH_MOVEMENT_OUT]

    low_items = [i for i in serialized_items if i["status"] in (WH_STOCK_LOW, WH_STOCK_OUT)][:8]

    category_counts: dict[int, int] = {}
    for cat in categories:
        category_counts[cat.id] = sum(1 for it in items if it.category_id == cat.id)

    return {
        "summary": summary,
        "categories": categories,
        "category_counts": category_counts,
        "stock_items": serialized_items,
        "movements": all_movements,
        "movements_in": month_in_list,
        "movements_out": month_out_list,
        "low_items": low_items,
        "unit_options": list(WH_UNIT_OPTIONS),
        "unit_labels": WH_UNIT_LABELS,
        "today": date.today(),
    }


def apply_item_form(item: WarehouseItem, form: dict) -> str | None:
    name = (form.get("name") or "").strip()
    if not name:
        return "Informe o nome do item."
    item.name = name[:160]
    item.internal_code = (form.get("internal_code") or "").strip()[:40] or None
    unit = (form.get("unit") or "un").strip()
    if unit not in WH_UNIT_OPTIONS:
        unit = "un"
    item.unit = unit
    item.location = (form.get("location") or "").strip()[:120] or None
    item.notes = (form.get("notes") or "").strip() or None

    try:
        cat_id = int(form.get("category_id") or 0)
    except (TypeError, ValueError):
        cat_id = 0
    if cat_id:
        cat = db.session.get(WarehouseCategory, cat_id)
        if cat and cat.clube_id == item.clube_id:
            item.category_id = cat.id
        else:
            item.category_id = None
    else:
        item.category_id = None

    try:
        min_stock = int(form.get("min_stock") or 0)
    except (TypeError, ValueError):
        min_stock = 0
    item.min_stock = max(0, min_stock)

    price_raw = form.get("unit_price") or form.get("unit_price_cents")
    if price_raw is not None:
        if isinstance(price_raw, int):
            item.unit_price_cents = max(0, price_raw)
        else:
            cents = parse_money_brl(str(price_raw))
            if cents is not None:
                item.unit_price_cents = cents

    return None


def record_movement(
    item: WarehouseItem,
    direction: str,
    quantity: int,
    *,
    notes: str | None = None,
    user_id: int | None = None,
) -> str | None:
    if quantity <= 0:
        return "Informe uma quantidade válida."
    if direction not in (WH_MOVEMENT_IN, WH_MOVEMENT_OUT):
        return "Tipo de movimentação inválido."

    current = int(item.quantity or 0)
    if direction == WH_MOVEMENT_OUT and quantity > current:
        return f"Estoque insuficiente (disponível: {current})."

    if direction == WH_MOVEMENT_IN:
        item.quantity = current + quantity
    else:
        item.quantity = current - quantity

    item.updated_at = datetime.utcnow()
    balance = int(item.quantity)
    mv = WarehouseMovement(
        clube_id=item.clube_id,
        item_id=item.id,
        direction=direction,
        quantity=quantity,
        notes=(notes or "").strip() or None,
        balance_after=balance,
        created_by_id=user_id,
    )
    db.session.add(mv)
    return None


def delete_movement(mv: WarehouseMovement, *, viewer_id: int | None = None) -> str | None:
    """Remove um lançamento e reverte o estoque. Só o autor do lançamento pode excluir."""
    if mv.created_by_id is not None and viewer_id is not None and mv.created_by_id != viewer_id:
        return "Só quem registrou este lançamento pode excluí-lo."

    item = mv.item
    if not item or not item.active:
        return "Item não encontrado."

    qty = int(mv.quantity or 0)
    if qty <= 0:
        return "Lançamento inválido."

    current = int(item.quantity or 0)
    if mv.direction == WH_MOVEMENT_IN:
        if current < qty:
            return (
                "Não é possível excluir esta entrada: o estoque atual é menor que a quantidade "
                "lançada (há saídas posteriores)."
            )
        item.quantity = current - qty
    elif mv.direction == WH_MOVEMENT_OUT:
        item.quantity = current + qty
    else:
        return "Tipo de movimentação inválido."

    item.updated_at = datetime.utcnow()
    db.session.delete(mv)
    return None
