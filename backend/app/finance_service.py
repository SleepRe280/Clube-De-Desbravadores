"""Serviço financeiro — dashboard, cobranças, PIX, comprovantes e auditoria."""

from __future__ import annotations

import json
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.club_services import billable_members_query, finance_ledger_query, get_pix_for_club
from app.extensions import db
from app.finance_util import format_brl_cents
from app.models import (
    FEE_CATEGORIES,
    FEE_STATUS_ATRASADO,
    FEE_STATUS_CANCELADO,
    FEE_STATUS_PAGO,
    FEE_STATUS_PENDENTE,
    FinanceAuditLog,
    FinanceLedgerEntry,
    Member,
    MemberFee,
    PaymentProof,
    PROOF_STATUS_APPROVED,
    PROOF_STATUS_PENDING,
    PROOF_STATUS_REJECTED,
    PROOF_STATUS_REVISION,
)
from app.pix_util import build_pix_static_payload, pix_qr_data_uri

CATEGORY_LABELS = {
    "mensalidade": "Mensalidade",
    "eventos": "Eventos",
    "alimentacao": "Alimentação",
    "transporte": "Transporte",
    "uniforme": "Uniforme",
    "materiais": "Materiais",
    "doacoes": "Doações",
    "campori": "Campori",
    "outros": "Outros",
}

STATUS_LABELS = {
    FEE_STATUS_PAGO: "Pago",
    FEE_STATUS_PENDENTE: "Pendente",
    FEE_STATUS_ATRASADO: "Vencido",
    FEE_STATUS_CANCELADO: "Cancelado",
}


def log_finance_action(
    clube_id: str | None,
    action: str,
    *,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
) -> None:
    row = FinanceAuditLog(
        clube_id=clube_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details_json=json.dumps(details or {}, ensure_ascii=False) if details else None,
    )
    db.session.add(row)


def credit_fee_to_ledger(fee: MemberFee, *, user_id: int | None = None) -> FinanceLedgerEntry | None:
    """Registra entrada no caixa somente quando o diretor confirma o pagamento (botão Pago)."""
    if fee.paid_at is None:
        return None
    existing = FinanceLedgerEntry.query.filter_by(member_fee_id=fee.id).first()
    if existing:
        return existing
    member = fee.member
    if not member or not member.clube_id:
        return None
    amount = fee.effective_amount_cents()
    if amount <= 0:
        return None
    title = (fee.title or "Mensalidade").strip()
    desc = f"{title} — {member.full_name}"[:400]
    row = FinanceLedgerEntry(
        clube_id=member.clube_id,
        occurred_at=date.today(),
        direction="income",
        amount_cents=amount,
        description=desc,
        category=(fee.category or "mensalidade") if (fee.category or "") in FEE_CATEGORIES else "mensalidade",
        notes=f"Pagamento confirmado (cobrança #{fee.id})",
        member_id=member.id,
        member_fee_id=fee.id,
        created_by_id=user_id,
    )
    db.session.add(row)
    return row


def fee_status_badge(status: str) -> str:
    return {
        FEE_STATUS_PAGO: "fn-badge--paid",
        FEE_STATUS_PENDENTE: "fn-badge--pending",
        FEE_STATUS_ATRASADO: "fn-badge--overdue",
        FEE_STATUS_CANCELADO: "fn-badge--cancelled",
    }.get(status, "fn-badge--pending")


def serialize_fee(fee: MemberFee, today: date | None = None) -> dict:
    st = fee.computed_status(today)
    return {
        "id": fee.id,
        "member_id": fee.member_id,
        "member_name": fee.member.full_name if fee.member else "",
        "member_photo": getattr(fee.member, "photo_filename", None) if fee.member else None,
        "title": fee.title,
        "category": fee.category or "mensalidade",
        "category_label": CATEGORY_LABELS.get(fee.category or "mensalidade", "Outros"),
        "amount_cents": fee.effective_amount_cents(),
        "raw_amount_cents": fee.amount_cents,
        "due_date": fee.due_date,
        "due_label": fee.due_date.strftime("%d/%m/%Y"),
        "paid_at": fee.paid_at,
        "status": st,
        "status_label": STATUS_LABELS.get(st, st),
        "status_css": fee_status_badge(st),
        "notes": fee.notes or "",
        "installment": (
            f"{fee.installment_n}/{fee.installment_total}"
            if fee.installment_n and fee.installment_total
            else None
        ),
    }


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def monthly_flow(clube_id: str, months: int = 6) -> dict:
    today = date.today()
    labels = []
    income = []
    expense = []
    balance_acc = []
    running = 0
    y, m = today.year, today.month
    points = []
    for _ in range(months - 1, -1, -1):
        mm = m - _
        yy = y
        while mm < 1:
            mm += 12
            yy -= 1
        start, end = _month_bounds(yy, mm)
        points.append((start, end, f"{start.strftime('%b')}/{str(yy)[-2:]}"))
    points.reverse()
    for start, end, label in points:
        inc = (
            db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
            .filter(
                FinanceLedgerEntry.clube_id == clube_id,
                FinanceLedgerEntry.direction == "income",
                FinanceLedgerEntry.occurred_at >= start,
                FinanceLedgerEntry.occurred_at <= end,
            )
            .scalar()
            or 0
        )
        out = (
            db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
            .filter(
                FinanceLedgerEntry.clube_id == clube_id,
                FinanceLedgerEntry.direction == "expense",
                FinanceLedgerEntry.occurred_at >= start,
                FinanceLedgerEntry.occurred_at <= end,
            )
            .scalar()
            or 0
        )
        running += int(inc) - int(out)
        labels.append(label)
        income.append(int(inc))
        expense.append(int(out))
        balance_acc.append(running)
    return {"labels": labels, "income": income, "expense": expense, "balance": balance_acc}


def dashboard_summary(clube_id: str) -> dict:
    today = date.today()
    month_start, month_end = _month_bounds(today.year, today.month)
    prev_m = today.month - 1
    prev_y = today.year
    if prev_m < 1:
        prev_m = 12
        prev_y -= 1
    prev_start, prev_end = _month_bounds(prev_y, prev_m)

    total_in = (
        db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
        .filter(FinanceLedgerEntry.clube_id == clube_id, FinanceLedgerEntry.direction == "income")
        .scalar()
        or 0
    )
    total_out = (
        db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
        .filter(FinanceLedgerEntry.clube_id == clube_id, FinanceLedgerEntry.direction == "expense")
        .scalar()
        or 0
    )
    month_in = (
        db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
        .filter(
            FinanceLedgerEntry.clube_id == clube_id,
            FinanceLedgerEntry.direction == "income",
            FinanceLedgerEntry.occurred_at >= month_start,
            FinanceLedgerEntry.occurred_at <= month_end,
        )
        .scalar()
        or 0
    )
    month_out = (
        db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
        .filter(
            FinanceLedgerEntry.clube_id == clube_id,
            FinanceLedgerEntry.direction == "expense",
            FinanceLedgerEntry.occurred_at >= month_start,
            FinanceLedgerEntry.occurred_at <= month_end,
        )
        .scalar()
        or 0
    )
    prev_in = (
        db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
        .filter(
            FinanceLedgerEntry.clube_id == clube_id,
            FinanceLedgerEntry.direction == "income",
            FinanceLedgerEntry.occurred_at >= prev_start,
            FinanceLedgerEntry.occurred_at <= prev_end,
        )
        .scalar()
        or 0
    )
    prev_out = (
        db.session.query(func.coalesce(func.sum(FinanceLedgerEntry.amount_cents), 0))
        .filter(
            FinanceLedgerEntry.clube_id == clube_id,
            FinanceLedgerEntry.direction == "expense",
            FinanceLedgerEntry.occurred_at >= prev_start,
            FinanceLedgerEntry.occurred_at <= prev_end,
        )
        .scalar()
        or 0
    )

    fees_q = (
        MemberFee.query.join(Member, Member.id == MemberFee.member_id)
        .filter(Member.clube_id == clube_id, MemberFee.paid_at.is_(None))
        .filter((MemberFee.status.is_(None)) | (MemberFee.status != FEE_STATUS_CANCELADO))
    )
    pending_cents = 0
    pending_count = 0
    overdue_count = 0
    for f in fees_q.all():
        st = f.computed_status(today)
        if st == FEE_STATUS_CANCELADO:
            continue
        pending_cents += f.effective_amount_cents()
        pending_count += 1
        if st == FEE_STATUS_ATRASADO:
            overdue_count += 1

    def pct_change(cur: int, prev: int) -> int | None:
        if prev <= 0:
            return None if cur <= 0 else 100
        return int(round(100 * (cur - prev) / prev))

    balance = int(total_in) - int(total_out)
    cash_status = "positivo" if balance >= 0 else "atencao"

    return {
        "balance_cents": balance,
        "month_in_cents": int(month_in),
        "month_out_cents": int(month_out),
        "pending_cents": pending_cents,
        "pending_count": pending_count,
        "overdue_count": overdue_count,
        "month_in_delta_pct": pct_change(int(month_in), int(prev_in)),
        "month_out_delta_pct": pct_change(int(month_out), int(prev_out)),
        "cash_status": cash_status,
    }


def fees_summary_counts(clube_id: str) -> dict:
    today = date.today()
    paid = pending = overdue = 0
    rows = (
        MemberFee.query.join(Member, Member.id == MemberFee.member_id)
        .filter(Member.clube_id == clube_id)
        .all()
    )
    for f in rows:
        st = f.computed_status(today)
        if st == FEE_STATUS_PAGO:
            paid += 1
        elif st == FEE_STATUS_ATRASADO:
            overdue += 1
        elif st == FEE_STATUS_PENDENTE:
            pending += 1
    return {"paid": paid, "pending": pending, "overdue": overdue, "total": len(rows)}


def pix_context(clube_id: str, club_name: str = "Clube") -> dict:
    key = get_pix_for_club(clube_id)
    payload = build_pix_static_payload(key, merchant_name=club_name[:25]) if key else ""
    return {
        "pix_key": key,
        "pix_payload": payload,
        "pix_qr_uri": pix_qr_data_uri(payload) if payload else None,
    }


def build_finance_dashboard(clube_id: str, club_name: str = "Clube") -> dict:
    today = date.today()
    summary = dashboard_summary(clube_id)
    flow = monthly_flow(clube_id)
    fee_counts = fees_summary_counts(clube_id)

    ledger = (
        finance_ledger_query(clube_id)
        .order_by(FinanceLedgerEntry.occurred_at.desc(), FinanceLedgerEntry.id.desc())
        .limit(40)
        .all()
    )
    movements = []
    for row in ledger:
        movements.append(
            {
                "id": row.id,
                "direction": row.direction,
                "is_income": row.direction == "income",
                "amount_cents": row.amount_cents,
                "amount_label": format_brl_cents(row.amount_cents),
                "description": row.description,
                "category": row.category,
                "category_label": CATEGORY_LABELS.get(row.category or "outros", row.category or "—"),
                "date_label": row.occurred_at.strftime("%d/%m/%Y"),
                "time_ago": _relative_time(row.created_at),
            }
        )

    fees_all = (
        MemberFee.query.join(Member, Member.id == MemberFee.member_id)
        .filter(Member.clube_id == clube_id)
        .order_by(MemberFee.due_date.desc(), MemberFee.id.desc())
        .limit(80)
        .all()
    )
    fees_serialized = [serialize_fee(f, today) for f in fees_all]
    fees_open = [f for f in fees_serialized if f["status"] in (FEE_STATUS_PENDENTE, FEE_STATUS_ATRASADO)]
    fees_recent = fees_serialized[:8]

    upcoming = sorted(
        [f for f in fees_open if f["status"] != FEE_STATUS_CANCELADO],
        key=lambda x: x["due_date"],
    )[:5]

    proofs_pending = (
        PaymentProof.query.join(MemberFee, MemberFee.id == PaymentProof.member_fee_id)
        .join(Member, Member.id == MemberFee.member_id)
        .filter(Member.clube_id == clube_id, PaymentProof.status == PROOF_STATUS_PENDING)
        .order_by(PaymentProof.created_at.asc())
        .limit(20)
        .all()
    )
    pending_proofs = []
    for p in proofs_pending:
        pending_proofs.append(
            {
                "id": p.id,
                "fee_id": p.member_fee_id,
                "member_name": p.fee.member.full_name if p.fee and p.fee.member else "",
                "fee_title": p.fee.title if p.fee else "",
                "amount_label": format_brl_cents(p.fee.effective_amount_cents()) if p.fee else "",
                "created_label": p.created_at.strftime("%d/%m/%Y %H:%M") if p.created_at else "",
                "note": p.note or "",
            }
        )

    members = billable_members_query(clube_id).order_by(Member.full_name).all()

    audit = (
        FinanceAuditLog.query.filter_by(clube_id=clube_id)
        .order_by(FinanceAuditLog.created_at.desc())
        .limit(15)
        .all()
    )

    return {
        "summary": summary,
        "flow": flow,
        "fee_counts": fee_counts,
        "movements": movements,
        "fees_open": fees_open,
        "fees_recent": fees_recent,
        "fees_all": fees_serialized,
        "upcoming": upcoming,
        "pending_proofs": pending_proofs,
        "members": members,
        "pix": pix_context(clube_id, club_name),
        "categories": FEE_CATEGORIES,
        "category_labels": CATEGORY_LABELS,
        "audit_logs": audit,
        "today": today,
    }


def _relative_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    diff = datetime.utcnow() - dt
    if diff.days == 0:
        return "Hoje"
    if diff.days == 1:
        return "Ontem"
    return f"{diff.days} dias"


MONTH_ABBR_PT = (
    "JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
    "JUL", "AGO", "SET", "OUT", "NOV", "DEZ",
)


def _days_until_label(days: int) -> str:
    if days < 0:
        return f"Vencido há {abs(days)} dia(s)"
    if days == 0:
        return "Vence hoje"
    if days == 1:
        return "Em 1 dia"
    return f"Em {days} dias"


def _enrich_parent_fee_row(row: dict, today: date) -> dict:
    due = row["due_date"]
    row["due_day"] = due.day if due else None
    row["due_month_abbr"] = MONTH_ABBR_PT[due.month - 1] if due else ""
    row["amount_label"] = format_brl_cents(row["amount_cents"])
    row["is_overdue"] = row["status"] == FEE_STATUS_ATRASADO
    paid_at = row.get("paid_at")
    row["paid_label"] = paid_at.strftime("%d/%m/%Y") if paid_at else None
    if due:
        row["days_until"] = (due - today).days
    else:
        row["days_until"] = None
    return row


def build_parent_finance_context(
    children: list,
    clube_id: str | None,
    club_name: str = "Clube",
) -> dict:
    """Contexto do portal família — cobranças, PIX e comprovantes."""
    today = date.today()
    by_member = {c.id: c for c in children}
    ids = [c.id for c in children]
    fees_raw = []
    if ids:
        fees_raw = (
            MemberFee.query.filter(MemberFee.member_id.in_(ids))
            .order_by(MemberFee.due_date.desc(), MemberFee.id.desc())
            .all()
        )
    fees = []
    for f in fees_raw:
        row = serialize_fee(f, today)
        latest = (
            PaymentProof.query.filter_by(member_fee_id=f.id)
            .order_by(PaymentProof.created_at.desc())
            .first()
        )
        row["proof_status"] = latest.status if latest else None
        row["proof_id"] = latest.id if latest else None
        row["can_upload_proof"] = (
            row["status"] in (FEE_STATUS_PENDENTE, FEE_STATUS_ATRASADO)
            and (not latest or latest.status in (PROOF_STATUS_REJECTED, PROOF_STATUS_REVISION))
        )
        row["proof_approved_awaiting_payment"] = (
            row["status"] in (FEE_STATUS_PENDENTE, FEE_STATUS_ATRASADO)
            and latest is not None
            and latest.status == PROOF_STATUS_APPROVED
        )
        fees.append(_enrich_parent_fee_row(row, today))

    active_fees = [x for x in fees if x["status"] != FEE_STATUS_CANCELADO]
    fees_open = sorted(
        [x for x in active_fees if x["status"] in (FEE_STATUS_PENDENTE, FEE_STATUS_ATRASADO)],
        key=lambda x: x["due_date"],
    )
    fees_paid = sorted(
        [x for x in active_fees if x["status"] == FEE_STATUS_PAGO],
        key=lambda x: x["paid_at"] or x["due_date"],
        reverse=True,
    )
    fees_history = sorted(active_fees, key=lambda x: (x["due_date"], x["id"]), reverse=True)

    open_total_cents = sum(x["amount_cents"] for x in fees_open)
    year = today.year
    year_paid = [
        x for x in fees_paid
        if x.get("paid_at") and x["paid_at"].year == year
    ]
    year_paid_total_cents = sum(x["amount_cents"] for x in year_paid)

    last_payment = None
    paid_with_date = [x for x in fees_paid if x.get("paid_at")]
    if paid_with_date:
        last = paid_with_date[0]
        last_payment = {
            "amount_cents": last["amount_cents"],
            "amount_label": last["amount_label"],
            "paid_label": last["paid_label"],
            "title": last["title"],
        }

    next_due = None
    if fees_open:
        n = fees_open[0]
        days = (n["due_date"] - today).days
        next_due = {
            "due_label": n["due_label"],
            "days": days,
            "days_label": _days_until_label(days),
            "title": n["title"],
        }

    pix = pix_context(clube_id, club_name) if clube_id else {"pix_key": "", "pix_payload": "", "pix_qr_uri": None}
    pending = len(fees_open)
    paid = len(fees_paid)
    return {
        "children": children,
        "by_member": by_member,
        "fees": fees_history,
        "fees_open": fees_open,
        "fees_paid": fees_paid,
        "fees_history": fees_history,
        "pix": pix,
        "today": today,
        "counts": {
            "pending": pending,
            "paid": paid,
            "total": len(active_fees),
            "overdue": sum(1 for x in fees_open if x["status"] == FEE_STATUS_ATRASADO),
        },
        "summary": {
            "open_total_cents": open_total_cents,
            "open_total_label": format_brl_cents(open_total_cents),
            "open_count": pending,
            "last_payment": last_payment,
            "year": year,
            "year_paid_total_cents": year_paid_total_cents,
            "year_paid_total_label": format_brl_cents(year_paid_total_cents),
            "year_paid_count": len(year_paid),
            "next_due": next_due,
        },
    }


def generate_fees_bulk(
    clube_id: str,
    *,
    amount_cents: int,
    due_date: date,
    title: str,
    category: str,
    member_ids: list[int] | None = None,
    discount_cents: int = 0,
    fine_cents: int = 0,
    installments: int = 1,
) -> list[MemberFee]:
    q = billable_members_query(clube_id)
    if member_ids:
        q = q.filter(Member.id.in_(member_ids))
    members = q.all()
    created = []
    group = str(uuid.uuid4()) if installments > 1 else None
    inst_total = max(1, min(installments, 12))
    for m in members:
        base_amt = amount_cents // inst_total
        remainder = amount_cents % inst_total
        for n in range(1, inst_total + 1):
            amt = base_amt + (remainder if n == inst_total else 0)
            due = due_date
            if n > 1:
                mm = due_date.month + (n - 1)
                yy = due_date.year
                while mm > 12:
                    mm -= 12
                    yy += 1
                due = date(yy, mm, min(due_date.day, monthrange(yy, mm)[1]))
            fee = MemberFee(
                member_id=m.id,
                title=f"{title} ({n}/{inst_total})" if inst_total > 1 else title[:200],
                category=category if category in FEE_CATEGORIES else "mensalidade",
                amount_cents=amt,
                discount_cents=discount_cents,
                fine_cents=fine_cents,
                due_date=due,
                installment_group=group,
                installment_n=n if inst_total > 1 else None,
                installment_total=inst_total if inst_total > 1 else None,
            )
            db.session.add(fee)
            created.append(fee)
    return created
