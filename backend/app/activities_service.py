"""Caderno digital — classes, requisitos, tarefas para casa e progresso."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import (
    ActivityRecord,
    AgendaEvent,
    HW_STATUS_APPROVED,
    HW_STATUS_OPEN,
    HW_STATUS_OVERDUE,
    HW_STATUS_REJECTED,
    HW_STATUS_REVISION,
    HW_STATUS_SUBMITTED,
    HW_STATUS_LABELS,
    HomeworkAssignment,
    HomeworkSubmission,
    Member,
    MemberNotebookEnrollment,
    MemberNotebookRequirementProgress,
    NB_STATUS_COMPLETED,
    NB_STATUS_IN_PROGRESS,
    NB_STATUS_LABELS,
    NB_STATUS_NOT_STARTED,
    NB_STATUS_PENDING,
    NB_STATUS_REJECTED,
    NB_STATUS_REVISION,
    NOTEBOOK_CLASS_ALIASES,
    NotebookClass,
    NotebookClassRequirement,
    NotebookRequirementHistory,
    DEFAULT_NOTEBOOK_CATEGORIES,
    PATHFINDER_CLASS_NAMES,
    User,
)
from app.notebook_catalog import sync_notebook_catalog

CLASS_COLORS = {
    "amigo": "#3b82f6",
    "companheiro": "#22c55e",
    "pesquisador": "#8b5cf6",
    "pioneiro": "#f97316",
    "excursionista": "#6366f1",
    "guia": "#f9bc15",
}

CLASS_ICON = {
    "amigo": "🤝",
    "companheiro": "🌿",
    "pesquisador": "🔍",
    "pioneiro": "🧭",
    "excursionista": "🏔️",
    "guia": "⭐",
}

_ROMAN_SECTION_ORDER = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
}


def _section_sort_key(code: str, *, is_advanced: bool = False, min_order: int = 0) -> tuple:
    """Ordena seções do caderno: I … IX e classe avançada (AV) por último."""
    c = (code or "").strip().upper()
    if is_advanced or c == "AV":
        return (2, 0, min_order)
    return (0, _ROMAN_SECTION_ORDER.get(c, 99), min_order)


def _sort_notebook_sections(sections: list[dict]) -> list[dict]:
    return sorted(
        sections,
        key=lambda s: _section_sort_key(
            s.get("code") or "",
            is_advanced=bool(s.get("is_advanced")),
            min_order=int(s.get("min_sort_order") or 0),
        ),
    )


def _slug(name: str) -> str:
    s = (name or "").strip().lower()
    for old, new in (
        ("ã", "a"),
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("ç", "c"),
    ):
        s = s.replace(old, new)
    return s.replace(" ", "_")


def normalize_class_name(label: str | None) -> str | None:
    if not label:
        return None
    raw = label.strip()
    key = raw.lower()
    if key in NOTEBOOK_CLASS_ALIASES:
        return NOTEBOOK_CLASS_ALIASES[key]
    for name in PATHFINDER_CLASS_NAMES:
        if name.lower() == key:
            return name
    return raw if raw in PATHFINDER_CLASS_NAMES else None


CIRCLED_NUMBERS = ("", "❶", "❷", "❸", "❹", "❺", "❻", "❼", "❽", "❾", "❿",
                   "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳")


def circled_number(n: int) -> str:
    if 1 <= n < len(CIRCLED_NUMBERS):
        return CIRCLED_NUMBERS[n]
    return f"#{n}"


def _base_requirements(class_name: str) -> list[dict]:
    """Requisitos representativos por classe (estrutura escalável)."""
    common = [
        {
            "title": "Participar de devocional semanal",
            "description": "Presença e participação ativa no devocional do clube.",
            "category": "Espiritual",
        },
        {
            "title": "Memorizar versículo bíblico",
            "description": "Recitar o versículo indicado pelo conselheiro em reunião.",
            "category": "Espiritual",
        },
        {
            "title": "Atividade física regular",
            "description": "Registrar exercícios ou desafio físico por 4 semanas.",
            "category": "Físico",
        },
        {
            "title": "Projeto de serviço comunitário",
            "description": "Participar de ação de serviço aprovada pela diretoria.",
            "category": "Social",
        },
        {
            "title": "Relatório de leitura",
            "description": "Entregar resumo de leitura ou estudo indicado.",
            "category": "Intelectual",
        },
        {
            "title": "Atividade de natureza",
            "description": "Completar trilha, observação ou conservação ambiental.",
            "category": "Natureza",
        },
        {
            "title": "Habilidade profissional",
            "description": "Demonstrar aprendizado em ofício ou habilidade prática.",
            "category": "Profissional",
        },
        {
            "title": "Acampamento ou excursão",
            "description": "Participar de atividade ao ar livre com a unidade.",
            "category": "Natureza",
        },
    ]
    extra = {
        "Amigo": [
            {
                "title": "Conhecer história dos Desbravadores",
                "description": "Apresentar oralmente o que aprendeu sobre o movimento.",
                "category": "Intelectual",
            },
            {
                "title": "Primeiros socorros básico",
                "description": "Demonstrar cuidados simples em ferimentos leves.",
                "category": "Profissional",
            },
        ],
        "Companheiro": [
            {
                "title": "Nós e amarras essenciais",
                "description": "Demonstrar nó direito, lais de guia e bowline.",
                "category": "Profissional",
            },
            {
                "title": "Estudo da natureza local",
                "description": "Identificar espécies de plantas ou animais da região.",
                "category": "Natureza",
            },
        ],
        "Pesquisador": [
            {
                "title": "Projeto de pesquisa",
                "description": "Elaborar relatório sobre tema aprovado pelo conselheiro.",
                "category": "Intelectual",
            },
            {
                "title": "Liderança em pequeno grupo",
                "description": "Conduzir dinâmica ou atividade para desbravadores mais novos.",
                "category": "Social",
            },
        ],
        "Pioneiro": [
            {
                "title": "Planejamento de acampamento",
                "description": "Ajudar na organização logística de acampamento.",
                "category": "Profissional",
            },
            {
                "title": "Evangelismo criativo",
                "description": "Participar de ação evangelística do clube.",
                "category": "Espiritual",
            },
        ],
        "Excursionista": [
            {
                "title": "Trilha de longa duração",
                "description": "Completar caminhada ou trilha com equipamento adequado.",
                "category": "Físico",
            },
            {
                "title": "Sobrevivência outdoor",
                "description": "Demonstrar habilidades de acampamento avançado.",
                "category": "Natureza",
            },
        ],
        "Guia": [
            {
                "title": "Mentoria de desbravadores",
                "description": "Acompanhar pelo menos um desbravador mais novo por 30 dias.",
                "category": "Social",
            },
            {
                "title": "Projeto de liderança",
                "description": "Liderar iniciativa aprovada pela diretoria do clube.",
                "category": "Profissional",
            },
        ],
    }
    return common + extra.get(class_name, [])


DEFAULT_CLASS_SEED = [
    {"name": name, "slug": _slug(name), "color_hex": CLASS_COLORS.get(_slug(name), "#3b82f6")}
    for name in PATHFINDER_CLASS_NAMES
]


def ensure_default_classes() -> None:
    """Cadastra classes e requisitos oficiais (catálogo completo)."""
    sync_notebook_catalog()


def class_by_name(name: str | None) -> NotebookClass | None:
    norm = normalize_class_name(name)
    if not norm:
        return None
    slug = _slug(norm)
    return NotebookClass.query.filter_by(slug=slug, active=True).first()


def _requirement_ids(class_id: int) -> list[int]:
    return [
        r.id
        for r in NotebookClassRequirement.query.filter_by(class_id=class_id)
        .order_by(NotebookClassRequirement.sort_order)
        .all()
    ]


def _ensure_progress_rows(enrollment: MemberNotebookEnrollment) -> list[MemberNotebookRequirementProgress]:
    req_ids = _requirement_ids(enrollment.class_id)
    existing = {p.requirement_id: p for p in enrollment.requirement_progress.all()}
    for rid in req_ids:
        if rid not in existing:
            row = MemberNotebookRequirementProgress(
                enrollment_id=enrollment.id,
                requirement_id=rid,
                status=NB_STATUS_NOT_STARTED,
            )
            db.session.add(row)
            existing[rid] = row
    db.session.flush()
    return list(existing.values())


def recalc_enrollment_progress(enrollment: MemberNotebookEnrollment) -> MemberNotebookEnrollment:
    rows = _ensure_progress_rows(enrollment)
    total = len(rows)
    done = sum(1 for r in rows if r.status == NB_STATUS_COMPLETED)
    pending = sum(1 for r in rows if r.status == NB_STATUS_PENDING)
    pct = round(100 * done / total) if total else 0
    enrollment.progress_percent = pct
    enrollment.updated_at = datetime.utcnow()

    if total and done == total:
        enrollment.status = NB_STATUS_COMPLETED
        enrollment.completed_at = enrollment.completed_at or datetime.utcnow()
    elif pending > 0 or done > 0:
        enrollment.status = NB_STATUS_IN_PROGRESS
    else:
        enrollment.status = NB_STATUS_IN_PROGRESS

    member = enrollment.member
    if member:
        member.overall_performance = member.computed_overall_performance()
    return enrollment


def get_active_enrollment(member: Member) -> MemberNotebookEnrollment | None:
    enr = (
        MemberNotebookEnrollment.query.filter_by(member_id=member.id, is_active=True)
        .order_by(MemberNotebookEnrollment.updated_at.desc())
        .first()
    )
    if enr:
        return enr
    nc = class_by_name(member.notebook_current)
    if not nc:
        return None
    return (
        MemberNotebookEnrollment.query.filter_by(member_id=member.id, class_id=nc.id)
        .first()
    )


def ensure_member_notebook(member: Member, *, user_id: int | None = None) -> MemberNotebookEnrollment | None:
    """Gera ou atualiza caderno digital conforme classe atual do desbravador."""
    ensure_default_classes()
    norm = normalize_class_name(member.notebook_current)
    if not norm:
        return None
    member.notebook_current = norm
    nc = class_by_name(norm)
    if not nc:
        return None

    MemberNotebookEnrollment.query.filter_by(member_id=member.id, is_active=True).update(
        {MemberNotebookEnrollment.is_active: False}, synchronize_session=False
    )

    enr = MemberNotebookEnrollment.query.filter_by(member_id=member.id, class_id=nc.id).first()
    if not enr:
        enr = MemberNotebookEnrollment(
            member_id=member.id,
            class_id=nc.id,
            status=NB_STATUS_IN_PROGRESS,
            is_active=True,
        )
        db.session.add(enr)
        db.session.flush()
    else:
        enr.is_active = True
        enr.updated_at = datetime.utcnow()

    _ensure_progress_rows(enr)
    recalc_enrollment_progress(enr)
    return enr


def _log_requirement_change(
    row: MemberNotebookRequirementProgress,
    *,
    old_status: str,
    new_status: str,
    user_id: int | None,
    note: str | None = None,
) -> None:
    db.session.add(
        NotebookRequirementHistory(
            progress_id=row.id,
            action="status_change",
            old_status=old_status,
            new_status=new_status,
            note=note,
            performed_by_id=user_id,
        )
    )


def set_requirement_status(
    progress_id: int,
    status: str,
    *,
    user_id: int | None = None,
    notes: str | None = None,
    review_note: str | None = None,
    sign_instructor: bool = False,
) -> MemberNotebookRequirementProgress | None:
    row = db.session.get(MemberNotebookRequirementProgress, progress_id)
    if not row:
        return None
    allowed = {
        NB_STATUS_NOT_STARTED,
        NB_STATUS_IN_PROGRESS,
        NB_STATUS_PENDING,
        NB_STATUS_COMPLETED,
        NB_STATUS_REJECTED,
        NB_STATUS_REVISION,
    }
    if status not in allowed:
        return None

    old_status = row.status
    row.status = status
    row.notes = notes if notes is not None else row.notes
    row.review_note = review_note if review_note is not None else row.review_note
    row.updated_at = datetime.utcnow()

    if status == NB_STATUS_COMPLETED:
        row.completed_at = datetime.utcnow()
        row.completion_date = date.today()
        row.approved_by_id = user_id
        row.approved_at = datetime.utcnow()
        row.instructor_signed = True
        row.instructor_signed_at = datetime.utcnow()
    elif status in (NB_STATUS_NOT_STARTED, NB_STATUS_IN_PROGRESS):
        row.completed_at = None
        row.completion_date = None
        row.approved_by_id = None
        row.approved_at = None
        row.instructor_signed = False
        row.instructor_signed_at = None
    elif status == NB_STATUS_PENDING:
        row.instructor_signed = False
        row.instructor_signed_at = None

    if sign_instructor and status == NB_STATUS_COMPLETED:
        row.instructor_signed = True
        row.instructor_signed_at = datetime.utcnow()

    _log_requirement_change(row, old_status=old_status, new_status=status, user_id=user_id, note=review_note)

    enr = row.enrollment
    if enr:
        recalc_enrollment_progress(enr)
        _sync_activity_record(enr, row)
    return row


def _sync_activity_record(
    enrollment: MemberNotebookEnrollment,
    progress: MemberNotebookRequirementProgress,
) -> None:
    """Mantém ActivityRecord alinhado a requisitos concluídos."""
    req = progress.requirement
    member = enrollment.member
    if not req or not member:
        return
    title = f"{req.title} ({enrollment.notebook_class.name if enrollment.notebook_class else 'Caderno'})"
    rec = (
        ActivityRecord.query.filter_by(member_id=member.id, title=title)
        .filter(ActivityRecord.category == "Caderno")
        .first()
    )
    if progress.status == NB_STATUS_COMPLETED:
        if not rec:
            rec = ActivityRecord(
                member_id=member.id,
                title=title,
                category="Caderno",
                notes=req.description,
                progress_percent=100,
                completed=True,
            )
            db.session.add(rec)
        else:
            rec.completed = True
            rec.progress_percent = 100
    elif rec and progress.status in (NB_STATUS_REJECTED, NB_STATUS_REVISION, NB_STATUS_NOT_STARTED):
        if progress.status == NB_STATUS_NOT_STARTED:
            db.session.delete(rec)
        else:
            rec.completed = False
            rec.progress_percent = 50 if progress.status == NB_STATUS_REVISION else 0


def member_notebook_summary(member: Member) -> dict:
    enr = get_active_enrollment(member)
    if not enr:
        ensure_member_notebook(member)
        enr = get_active_enrollment(member)

    total_req = 0
    done = 0
    pending = 0
    in_progress = 0
    class_name = member.notebook_current or "—"
    class_color = "#64748b"
    pct = 0

    if enr:
        rows = _ensure_progress_rows(enr)
        total_req = len(rows)
        done = sum(1 for r in rows if r.status == NB_STATUS_COMPLETED)
        pending = sum(1 for r in rows if r.status == NB_STATUS_PENDING)
        in_progress = sum(1 for r in rows if r.status == NB_STATUS_IN_PROGRESS)
        pct = enr.progress_percent
        if enr.notebook_class:
            class_name = enr.notebook_class.name
            class_color = enr.notebook_class.color_hex or class_color

    if total_req == 0:
        status_key = "not_started"
        status_label = "Sem caderno"
    elif done == total_req:
        status_key = "completed"
        status_label = "Concluído"
    elif pending > 0:
        status_key = "pending"
        status_label = "Aguardando avaliação"
    elif in_progress > 0 or done > 0:
        status_key = "in_progress"
        status_label = "Em andamento"
    else:
        status_key = "not_started"
        status_label = "Não iniciado"

    return {
        "enrollment_id": enr.id if enr else None,
        "class_name": class_name,
        "class_color": class_color,
        "progress_percent": pct,
        "total_requirements": total_req,
        "completed_count": done,
        "pending_count": pending,
        "in_progress_count": in_progress,
        "status_key": status_key,
        "status_label": status_label,
    }


def club_dashboard_stats(clube_id: str) -> dict:
    ensure_default_classes()
    members = Member.query.filter_by(clube_id=clube_id).all()
    member_ids = [m.id for m in members]
    active_classes = NotebookClass.query.filter_by(active=True).count()

    if not member_ids:
        return {
            "total_members": 0,
            "active_classes": active_classes,
            "completed_total": 0,
            "requirements_total": 0,
            "pending_review": 0,
            "homework_active": 0,
            "club_progress_pct": 0,
        }

    progress_rows = (
        MemberNotebookRequirementProgress.query.join(MemberNotebookEnrollment)
        .filter(MemberNotebookEnrollment.member_id.in_(member_ids))
        .all()
    )
    total_req = len(progress_rows)
    completed = sum(1 for r in progress_rows if r.status == NB_STATUS_COMPLETED)
    pending_review = sum(1 for r in progress_rows if r.status == NB_STATUS_PENDING)

    today = date.today()
    homework_active = HomeworkAssignment.query.filter(
        HomeworkAssignment.clube_id == clube_id,
        HomeworkAssignment.active.is_(True),
    ).count()

    overdue_hw = (
        HomeworkSubmission.query.join(HomeworkAssignment)
        .filter(
            HomeworkSubmission.member_id.in_(member_ids),
            HomeworkSubmission.status == HW_STATUS_SUBMITTED,
            HomeworkAssignment.due_date < today,
        )
        .count()
    )

    club_pct = round(100 * completed / total_req) if total_req else 0

    return {
        "total_members": len(member_ids),
        "active_classes": active_classes,
        "completed_total": completed,
        "requirements_total": total_req,
        "pending_review": pending_review,
        "homework_active": homework_active,
        "club_progress_pct": club_pct,
        "overdue_submissions": overdue_hw,
    }


def serialize_member_table_row(member: Member, *, photo_url: str | None = None) -> dict:
    summary = member_notebook_summary(member)
    handle = (member.full_name or "").lower().replace(" ", ".")[:24]
    nc = class_by_name(member.notebook_current)
    return {
        "id": member.id,
        "full_name": member.full_name,
        "handle": f"@{handle}" if handle else "",
        "unit": member.unit or "—",
        "photo_url": photo_url,
        "initial": (member.full_name or "?")[0].upper(),
        "class_name": summary["class_name"],
        "class_slug": nc.slug if nc else _slug(summary["class_name"]),
        "class_color": summary["class_color"],
        "progress_percent": summary["progress_percent"],
        "completed_count": summary["completed_count"],
        "total_requirements": summary["total_requirements"],
        "pending_count": summary["pending_count"],
        "status_key": summary["status_key"],
        "status_label": summary["status_label"],
        "enrollment_id": summary["enrollment_id"],
    }


def class_overview(clube_id: str) -> list[dict]:
    ensure_default_classes()
    members = Member.query.filter_by(clube_id=clube_id).all()
    by_class: dict[int, list[Member]] = {}
    for m in members:
        enr = get_active_enrollment(m)
        if not enr:
            ensure_member_notebook(m)
            enr = get_active_enrollment(m)
        if enr:
            by_class.setdefault(enr.class_id, []).append(m)

    out = []
    for nc in NotebookClass.query.filter_by(active=True).order_by(NotebookClass.sort_order).all():
        group = by_class.get(nc.id, [])
        n = len(group)
        if not n:
            out.append(
                {
                    "slug": nc.slug,
                    "name": nc.name,
                    "color_hex": nc.color_hex,
                    "icon": CLASS_ICON.get(nc.slug, "📘"),
                    "member_count": 0,
                    "progress_pct": 0,
                    "completed": 0,
                    "total": nc.requirements.count(),
                }
            )
            continue
        pcts = []
        done_sum = 0
        total_sum = 0
        for m in group:
            s = member_notebook_summary(m)
            pcts.append(s["progress_percent"])
            done_sum += s["completed_count"]
            total_sum += s["total_requirements"]
        out.append(
            {
                "slug": nc.slug,
                "name": nc.name,
                "color_hex": nc.color_hex,
                "icon": CLASS_ICON.get(nc.slug, "📘"),
                "member_count": n,
                "progress_pct": round(sum(pcts) / len(pcts)) if pcts else 0,
                "completed": done_sum,
                "total": total_sum or nc.requirements.count(),
            }
        )
    return out


def pending_review_sidebar(clube_id: str, limit: int = 8) -> list[dict]:
    rows = (
        MemberNotebookRequirementProgress.query.join(MemberNotebookEnrollment)
        .join(Member)
        .join(NotebookClassRequirement)
        .filter(
            Member.clube_id == clube_id,
            MemberNotebookRequirementProgress.status == NB_STATUS_PENDING,
        )
        .order_by(MemberNotebookRequirementProgress.updated_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for row in rows:
        req = row.requirement
        enr = row.enrollment
        m = enr.member if enr else None
        if not m or not req:
            continue
        out.append(
            {
                "progress_id": row.id,
                "member_id": m.id,
                "member_name": m.full_name,
                "title": req.title,
                "evidence_type": "Requisito",
                "submitted_at": row.updated_at,
                "ago": _ago(row.updated_at),
            }
        )

    hw_rows = (
        HomeworkSubmission.query.join(HomeworkAssignment)
        .join(Member)
        .filter(
            Member.clube_id == clube_id,
            HomeworkSubmission.status == HW_STATUS_SUBMITTED,
        )
        .order_by(HomeworkSubmission.submitted_at.desc())
        .limit(limit)
        .all()
    )
    for sub in hw_rows:
        if len(out) >= limit:
            break
        out.append(
            {
                "progress_id": sub.id,
                "member_id": sub.member_id,
                "member_name": sub.member.full_name if sub.member else "—",
                "title": sub.assignment.title if sub.assignment else "Tarefa",
                "evidence_type": sub.evidence_type or "Envio",
                "submitted_at": sub.submitted_at,
                "ago": _ago(sub.submitted_at),
                "kind": "homework",
            }
        )
    return out[:limit]


def upcoming_activities(clube_id: str, limit: int = 6) -> list[dict]:
    today = date.today()
    events = (
        AgendaEvent.query.filter(
            AgendaEvent.clube_id == clube_id,
            AgendaEvent.event_date >= today,
        )
        .order_by(AgendaEvent.event_date.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "title": ev.title,
            "date_label": ev.event_date.strftime("%d/%m/%Y") if ev.event_date else "",
            "time_label": ev.event_time or "",
            "category": ev.category or "evento",
        }
        for ev in events
    ]


def _ago(dt: datetime | None) -> str:
    if not dt:
        return ""
    delta = datetime.utcnow() - dt
    if delta.days > 0:
        return f"há {delta.days}d"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"há {hours}h"
    return "agora"


def _serialize_progress_row(row: MemberNotebookRequirementProgress) -> dict:
    req = row.requirement
    approver = None
    if row.approved_by_id:
        u = db.session.get(User, row.approved_by_id)
        approver = u.full_name if u else None
    num = req.req_number if req else 0
    return {
        "progress_id": row.id,
        "requirement_id": req.id if req else None,
        "number": num,
        "number_label": circled_number(num),
        "title": req.title if req else "",
        "description": (req.description or "") if req else "",
        "section_code": req.section_code if req else "",
        "section_title": req.section_title if req else "",
        "is_optional": bool(req.is_optional) if req else False,
        "status": row.status,
        "status_label": NB_STATUS_LABELS.get(row.status, row.status),
        "notes": row.notes or "",
        "review_note": row.review_note or "",
        "completion_date": row.completion_date,
        "completed_at": row.completed_at,
        "instructor_signed": row.instructor_signed,
        "approver": approver,
    }


def build_member_notebook_detail(
    member: Member,
    *,
    photo_url: str | None = None,
    section_filter: str = "",
) -> dict:
    ensure_member_notebook(member)
    enr = get_active_enrollment(member)
    if not enr:
        return {
            "member": member,
            "photo_url": photo_url,
            "enrollment": None,
            "sections": [],
            "requirements": [],
        }

    nc = enr.notebook_class
    rows = _ensure_progress_rows(enr)
    by_section: dict[str, dict] = {}
    for row in rows:
        req = row.requirement
        if not req:
            continue
        key = f"{req.section_code}|{req.section_title}"
        if section_filter and req.section_code != section_filter:
            continue
        sec = by_section.setdefault(
            key,
            {
                "code": req.section_code,
                "title": req.section_title,
                "is_advanced": req.is_advanced,
                "min_sort_order": req.sort_order,
                "requirements": [],
            },
        )
        sec["min_sort_order"] = min(sec["min_sort_order"], req.sort_order)
        sec["requirements"].append(_serialize_progress_row(row))

    sections = []
    for sec in _sort_notebook_sections(list(by_section.values())):
        reqs = sec["requirements"]
        total = len(reqs)
        done = sum(1 for i in reqs if i["status"] == NB_STATUS_COMPLETED)
        sec["total"] = total
        sec["done"] = done
        sec["pct"] = round(100 * done / total) if total else 0
        sections.append(sec)

    requirements_flat = [item for sec in sections for item in sec["requirements"]]

    return {
        "member": member,
        "photo_url": photo_url,
        "enrollment": enr,
        "class_name": nc.name if nc else member.notebook_current,
        "class_slug": nc.slug if nc else "",
        "class_color": nc.color_hex if nc else "#3b82f6",
        "min_age": nc.min_age if nc else None,
        "progress_percent": enr.progress_percent,
        "sections": sections,
        "requirements": requirements_flat,
        "summary": member_notebook_summary(member),
    }


def build_class_catalog_view(
    class_slug: str,
    clube_id: str,
    *,
    member_id: int | None = None,
    photo_url_builder=None,
) -> dict | None:
    """Visão do caderno por classe (catálogo + progresso opcional de um membro)."""
    ensure_default_classes()
    nc = NotebookClass.query.filter_by(slug=class_slug, active=True).first()
    if not nc:
        return None

    reqs = (
        NotebookClassRequirement.query.filter_by(class_id=nc.id)
        .order_by(NotebookClassRequirement.sort_order)
        .all()
    )
    progress_map: dict[int, MemberNotebookRequirementProgress] = {}
    member = None
    enr = None
    if member_id:
        member = db.session.get(Member, member_id)
        if member and member.clube_id == clube_id:
            ensure_member_notebook(member)
            enr = MemberNotebookEnrollment.query.filter_by(
                member_id=member.id, class_id=nc.id
            ).first()
            if enr:
                for p in _ensure_progress_rows(enr):
                    progress_map[p.requirement_id] = p

    by_section: dict[str, dict] = {}
    for req in reqs:
        key = f"{req.section_code}|{req.section_title}"
        sec = by_section.setdefault(
            key,
            {
                "code": req.section_code,
                "title": req.section_title,
                "is_advanced": req.is_advanced,
                "min_sort_order": req.sort_order,
                "requirements": [],
            },
        )
        sec["min_sort_order"] = min(sec["min_sort_order"], req.sort_order)
        prog = progress_map.get(req.id)
        item = {
            "requirement_id": req.id,
            "progress_id": prog.id if prog else None,
            "number": req.req_number,
            "number_label": circled_number(req.req_number),
            "title": req.title,
            "description": req.description or "",
            "is_optional": req.is_optional,
            "status": prog.status if prog else NB_STATUS_NOT_STARTED,
            "status_label": NB_STATUS_LABELS.get(
                prog.status if prog else NB_STATUS_NOT_STARTED,
                NB_STATUS_NOT_STARTED,
            ),
            "completion_date": prog.completion_date if prog else None,
            "instructor_signed": prog.instructor_signed if prog else False,
            "approver": (
                prog.approved_by.full_name
                if prog and prog.approved_by
                else None
            ),
        }
        sec["requirements"].append(item)

    sections = []
    for sec in _sort_notebook_sections(list(by_section.values())):
        total = len(sec["requirements"])
        done = sum(1 for i in sec["requirements"] if i["status"] == NB_STATUS_COMPLETED)
        sec["total"] = total
        sec["done"] = done
        sec["pct"] = round(100 * done / total) if total else 0
        sections.append(sec)

    n_members = (
        MemberNotebookEnrollment.query.join(Member)
        .filter(Member.clube_id == clube_id, MemberNotebookEnrollment.class_id == nc.id)
        .count()
    )

    return {
        "class": nc,
        "slug": nc.slug,
        "name": nc.name,
        "color_hex": nc.color_hex,
        "min_age": nc.min_age,
        "advanced_title": nc.advanced_title,
        "total_requirements": len(reqs),
        "member_count": n_members,
        "sections": sections,
        "member": member,
        "enrollment": enr,
        "progress_percent": enr.progress_percent if enr else 0,
    }


def build_class_requirements_for_homework(class_slug: str) -> dict | None:
    """Árvore de seções e requisitos oficiais para o modal de tarefa para casa."""
    nc = NotebookClass.query.filter_by(slug=class_slug, active=True).first()
    if not nc:
        return None
    reqs = (
        NotebookClassRequirement.query.filter_by(class_id=nc.id)
        .order_by(
            NotebookClassRequirement.is_advanced.asc(),
            NotebookClassRequirement.section_code.asc(),
            NotebookClassRequirement.sort_order.asc(),
            NotebookClassRequirement.req_number.asc(),
        )
        .all()
    )
    by_section: dict[str, dict] = {}
    for req in reqs:
        key = f"{req.is_advanced}|{req.section_code}|{req.section_title}"
        if key not in by_section:
            by_section[key] = {
                "code": req.section_code,
                "title": req.section_title,
                "is_advanced": req.is_advanced,
                "requirements": [],
            }
        by_section[key]["requirements"].append(
            {
                "id": req.id,
                "number_label": circled_number(req.req_number),
                "title": req.title,
                "description": (req.description or "")[:500],
                "is_optional": req.is_optional,
                "optional_group": req.optional_group,
            }
        )
    sections = sorted(
        by_section.values(),
        key=lambda s: (s["is_advanced"], s["code"]),
    )
    return {
        "class_slug": nc.slug,
        "class_name": nc.name,
        "color_hex": nc.color_hex or CLASS_COLORS.get(nc.slug, "#3b82f6"),
        "sections": sections,
    }


def homework_list(clube_id: str, *, include_inactive: bool = False) -> list[dict]:
    q = HomeworkAssignment.query.filter_by(clube_id=clube_id)
    if not include_inactive:
        q = q.filter_by(active=True)
    rows = q.order_by(HomeworkAssignment.created_at.desc()).all()
    today = date.today()
    out = []
    for hw in rows:
        n_sub = hw.submissions.count()
        n_done = hw.submissions.filter_by(status=HW_STATUS_APPROVED).count()
        overdue = bool(hw.due_date and hw.due_date < today)
        req = hw.requirement
        section_label = ""
        if req:
            section_label = f"{req.section_code}. {req.section_title}"
        out.append(
            {
                "id": hw.id,
                "title": hw.title,
                "description": (hw.description or "")[:200],
                "due_date": hw.due_date,
                "due_label": hw.due_date.strftime("%d/%m/%Y") if hw.due_date else "Sem prazo",
                "class_slug": hw.class_slug,
                "class_name": req.notebook_class.name if req and req.notebook_class else hw.class_slug,
                "category": hw.category or section_label or "Geral",
                "section_label": section_label,
                "requirement_id": hw.requirement_id,
                "submissions_count": n_sub,
                "approved_count": n_done,
                "overdue": overdue,
                "active": hw.active,
                "created_at": hw.created_at,
            }
        )
    return out


def _resolve_homework_targets(
    clube_id: str,
    *,
    class_slug: str | None,
    target_units: list[str] | None,
    target_member_ids: list[int] | None,
) -> list[Member]:
    q = Member.query.filter_by(clube_id=clube_id)
    if target_member_ids:
        return q.filter(Member.id.in_(target_member_ids)).all()
    if target_units:
        return q.filter(Member.unit.in_(target_units)).all()
    if class_slug:
        nc = NotebookClass.query.filter_by(slug=class_slug).first()
        if nc:
            name = nc.name
            return [m for m in q.all() if normalize_class_name(m.notebook_current) == name]
    return q.all()


def create_homework(
    clube_id: str,
    *,
    requirement_id: int,
    description: str | None,
    due_date: date | None,
    attachment_filename: str | None,
    created_by_id: int | None,
    target_units: list[str] | None = None,
    target_member_ids: list[int] | None = None,
) -> HomeworkAssignment:
    """Cria tarefa para casa a partir de um requisito oficial do catálogo."""
    import json

    req = db.session.get(NotebookClassRequirement, requirement_id)
    if not req:
        raise ValueError("Requisito não encontrado.")
    nc = req.notebook_class
    if not nc:
        raise ValueError("Classe do requisito inválida.")

    hw = HomeworkAssignment(
        clube_id=clube_id,
        requirement_id=req.id,
        title=req.title,
        description=description or req.description,
        due_date=due_date,
        class_slug=nc.slug,
        category=f"{req.section_code}. {req.section_title}",
        target_units_json=json.dumps(target_units) if target_units else None,
        target_members_json=json.dumps(target_member_ids) if target_member_ids else None,
        attachment_filename=attachment_filename,
        created_by_id=created_by_id,
        active=True,
    )
    db.session.add(hw)
    db.session.flush()

    targets = _resolve_homework_targets(
        clube_id,
        class_slug=nc.slug,
        target_units=target_units,
        target_member_ids=target_member_ids,
    )
    for member in targets:
        ensure_member_notebook(member)
        enr = (
            MemberNotebookEnrollment.query.filter_by(
                member_id=member.id, class_id=nc.id, is_active=True
            ).first()
        )
        if not enr:
            continue
        prog = MemberNotebookRequirementProgress.query.filter_by(
            enrollment_id=enr.id, requirement_id=req.id
        ).first()
        if prog and prog.status == NB_STATUS_NOT_STARTED:
            set_requirement_status(
                prog.id,
                NB_STATUS_IN_PROGRESS,
                user_id=created_by_id,
                notes="Tarefa para casa atribuída pela diretoria.",
            )
    return hw


def review_homework_submission(
    submission_id: int,
    action: str,
    *,
    reviewer_id: int | None,
    review_note: str | None = None,
) -> HomeworkSubmission | None:
    sub = db.session.get(HomeworkSubmission, submission_id)
    if not sub:
        return None
    mapping = {
        "approve": HW_STATUS_APPROVED,
        "reject": HW_STATUS_REJECTED,
        "revision": HW_STATUS_REVISION,
    }
    status = mapping.get(action)
    if not status:
        return None
    sub.status = status
    sub.reviewed_by_id = reviewer_id
    sub.reviewed_at = datetime.utcnow()
    sub.review_note = review_note
    return sub


def build_activities_dashboard(
    clube_id: str,
    *,
    photo_url_builder,
    tab: str = "desbravadores",
    q: str = "",
    class_filter: str = "",
    status_filter: str = "",
    sort: str = "progress",
    page: int = 1,
    per_page: int = 15,
    member_id: int | None = None,
    class_slug: str = "amigo",
) -> dict:
    ensure_default_classes()
    stats = club_dashboard_stats(clube_id)

    query = Member.query.filter_by(clube_id=clube_id)
    if q:
        query = query.filter(Member.full_name.ilike(f"%{q.strip()}%"))

    members = query.order_by(Member.full_name).all()
    rows = []
    for m in members:
        summary = member_notebook_summary(m)
        if class_filter and summary["class_name"].lower() != class_filter.lower():
            continue
        if status_filter == "completed" and summary["status_key"] != "completed":
            continue
        if status_filter == "pending" and summary["pending_count"] == 0:
            continue
        if status_filter == "in_progress" and summary["status_key"] not in ("in_progress", "pending"):
            continue
        pu = photo_url_builder(m.photo_filename) if m.photo_filename else None
        rows.append(serialize_member_table_row(m, photo_url=pu))

    if sort == "name":
        rows.sort(key=lambda r: r["full_name"])
    elif sort == "pending":
        rows.sort(key=lambda r: r["pending_count"], reverse=True)
    else:
        rows.sort(key=lambda r: r["progress_percent"], reverse=True)

    total_pages = max(1, (len(rows) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_rows = rows[start : start + per_page]

    detail = None
    if member_id:
        m = db.session.get(Member, member_id)
        if m and m.clube_id == clube_id:
            pu = photo_url_builder(m.photo_filename) if m.photo_filename else None
            detail = build_member_notebook_detail(m, photo_url=pu)

    classes = []
    class_tabs = []
    for c in NotebookClass.query.filter_by(active=True).order_by(NotebookClass.sort_order).all():
        n_req = c.requirements.count()
        classes.append({"slug": c.slug, "name": c.name, "color_hex": c.color_hex})
        class_tabs.append(
            {
                "slug": c.slug,
                "name": c.name,
                "color_hex": c.color_hex,
                "icon": CLASS_ICON.get(c.slug, "📘"),
                "requirements_count": n_req,
            }
        )

    active_slug = class_slug or "amigo"
    if detail and detail.get("class_slug"):
        active_slug = detail["class_slug"]
    class_view = build_class_catalog_view(
        active_slug,
        clube_id,
        member_id=member_id,
        photo_url_builder=photo_url_builder,
    )

    units = sorted({m.unit for m in members if m.unit})
    member_options = [
        {"id": m.id, "full_name": m.full_name, "unit": m.unit or "—"}
        for m in sorted(members, key=lambda x: x.full_name)
    ]

    return {
        "stats": stats,
        "tab": tab,
        "members": page_rows,
        "member_options": member_options,
        "members_total": len(rows),
        "page": page,
        "total_pages": total_pages,
        "selected_member_id": member_id if detail else None,
        "detail": detail,
        "classes": classes,
        "class_tabs": class_tabs,
        "active_class_slug": active_slug,
        "class_view": class_view,
        "units": units,
        "class_overview": class_overview(clube_id),
        "pending_sidebar": pending_review_sidebar(clube_id),
        "upcoming": upcoming_activities(clube_id),
        "homework_rows": homework_list(clube_id),
        "class_options": list(PATHFINDER_CLASS_NAMES),
        "categories": sorted(
            {
                c
                for nc in NotebookClass.query.filter_by(active=True).all()
                for c in {r.category for r in nc.requirements.all()}
            }
        )
        or list(DEFAULT_NOTEBOOK_CATEGORIES),
    }


_PARENT_STATUS_META = {
    "catalog": {
        "label": "No caderno",
        "css": "pa-status--catalog",
        "action": "Ver detalhes",
        "action_css": "pa-btn--outline",
    },
    "homework": {
        "label": "Tarefa para casa",
        "css": "pa-status--homework",
        "action": "Enviar evidência",
        "action_css": "pa-btn--primary",
    },
    "pending_review": {
        "label": "Aguardando aprovação",
        "css": "pa-status--review",
        "action": "Ver detalhes",
        "action_css": "pa-btn--outline",
    },
    "completed": {
        "label": "Concluída",
        "css": "pa-status--done",
        "action": "Ver certificado",
        "action_css": "pa-btn--outline",
    },
    "rejected": {
        "label": "Correção solicitada",
        "css": "pa-status--rejected",
        "action": "Enviar evidência",
        "action_css": "pa-btn--primary",
    },
    "expired": {
        "label": "Prazo expirado",
        "css": "pa-status--expired",
        "action": "Ver detalhes",
        "action_css": "pa-btn--outline",
    },
}

_MEDAL_MILESTONES = (
    (100, "Medalha de Honra", "gold", "🏅"),
    (75, "Medalha Ouro", "gold", "🥇"),
    (50, "Medalha Prata", "silver", "🥈"),
    (25, "Medalha Bronze", "bronze", "🥉"),
)


def _section_filter_slug(code: str) -> str:
    return f"sec-{(code or 'gerais').strip().upper()}"


def _section_filter_label(code: str, title: str) -> str:
    c = (code or "").strip().upper()
    if c == "AV":
        return f"AV. {title}"
    return f"{c}. {title}" if c else title


def _requirement_points(req: NotebookClassRequirement | None) -> int:
    if not req:
        return 10
    return 15 if req.is_advanced else 10


def _resolve_parent_card_status(
    nb_status: str,
    *,
    hw_assigned: bool,
    hw_status: str | None = None,
    overdue: bool = False,
) -> str:
    """Pais/desbravadores não iniciam atividades — só enviam quando há tarefa para casa."""
    if hw_status == HW_STATUS_APPROVED or nb_status == NB_STATUS_COMPLETED:
        return "completed"
    if not hw_assigned:
        return "catalog"
    if overdue and hw_status not in (HW_STATUS_APPROVED, HW_STATUS_SUBMITTED):
        return "expired"
    if hw_status == HW_STATUS_SUBMITTED or nb_status == NB_STATUS_PENDING:
        return "pending_review"
    if hw_status == HW_STATUS_REJECTED or nb_status == NB_STATUS_REJECTED:
        return "rejected"
    if hw_status in (HW_STATUS_REVISION,) or nb_status == NB_STATUS_REVISION:
        return "homework"
    return "homework"


def _next_medal_goal(done: int, total: int) -> dict:
    if total <= 0:
        return {
            "label": "Medalha Bronze",
            "tier": "bronze",
            "icon": "🥉",
            "remaining": 0,
            "target_pct": 25,
            "motivation": "Complete os requisitos do caderno para conquistar sua primeira medalha.",
        }
    pct = round(100 * done / total)
    for threshold, label, tier, icon in _MEDAL_MILESTONES:
        if pct < threshold:
            need = max(0, round(total * threshold / 100) - done)
            return {
                "label": label,
                "tier": tier,
                "icon": icon,
                "remaining": need,
                "target_pct": threshold,
                "motivation": f"Faltam {need} atividades para a próxima conquista.",
            }
    return {
        "label": "Classe concluída",
        "tier": "gold",
        "icon": "🏅",
        "remaining": 0,
        "target_pct": 100,
        "motivation": "Parabéns! Você completou todos os requisitos desta classe.",
    }


def _build_timeline(progress_row: MemberNotebookRequirementProgress | None, hw_sub: HomeworkSubmission | None) -> dict | None:
    if not progress_row:
        return None
    req = progress_row.requirement
    nb_status = progress_row.status
    hw_status = hw_sub.status if hw_sub else None

    def step(key: str, label: str, state: str) -> dict:
        return {"key": key, "label": label, "state": state}

    assigned = "done" if hw_sub or nb_status != NB_STATUS_NOT_STARTED else "pending"
    if hw_sub and not hw_sub.submitted_at:
        assigned = "current"
    evidence = "done" if hw_sub and hw_sub.submitted_at else "pending"
    if hw_status == HW_STATUS_SUBMITTED:
        evidence = "current" if nb_status != NB_STATUS_COMPLETED else "done"
    review = "pending"
    if nb_status == NB_STATUS_PENDING or hw_status == HW_STATUS_SUBMITTED:
        review = "current"
    elif nb_status == NB_STATUS_COMPLETED or hw_status == HW_STATUS_APPROVED:
        review = "done"
    approved = "done" if nb_status == NB_STATUS_COMPLETED or hw_status == HW_STATUS_APPROVED else "pending"

    started_at = hw_sub.submitted_at if hw_sub and hw_sub.submitted_at else progress_row.updated_at
    return {
        "progress_id": progress_row.id,
        "title": req.title if req else "Atividade",
        "started_label": started_at.strftime("%d/%m/%Y") if started_at else "",
        "steps": [
            step("assigned", "Tarefa atribuída pela diretoria", assigned),
            step("evidence", "Evidência enviada", evidence),
            step("review", "Aguardando aprovação", review),
            step("approved", "Aprovada pela diretoria", approved),
        ],
    }


def build_parent_activities_page(member: Member) -> dict:
    """Monta dados completos da aba Atividades do portal dos pais."""
    ensure_member_notebook(member)
    detail = build_member_notebook_detail(member)
    summary = member_notebook_summary(member)
    nc_slug = detail.get("class_slug") or _slug(summary["class_name"])
    class_icon = CLASS_ICON.get(nc_slug, "📘")

    hw_by_req: dict[int, dict] = {}
    hw_sub_by_assignment: dict[int, HomeworkSubmission] = {}
    today = date.today()

    if member.clube_id:
        class_slug = nc_slug
        for hw in homework_list(member.clube_id):
            hw_slug = (hw.get("class_slug") or "").lower()
            if hw_slug and hw_slug != class_slug:
                continue
            rid = hw.get("requirement_id")
            if rid:
                hw_by_req[rid] = hw
        for sub in HomeworkSubmission.query.filter_by(member_id=member.id).all():
            hw_sub_by_assignment[sub.assignment_id] = sub

    cards: list[dict] = []
    section_filters: list[dict] = []
    recent_cutoff = datetime.utcnow() - timedelta(days=14)

    for sec in detail.get("sections") or []:
        sec_code = sec.get("code") or ""
        sec_title = sec.get("title") or ""
        sec_slug = _section_filter_slug(sec_code)
        section_filters.append(
            {
                "slug": sec_slug,
                "label": _section_filter_label(sec_code, sec_title),
                "code": sec_code,
                "count": len(sec.get("requirements") or []),
            }
        )
        for req_data in sec.get("requirements") or []:
            rid = req_data.get("requirement_id")
            progress_id = req_data.get("progress_id")
            prog_row = None
            if progress_id:
                prog_row = db.session.get(MemberNotebookRequirementProgress, progress_id)

            req_obj = db.session.get(NotebookClassRequirement, rid) if rid else None
            hw = hw_by_req.get(rid) if rid else None
            hw_sub = hw_sub_by_assignment.get(hw["id"]) if hw else None
            hw_assigned = bool(hw and hw.get("active"))

            hw_status = hw_sub.status if hw_sub else None
            overdue = bool(hw_assigned and hw.get("overdue") and hw_status != HW_STATUS_APPROVED)
            display_status = _resolve_parent_card_status(
                req_data.get("status") or NB_STATUS_NOT_STARTED,
                hw_assigned=hw_assigned,
                hw_status=hw_status,
                overdue=overdue,
            )
            meta = _PARENT_STATUS_META[display_status]
            due_label = "Aguardando tarefa da diretoria"
            if hw_assigned and hw.get("due_label"):
                due_label = hw["due_label"]
            elif req_data.get("completion_date"):
                due_label = f"Concluída em {req_data['completion_date'].strftime('%d/%m/%Y')}"

            cards.append(
                {
                    "id": progress_id or rid,
                    "progress_id": progress_id,
                    "requirement_id": rid,
                    "homework_id": hw["id"] if hw else None,
                    "title": req_data.get("title") or "",
                    "description": (req_data.get("description") or "")[:160],
                    "section_code": sec_code,
                    "section_title": sec_title,
                    "section_slug": sec_slug,
                    "section_label": _section_filter_label(sec_code, sec_title),
                    "number_label": req_data.get("number_label") or "",
                    "points": _requirement_points(req_obj),
                    "xp_label": f"{_requirement_points(req_obj)} XP",
                    "due_label": due_label,
                    "status_key": display_status,
                    "status_label": meta["label"],
                    "status_css": meta["css"],
                    "action_label": meta["action"],
                    "action_css": meta["action_css"],
                    "can_submit": bool(
                        hw_assigned and display_status in ("homework", "rejected")
                    ),
                    "hw_assigned": hw_assigned,
                    "is_new_homework": bool(
                        hw_assigned
                        and hw.get("created_at")
                        and hw["created_at"] >= recent_cutoff
                        and display_status == "homework"
                    ),
                    "updated_at": prog_row.updated_at if prog_row else None,
                }
            )

    _pending_keys = {"homework", "rejected", "expired"}
    _in_progress_keys = {"pending_review"}
    pending_count = sum(1 for c in cards if c["status_key"] in _pending_keys)
    in_progress_count = sum(1 for c in cards if c["status_key"] in _in_progress_keys)
    completed_count = sum(1 for c in cards if c["status_key"] == "completed")
    total_count = len(cards)

    stats = {
        "pending": pending_count,
        "in_progress": in_progress_count,
        "in_review": in_progress_count,
        "completed": completed_count,
        "total": total_count,
        "catalog": sum(1 for c in cards if c["status_key"] == "catalog"),
        "new": sum(1 for c in cards if c.get("is_new_homework")),
    }

    def _overview_pct(n: int) -> int:
        if total_count <= 0:
            return 0
        return round(100 * n / total_count)

    overview = {
        "pending": pending_count,
        "pending_pct": _overview_pct(pending_count),
        "in_progress": in_progress_count,
        "in_progress_pct": _overview_pct(in_progress_count),
        "completed": completed_count,
        "completed_pct": _overview_pct(completed_count),
        "total": total_count,
    }

    recent_completed: list[dict] = []
    for c in sorted(
        (x for x in cards if x["status_key"] == "completed"),
        key=lambda x: x.get("updated_at") or datetime.min,
        reverse=True,
    )[:5]:
        recent_completed.append(
            {
                "title": c["title"],
                "section_label": c["section_label"],
                "due_label": c["due_label"],
                "number_label": c.get("number_label") or "",
            }
        )

    child_name = (member.full_name or "").strip()
    child_first_name = child_name.split()[0] if child_name else "Desbravador"

    categories = [{"slug": "todas", "label": "Todas", "icon": "⊞", "count": len(cards)}]
    for sf in section_filters:
        categories.append(
            {
                "slug": sf["slug"],
                "label": sf["label"],
                "icon": sf["code"],
                "count": sf["count"],
            }
        )

    done = summary["completed_count"]
    total = summary["total_requirements"]
    pct = summary["progress_percent"]
    next_medal = _next_medal_goal(done, total)

    timeline_focus = None
    for c in sorted(cards, key=lambda x: x.get("updated_at") or datetime.min, reverse=True):
        if c["status_key"] in ("homework", "pending_review", "rejected") and c.get("hw_assigned"):
            prog = db.session.get(MemberNotebookRequirementProgress, c["progress_id"]) if c.get("progress_id") else None
            hw_sub = hw_sub_by_assignment.get(c["homework_id"]) if c.get("homework_id") else None
            timeline_focus = _build_timeline(prog, hw_sub)
            if timeline_focus:
                timeline_focus["card"] = c
                break

    sp_done = 0
    try:
        from app.specialties_service import member_progress_summary

        sp_done = member_progress_summary(member, member.clube_id).get("completed_count", 0)
    except Exception:
        pass

    medals_count = sum(1 for threshold, *_ in _MEDAL_MILESTONES if total and round(100 * done / total) >= threshold)

    achievement_title = "Aventureiro em formação"
    if pct >= 100:
        achievement_title = "Desbravador exemplar"
    elif pct >= 75:
        achievement_title = "Explorador dedicado"
    elif pct >= 50:
        achievement_title = "Companheiro em ação"
    elif pct >= 25:
        achievement_title = "Pesquisador em progresso"

    return {
        "has_notebook": bool(detail.get("requirements")),
        "child_name": child_name,
        "child_first_name": child_first_name,
        "class_name": summary["class_name"],
        "class_slug": nc_slug,
        "class_color": summary["class_color"],
        "class_icon": class_icon,
        "progress": {
            "done": done,
            "total": total,
            "percent": pct,
            "motivation": next_medal["motivation"],
            "pending": pending_count,
        },
        "next_medal": next_medal,
        "stats": stats,
        "overview": overview,
        "recent_completed": recent_completed,
        "categories": categories,
        "sections": detail.get("sections") or [],
        "activity_cards": cards,
        "timeline": timeline_focus,
        "achievements": {
            "medals_count": medals_count,
            "specialties_count": sp_done,
            "activities_completed": done,
            "badge_title": achievement_title,
            "progress_url": None,
        },
        "homework_submit_url": None,
        "communications_url": None,
    }


def backfill_member_notebooks(clube_id: str | None = None) -> int:
    """Gera cadernos para desbravadores existentes."""
    ensure_default_classes()
    q = Member.query
    if clube_id:
        q = q.filter_by(clube_id=clube_id)
    count = 0
    for m in q.all():
        if m.notebook_current:
            ensure_member_notebook(m)
            count += 1
    return count
