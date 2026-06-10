"""Helpers para montar entradas do catálogo de requisitos."""

from __future__ import annotations

from typing import Any


def sec(code: str, title: str, items: list[dict[str, Any]], *, advanced: bool = False) -> dict:
    return {"code": code, "title": title, "advanced": advanced, "items": items}


def req(
    n: int,
    title: str,
    description: str = "",
    *,
    optional: bool = False,
    optional_group: str | None = None,
) -> dict:
    return {
        "number": n,
        "title": title,
        "description": description.strip(),
        "optional": optional,
        "optional_group": optional_group,
    }


def opt_req(n: int, title: str, description: str, group: str) -> dict:
    return req(n, title, description, optional=True, optional_group=group)
