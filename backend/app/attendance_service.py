"""Serviço de presenças — métricas, chamada em lote, calendário e alertas."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from typing import Callable

from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models import Attendance, Member

ATT_PRESENTE = "presente"
ATT_FALTA = "falta"
ATT_ATRASADO = "atrasado"
ATT_JUSTIFICADO = "justificado"
ATT_DISPENSA = "dispensa"
ATT_NAO_REGISTRADO = "nao_registrado"

ATT_STATUSES = (
    ATT_PRESENTE,
    ATT_FALTA,
    ATT_ATRASADO,
    ATT_JUSTIFICADO,
    ATT_DISPENSA,
)

ATT_STATUS_LABELS = {
    ATT_PRESENTE: "Presente",
    ATT_FALTA: "Falta",
    ATT_ATRASADO: "Atrasado",
    ATT_JUSTIFICADO: "Justificado",
    ATT_DISPENSA: "Dispensa",
    ATT_NAO_REGISTRADO: "Não registrado",
}

ATT_STATUS_PRESENT_BOOL = {ATT_PRESENTE, ATT_ATRASADO}


def normalize_attendance_status(raw: str | None, *, present: bool | None = None) -> str:
    s = (raw or "").strip().lower().replace(" ", "_")
    if s in ATT_STATUSES:
        return s
    if s in ("1", "true", "sim", "present"):
        return ATT_PRESENTE
    if s in ("0", "false", "nao", "absent"):
        return ATT_FALTA
    if present is True:
        return ATT_PRESENTE
    if present is False:
        return ATT_FALTA
    return ATT_PRESENTE


def sync_present_from_status(status: str) -> bool:
    return status in ATT_STATUS_PRESENT_BOOL


def member_attendance_stats(rows: list[Attendance]) -> dict:
    """Estatísticas de um membro a partir dos registros."""
    if not rows:
        return {
            "present": 0,
            "absent": 0,
            "late": 0,
            "justified": 0,
            "dispensa": 0,
            "total": 0,
            "rate": None,
        }
    present = absent = late = justified = dispensa = 0
    for a in rows:
        st = a.effective_status()
        if st == ATT_PRESENTE:
            present += 1
        elif st == ATT_ATRASADO:
            present += 1
            late += 1
        elif st == ATT_FALTA:
            absent += 1
        elif st == ATT_JUSTIFICADO:
            justified += 1
        elif st == ATT_DISPENSA:
            dispensa += 1
    denom = present + absent
    rate = round(100 * present / denom) if denom else None
    return {
        "present": present,
        "absent": absent,
        "late": late,
        "justified": justified,
        "dispensa": dispensa,
        "total": len(rows),
        "rate": rate,
    }


def _members_query(clube_id: str):
    return Member.query.filter(Member.clube_id == clube_id).order_by(Member.full_name)


def _latest_meeting_date(clube_id: str) -> date | None:
    row = (
        db.session.query(func.max(Attendance.meeting_date))
        .join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id)
        .scalar()
    )
    return row


def _meeting_rows_for_date(clube_id: str, meeting_date: date) -> dict[int, Attendance]:
    rows = (
        Attendance.query.join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id, Attendance.meeting_date == meeting_date)
        .all()
    )
    return {r.member_id: r for r in rows}


def _month_bounds(ref: date) -> tuple[date, date]:
    start = ref.replace(day=1)
    _, last = monthrange(ref.year, ref.month)
    end = ref.replace(day=last)
    return start, end


def _calendar_heatmap(clube_id: str, ref: date) -> list[dict]:
    start, end = _month_bounds(ref)
    rows = (
        db.session.query(
            Attendance.meeting_date,
            Attendance.status,
            Attendance.present,
            func.count(Attendance.id),
        )
        .join(Member, Member.id == Attendance.member_id)
        .filter(
            Member.clube_id == clube_id,
            Attendance.meeting_date >= start,
            Attendance.meeting_date <= end,
        )
        .group_by(Attendance.meeting_date, Attendance.status, Attendance.present)
        .all()
    )
    by_day: dict[date, dict] = {}
    for md, status, present, cnt in rows:
        st = normalize_attendance_status(status, present=present)
        bucket = by_day.setdefault(
            md,
            {"present": 0, "absent": 0, "late": 0, "justified": 0, "dispensa": 0, "total": 0},
        )
        bucket["total"] += int(cnt)
        if st == ATT_PRESENTE:
            bucket["present"] += int(cnt)
        elif st == ATT_ATRASADO:
            bucket["present"] += int(cnt)
            bucket["late"] += int(cnt)
        elif st == ATT_FALTA:
            bucket["absent"] += int(cnt)
        elif st == ATT_JUSTIFICADO:
            bucket["justified"] += int(cnt)
        elif st == ATT_DISPENSA:
            bucket["dispensa"] += int(cnt)

    days: list[dict] = []
    d = start
    while d <= end:
        b = by_day.get(d)
        tone = "empty"
        if b and b["total"]:
            if b["absent"] > b["present"]:
                tone = "bad"
            elif b["late"] > 0:
                tone = "warn"
            elif b["justified"] > 0 and b["present"] == 0:
                tone = "info"
            else:
                tone = "good"
        days.append(
            {
                "date": d.isoformat(),
                "day": d.day,
                "weekday": d.weekday(),
                "tone": tone,
                "has_data": bool(b),
            }
        )
        d += timedelta(days=1)
    return days


def _meeting_history(clube_id: str, limit: int = 8) -> list[dict]:
    dates = (
        db.session.query(Attendance.meeting_date)
        .join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id)
        .distinct()
        .order_by(Attendance.meeting_date.desc())
        .limit(limit)
        .all()
    )
    out = []
    for (md,) in dates:
        rows = (
            Attendance.query.join(Member, Member.id == Attendance.member_id)
            .filter(Member.clube_id == clube_id, Attendance.meeting_date == md)
            .all()
        )
        counts = member_attendance_stats(rows)
        denom = counts["present"] + counts["absent"]
        rate = round(100 * counts["present"] / denom) if denom else 0
        out.append(
            {
                "date": md,
                "date_label": md.strftime("%d/%m/%Y"),
                "title": "Reunião semanal",
                "present": counts["present"],
                "absent": counts["absent"],
                "late": counts["late"],
                "justified": counts["justified"],
                "rate": rate,
            }
        )
    return out


def _month_absences(clube_id: str, ref: date) -> int:
    start, end = _month_bounds(ref)
    return (
        Attendance.query.join(Member, Member.id == Attendance.member_id)
        .filter(
            Member.clube_id == clube_id,
            Attendance.meeting_date >= start,
            Attendance.meeting_date <= end,
            or_(
                Attendance.status == ATT_FALTA,
                and_(Attendance.status.is_(None), Attendance.present.is_(False)),
            ),
        )
        .count()
    )


def _avg_rate_30d(clube_id: str) -> int:
    since = date.today() - timedelta(days=30)
    rows = (
        Attendance.query.join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id, Attendance.meeting_date >= since)
        .all()
    )
    if not rows:
        return 0
    stats = member_attendance_stats(rows)
    denom = stats["present"] + stats["absent"]
    return round(100 * stats["present"] / denom) if denom else 0


def _sparkline_30d(clube_id: str) -> list[int]:
    since = date.today() - timedelta(days=30)
    by_week: dict[int, list[Attendance]] = defaultdict(list)
    rows = (
        Attendance.query.join(Member, Member.id == Attendance.member_id)
        .filter(Member.clube_id == clube_id, Attendance.meeting_date >= since)
        .order_by(Attendance.meeting_date.asc())
        .all()
    )
    for r in rows:
        wk = (r.meeting_date - since).days // 7
        by_week[wk].append(r)
    points = []
    for wk in range(5):
        chunk = by_week.get(wk, [])
        if not chunk:
            points.append(0)
            continue
        st = member_attendance_stats(chunk)
        denom = st["present"] + st["absent"]
        points.append(round(100 * st["present"] / denom) if denom else 0)
    return points


def _alerts(clube_id: str, members: list[Member]) -> list[dict]:
    alerts: list[dict] = []
    streak_ids: list[int] = []
    low_ids: list[int] = []
    perfect_ids: list[int] = []
    stale_ids: list[int] = []
    since_90 = date.today() - timedelta(days=90)

    for m in members:
        rows = (
            m.attendances.filter(Attendance.meeting_date >= since_90)
            .order_by(Attendance.meeting_date.desc())
            .limit(12)
            .all()
        )
        if not rows:
            stale_ids.append(m.id)
            continue
        st = member_attendance_stats(list(rows))
        if st["rate"] is not None and st["rate"] < 70:
            low_ids.append(m.id)
        if st["rate"] == 100 and st["total"] >= 3:
            perfect_ids.append(m.id)
        consecutive = 0
        for a in rows:
            if a.effective_status() == ATT_FALTA:
                consecutive += 1
            else:
                break
        if consecutive >= 3:
            streak_ids.append(m.id)

    if streak_ids:
        alerts.append(
            {
                "tone": "danger",
                "title": f"{len(streak_ids)} membro{'s' if len(streak_ids) != 1 else ''} com 3+ faltas consecutivas",
                "filter": "falta",
                "member_ids": streak_ids,
            }
        )
    if low_ids:
        alerts.append(
            {
                "tone": "warn",
                "title": f"{len(low_ids)} membro{'s' if len(low_ids) != 1 else ''} com frequência abaixo de 70%",
                "filter": "low_rate",
                "member_ids": low_ids,
            }
        )
    if stale_ids:
        alerts.append(
            {
                "tone": "info",
                "title": f"{len(stale_ids)} membro{'s' if len(stale_ids) != 1 else ''} sem registro recente (90 dias)",
                "filter": "stale",
                "member_ids": stale_ids,
            }
        )
    if perfect_ids:
        alerts.append(
            {
                "tone": "success",
                "title": f"Parabéns! {len(perfect_ids)} membro{'s' if len(perfect_ids) != 1 else ''} com 100% de presença",
                "filter": "perfect",
                "member_ids": perfect_ids,
            }
        )
    return alerts


def _ranking_month(clube_id: str, ref: date, limit: int = 5) -> list[dict]:
    start, end = _month_bounds(ref)
    members = _members_query(clube_id).all()
    ranked = []
    for m in members:
        rows = m.attendances.filter(
            Attendance.meeting_date >= start,
            Attendance.meeting_date <= end,
        ).all()
        if not rows:
            continue
        st = member_attendance_stats(list(rows))
        if st["rate"] is None:
            continue
        ranked.append(
            {
                "member_id": m.id,
                "name": m.full_name,
                "unit": m.unit or "—",
                "rate": st["rate"],
                "photo": m.photo_filename,
            }
        )
    ranked.sort(key=lambda x: (-x["rate"], x["name"]))
    return ranked[:limit]


def _roll_call_rows(
    members: list[Member],
    by_member: dict[int, Attendance],
    *,
    photo_url_builder: Callable[[str | None], str | None],
) -> list[dict]:
    rows = []
    for m in members:
        att = by_member.get(m.id)
        if att:
            status = att.effective_status()
            note = att.note or ""
            att_id = att.id
        else:
            status = ATT_NAO_REGISTRADO
            note = ""
            att_id = None
        rows.append(
            {
                "member_id": m.id,
                "name": m.full_name,
                "unit": m.unit or "—",
                "reg_code": f"#{m.id:04d}",
                "status": status,
                "status_label": ATT_STATUS_LABELS.get(status, status),
                "note": note,
                "att_id": att_id,
                "photo_url": photo_url_builder(m.photo_filename),
                "initial": (m.full_name or "?")[0].upper(),
            }
        )
    return rows


def save_roll_call(
    clube_id: str,
    meeting_date: date,
    entries: list[dict],
) -> int:
    """Persiste chamada em lote. entries: {member_id, status, note}."""
    saved = 0
    member_ids = {m.id for m in _members_query(clube_id).all()}
    for entry in entries:
        try:
            mid = int(entry.get("member_id"))
        except (TypeError, ValueError):
            continue
        if mid not in member_ids:
            continue
        status = normalize_attendance_status(entry.get("status"))
        if status == ATT_NAO_REGISTRADO:
            existing = Attendance.query.filter_by(
                member_id=mid, meeting_date=meeting_date
            ).first()
            if existing:
                db.session.delete(existing)
            continue
        note = (entry.get("note") or "").strip() or None
        row = Attendance.query.filter_by(
            member_id=mid, meeting_date=meeting_date
        ).first()
        if not row:
            row = Attendance(member_id=mid, meeting_date=meeting_date)
            db.session.add(row)
        row.status = status
        row.present = sync_present_from_status(status)
        row.note = note
        m = Member.query.get(mid)
        if m:
            m.overall_performance = m.computed_overall_performance()
        saved += 1
    db.session.commit()
    return saved


def build_attendance_portal(
    clube_id: str,
    *,
    meeting_date: date | None = None,
    calendar_month: date | None = None,
    photo_url_builder: Callable[[str | None], str | None],
) -> dict:
    today = date.today()
    meeting_date = meeting_date or _latest_meeting_date(clube_id) or today
    calendar_month = calendar_month or meeting_date.replace(day=1)

    members = _members_query(clube_id).all()
    by_member = _meeting_rows_for_date(clube_id, meeting_date)
    roll_call = _roll_call_rows(members, by_member, photo_url_builder=photo_url_builder)

    counts = {"presente": 0, "falta": 0, "atrasado": 0, "justificado": 0, "dispensa": 0, "nao_registrado": 0}
    for r in roll_call:
        key = r["status"] if r["status"] in counts else "nao_registrado"
        counts[key] += 1

    n_members = len(members)
    present_today = counts["presente"] + counts["atrasado"]
    pct_today = round(100 * present_today / n_members, 1) if n_members else 0

    last_meeting = _latest_meeting_date(clube_id)
    member_stats = []
    for m in members:
        rows = list(m.attendances)
        st = member_attendance_stats(rows)
        last = (
            m.attendances.order_by(Attendance.meeting_date.desc()).first()
        )
        member_stats.append(
            {
                "member": m,
                "present": st["present"],
                "total": st["total"],
                "rate": st["rate"],
                "last_meeting": last.meeting_date if last else None,
            }
        )

    cal_days = _calendar_heatmap(clube_id, calendar_month)
    prev_month = (calendar_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_day = calendar_month.replace(day=28) + timedelta(days=4)
    next_month = next_day.replace(day=1)
    return {
        "meeting_date": meeting_date,
        "meeting_date_iso": meeting_date.isoformat(),
        "meeting_title": "Reunião semanal",
        "meeting_time": "19:30",
        "meeting_location": "Igreja central",
        "n_members": n_members,
        "present_today": present_today,
        "present_today_pct": pct_today,
        "month_absences": _month_absences(clube_id, today),
        "avg_rate_30d": _avg_rate_30d(clube_id),
        "sparkline": _sparkline_30d(clube_id),
        "last_meeting": last_meeting,
        "last_meeting_label": last_meeting.strftime("%d/%m/%Y") if last_meeting else "—",
        "roll_call": roll_call,
        "tab_counts": {
            "all": n_members,
            "presente": counts["presente"],
            "falta": counts["falta"],
            "atrasado": counts["atrasado"],
            "justificado": counts["justificado"],
            "dispensa": counts["dispensa"],
        },
        "calendar_month": calendar_month,
        "calendar_month_iso": calendar_month.strftime("%Y-%m"),
        "calendar_prev_iso": prev_month.strftime("%Y-%m"),
        "calendar_next_iso": next_month.strftime("%Y-%m"),
        "calendar_month_label": f"{MONTH_NAMES_PT.get(calendar_month.month, '')} {calendar_month.year}".strip(),
        "calendar_days": cal_days,
        "calendar_weeks": _calendar_weeks_grid(calendar_month, cal_days),
        "alerts": _alerts(clube_id, members),
        "meeting_history": _meeting_history(clube_id),
        "ranking": _ranking_month(clube_id, today),
        "member_stats": member_stats,
        "statuses": [
            {"id": s, "label": ATT_STATUS_LABELS[s]} for s in ATT_STATUSES + (ATT_NAO_REGISTRADO,)
        ],
    }


MONTH_NAMES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def _calendar_weeks_grid(ref: date, days: list[dict]) -> list[list[dict | None]]:
    """Semanas do calendário (domingo = primeira coluna)."""
    by_iso = {d["date"]: d for d in days}
    start, end = _month_bounds(ref)
    cells: list[dict | None] = []
    d = start
    while d <= end:
        iso = d.isoformat()
        cells.append(by_iso.get(iso))
        d += timedelta(days=1)
    pad_start = (start.weekday() + 1) % 7
    padded: list[dict | None] = [None] * pad_start + cells
    while len(padded) % 7:
        padded.append(None)
    weeks = []
    for i in range(0, len(padded), 7):
        weeks.append(padded[i : i + 7])
    return weeks
