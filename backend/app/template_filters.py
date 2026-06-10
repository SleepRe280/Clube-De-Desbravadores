"""Filtros Jinja2 — datas/horas seguras (ORM, ISO string ou texto)."""

from __future__ import annotations

from datetime import date, datetime


def _coerce_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= 10 and s[4:5] == "-":
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                pass
        return None
    if hasattr(value, "strftime"):
        return value
    return None


def fmt_date(value, fmt: str = "%d/%m/%Y") -> str:
    d = _coerce_date(value)
    if d is None:
        return str(value) if value else ""
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.strftime(fmt)
    if hasattr(d, "strftime"):
        return d.strftime(fmt)
    return str(value)


def fmt_time(value, fmt: str = "%H:%M") -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        s = value.strip()
        return s[:5] if len(s) >= 5 else s
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    return str(value)


def register_template_filters(app) -> None:
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["fmt_time"] = fmt_time
