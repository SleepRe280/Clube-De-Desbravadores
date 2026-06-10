"""Navegação hierárquica do painel admin — grupos expansíveis (accordion)."""
from __future__ import annotations

DESBRAVADORES_GROUP_ID = "desbravadores"

DESBRAVADORES_CHILD_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "members": (
        "admin.members",
        "admin.member_new",
        "admin.member_edit",
        "admin.member_profile",
    ),
    "units": (
        "admin.admin_units",
        "admin.admin_unit_create",
        "admin.admin_unit_detail",
        "admin.admin_unit_edit",
        "admin.admin_unit_role_create",
        "admin.admin_unit_role_update",
        "admin.admin_unit_role_delete",
        "admin.admin_unit_member_add",
        "admin.admin_unit_member_role",
        "admin.admin_unit_member_remove",
    ),
    "attendance": ("admin.attendance_overview",),
    "specialties": ("admin.admin_specialties",),
    "activities": (
        "admin.admin_activities",
        "admin.activities_requirement_status",
        "admin.activities_homework_create",
        "admin.activities_homework_review",
        "admin.activities_requirements_json",
    ),
}

DESBRAVADORES_ALL_ENDPOINTS: frozenset[str] = frozenset(
    ep for eps in DESBRAVADORES_CHILD_ENDPOINTS.values() for ep in eps
)


def desbravadores_nav_context(endpoint: str | None) -> dict:
    """Estado do accordion «Desbravadores» para templates admin."""
    ep = (endpoint or "").strip()
    child_active = {
        key: ep in eps for key, eps in DESBRAVADORES_CHILD_ENDPOINTS.items()
    }
    return {
        "ap_nav_desbravadores_open": ep in DESBRAVADORES_ALL_ENDPOINTS,
        "ap_nav_desbravadores_child_active": child_active,
        "ap_nav_desbravadores_has_active": any(child_active.values()),
    }
