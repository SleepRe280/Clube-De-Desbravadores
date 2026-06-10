"""Contexto da ficha premium do desbravador (pais + diretoria)."""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func

from app.extensions import db
from app.models import ActivityRecord, Attendance, MeetingDuque, Member, User


def format_cpf_display(digits: str | None) -> str:
    if not digits or len(digits) != 11:
        return "—"
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def _digits_phone(raw: str | None) -> str:
    return "".join(c for c in (raw or "") if c.isdigit())


def _whatsapp_url(phone: str | None) -> str | None:
    d = _digits_phone(phone)
    if len(d) < 10:
        return None
    if not d.startswith("55"):
        d = "55" + d
    return f"https://wa.me/{d}"


def _explorer_level(member: Member, duques_total: int, performance: int) -> tuple[int, str]:
    level = max(1, min(12, 1 + duques_total // 4 + performance // 15))
    return level, f"Explorador Nível {level}"


_STATUS_LABELS = {
    "ativo": "Ativo",
    "visitante": "Visitante",
    "em_treinamento": "Em treinamento",
    "inativo": "Inativo",
}


def _badges_for_member(member: Member, *, att_rate: int, performance: int, duques_total: int) -> list[dict]:
    status = (member.member_status or "ativo").strip()
    badges: list[dict] = [
        {
            "label": _STATUS_LABELS.get(status, status.title()),
            "variant": "success" if status == "ativo" else "slate",
        }
    ]
    if att_rate >= 85:
        badges.append({"label": "Frequência alta", "variant": "sky"})
    if performance >= 90:
        badges.append({"label": "Destaque", "variant": "gold"})
    elif performance >= 75:
        badges.append({"label": "Em evolução", "variant": "violet"})
    if duques_total >= 20 or performance >= 85:
        badges.append({"label": "Líder", "variant": "navy"})
    age = member.age_years
    if age is not None and age >= 13:
        badges.append({"label": "Veterano", "variant": "slate"})
    return badges[:5]


def _first_attendance_date(member_id: int) -> date | None:
    row = (
        Attendance.query.filter_by(member_id=member_id)
        .order_by(Attendance.meeting_date.asc())
        .first()
    )
    return row.meeting_date if row else None


def _timeline_events(member: Member, limit: int = 12) -> list[dict]:
    events: list[dict] = []
    try:
        from app.specialties_service import recent_specialty_achievements

        for sp in recent_specialty_achievements(member, limit=6):
            events.append(
                {
                    "title": sp["title"],
                    "subtitle": "Especialidade concluída",
                    "date": sp["date"],
                    "icon": "medal",
                    "kind": "especialidade",
                }
            )
    except Exception:
        pass
    for a in (
        ActivityRecord.query.filter_by(member_id=member.id, completed=True)
        .order_by(ActivityRecord.recorded_at.desc())
        .limit(6)
        .all()
    ):
        events.append(
            {
                "title": a.title,
                "subtitle": "Atividade concluída",
                "date": a.recorded_at,
                "icon": "trophy",
                "kind": "activity",
            }
        )
    for att in (
        Attendance.query.filter_by(member_id=member.id)
        .order_by(Attendance.meeting_date.desc())
        .limit(8)
        .all()
    ):
        events.append(
            {
                "title": "Reunião do clube",
                "subtitle": "Presente" if att.present else "Ausente",
                "date": att.meeting_date,
                "icon": "calendar",
                "kind": "attendance",
            }
        )
    for d in (
        MeetingDuque.query.filter_by(member_id=member.id)
        .order_by(MeetingDuque.meeting_date.desc())
        .limit(6)
        .all()
    ):
        if (d.duques or 0) > 0:
            events.append(
                {
                    "title": f"+{d.duques} duques",
                    "subtitle": "Reunião",
                    "date": d.meeting_date,
                    "icon": "star",
                    "kind": "duques",
                }
            )

    def sort_key(ev):
        dt = ev.get("date")
        if hasattr(dt, "year"):
            return dt
        return date.min

    events.sort(key=sort_key, reverse=True)
    return events[:limit]


def build_member_profile_context(
    member: Member,
    *,
    mode: str = "parent",
    linked_parent: User | None = None,
) -> dict:
    """Monta dados para template compartilhado da ficha premium."""
    pr, tot, att_rate = member.attendance_stats()
    performance = member.computed_overall_performance()
    notebook_pct = member.notebook_checklist_progress_percent()
    duques_total = int(
        db.session.query(func.coalesce(func.sum(MeetingDuque.duques), 0))
        .filter(MeetingDuque.member_id == member.id)
        .scalar()
        or 0
    )
    level_num, level_title = _explorer_level(member, duques_total, performance)
    entry_date = _first_attendance_date(member.id)

    parent_user = linked_parent or member.parent
    guardians = []
    if member.guardians_json:
        try:
            raw = json.loads(member.guardians_json)
            if isinstance(raw, list):
                for g in raw:
                    name = (g.get("name") or "").strip()
                    if not name:
                        continue
                    phone = (g.get("phone") or g.get("whatsapp") or "").strip() or None
                    guardians.append(
                        {
                            "role": (g.get("relation") or "Responsável").strip(),
                            "name": name,
                            "phone": phone,
                            "email": (g.get("email") or "").strip() or None,
                            "whatsapp": _whatsapp_url(g.get("whatsapp") or phone),
                            "avatar_letter": name[0].upper(),
                        }
                    )
        except (json.JSONDecodeError, TypeError):
            pass
    if not guardians:
        if member.father_name:
            guardians.append(
                {
                    "role": "Pai / responsável",
                    "name": member.father_name,
                    "phone": member.phone,
                    "email": parent_user.email if parent_user else member.email,
                    "whatsapp": _whatsapp_url(member.phone),
                    "avatar_letter": member.father_name[0].upper(),
                }
            )
        if member.mother_name:
            guardians.append(
                {
                    "role": "Mãe / responsável",
                    "name": member.mother_name,
                    "phone": None,
                    "email": None,
                    "whatsapp": None,
                    "avatar_letter": member.mother_name[0].upper(),
                }
            )
    if parent_user and not any(g.get("email") == parent_user.email for g in guardians):
        guardians.append(
            {
                "role": "Conta portal família",
                "name": parent_user.full_name or parent_user.email,
                "phone": None,
                "email": parent_user.email,
                "whatsapp": None,
                "avatar_letter": (parent_user.full_name or parent_user.email)[0].upper(),
            }
        )

    em_phone = member.emergency_contact_phone
    timeline = _timeline_events(member)
    sp_summary = {}
    try:
        from app.specialties_service import member_progress_summary

        sp_summary = member_progress_summary(member, member.clube_id)
    except Exception:
        pass
    addr_parts = [
        member.address_street,
        member.address_number,
        member.address_neighborhood,
        member.address_city,
        member.address_state,
    ]
    profile_address = ", ".join(p for p in addr_parts if p) or None
    if member.address_cep and profile_address:
        profile_address = f"CEP {member.address_cep} — {profile_address}"

    unit_brand = {}
    try:
        from app.members_service import unit_branding_for_member

        def _pu(rel):
            from flask import url_for

            return url_for("uploaded_file", rel_path=rel) if rel else None

        unit_brand = unit_branding_for_member(member, member.clube_id or "", _pu)
    except Exception:
        unit_brand = {}

    return {
        "profile_mode": mode,
        "profile_readonly": mode == "parent",
        "profile_badges": _badges_for_member(
            member, att_rate=att_rate, performance=performance, duques_total=duques_total
        ),
        "profile_level_num": level_num,
        "profile_level_title": level_title,
        "profile_performance": performance,
        "profile_attendance_rate": att_rate if tot else 0,
        "profile_attendance_present": pr,
        "profile_attendance_total": tot,
        "profile_notebook_pct": notebook_pct,
        "profile_duques_total": duques_total,
        "profile_class_label": member.notebook_current or "Classe em progresso",
        "profile_unit": member.unit or "Unidade",
        "profile_entry_date": entry_date,
        "profile_cpf_display": format_cpf_display(member.cpf),
        "profile_guardians": guardians,
        "profile_emergency": {
            "name": member.emergency_contact_name or "—",
            "phone": em_phone or "—",
            "relation": member.emergency_relation or "Contato de emergência",
            "whatsapp": _whatsapp_url(em_phone),
        },
        "profile_timeline": timeline,
        "profile_director_note": (
            "Desbravador dedicado, demonstra espírito de equipe e compromisso com o clube."
            if performance >= 70
            else "Acompanhamento em andamento pela diretoria do clube."
        )
        if mode == "admin"
        else None,
        "profile_meta_goal": f"Evoluir na classe {member.notebook_current}" if member.notebook_current else "Definir classe atual na ficha",
        "profile_specialties_summary": sp_summary if sp_summary else None,
        "profile_unit_logo_url": unit_brand.get("unit_logo_url"),
        "profile_unit_theme": unit_brand.get("unit_theme", "gold"),
        "profile_unit_detail_url": unit_brand.get("unit_detail_url"),
        "profile_unit_role": (member.unit_role or "Desbravador").strip(),
    }
