"""Gestão de especialidades — catálogo, progresso automático e sincronização."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import (
    ActivityRecord,
    DEFAULT_SPECIALTY_CATEGORIES,
    Member,
    MemberRequirementCheck,
    MemberSpecialtyProgress,
    OFFICIAL_SPECIALTY_COUNT,
    SP_DIFFICULTY_BASICA,
    SP_DIFFICULTY_LABELS,
    SP_ICON_KEYS,
    SP_STATUS_COMPLETED,
    SP_STATUS_IN_PROGRESS,
    SP_STATUS_LOCKED,
    SP_STATUS_NOT_STARTED,
    SP_STATUS_PENDING,
    SP_STATUS_LABELS,
    Specialty,
    SpecialtyRequirement,
    User,
)

ICON_EMOJI = {
    "first_aid": "🩹",
    "knots": "🪢",
    "trees": "🌳",
    "astronomy": "🔭",
    "cooking": "🍳",
    "camping": "⛺",
    "swimming": "🏊",
    "music": "🎵",
    "bible": "📖",
    "fitness": "💪",
    "crafts": "🎨",
    "nature": "🦋",
    "leadership": "⭐",
    "communication": "💬",
    "safety": "🛡️",
    "default": "🎖️",
    "custom": "🎖️",
}

ICON_COLORS = {
    "first_aid": "#ef4444",
    "knots": "#8b5cf6",
    "trees": "#22c55e",
    "astronomy": "#6366f1",
    "cooking": "#f59e0b",
    "camping": "#14b8a6",
    "swimming": "#0ea5e9",
    "music": "#ec4899",
    "bible": "#a855f7",
    "fitness": "#f97316",
    "crafts": "#eab308",
    "nature": "#10b981",
    "leadership": "#f9bc15",
    "communication": "#3b82f6",
    "safety": "#64748b",
    "default": "#3b82f6",
}

DEFAULT_SPECIALTY_SEED = [
    {
        "name": "Primeiros Socorros",
        "category": "Saúde e Fitness",
        "icon_key": "first_aid",
        "color_hex": "#ef4444",
        "difficulty": SP_DIFFICULTY_BASICA,
        "requirements": [
            "Demonstrar conhecimento sobre ferimentos leves",
            "Praticar bandagem simples",
            "Explicar quando chamar adultos ou serviços de emergência",
            "Participar de simulação de primeiros socorros",
        ],
    },
    {
        "name": "Nós e Amarras",
        "category": "Outdoor",
        "icon_key": "knots",
        "color_hex": "#8b5cf6",
        "requirements": [
            "Aprender e demonstrar o nó direito",
            "Aprender e demonstrar o nó lais de guia",
            "Aprender e demonstrar o nó bowline",
            "Usar nós em atividade prática do clube",
        ],
    },
    {
        "name": "Árvores",
        "category": "Natureza",
        "icon_key": "trees",
        "color_hex": "#22c55e",
        "requirements": [
            "Identificar 5 espécies de árvores locais",
            "Explicar importância das árvores para o meio ambiente",
            "Participar de atividade de plantio ou conservação",
        ],
    },
    {
        "name": "Astronomia",
        "category": "Ciência e Tecnologia",
        "icon_key": "astronomy",
        "color_hex": "#6366f1",
        "requirements": [
            "Identificar constelações visíveis na estação",
            "Explicar movimento aparente do Sol e da Lua",
            "Participar de observação noturna",
        ],
    },
    {
        "name": "Culinária",
        "category": "Artes e Habilidades",
        "icon_key": "cooking",
        "color_hex": "#f59e0b",
        "requirements": [
            "Preparar refeição simples com supervisão",
            "Demonstrar higiene na cozinha",
            "Planejar cardápio equilibrado para acampamento",
        ],
    },
    {
        "name": "Acampamento",
        "category": "Outdoor",
        "icon_key": "camping",
        "color_hex": "#14b8a6",
        "requirements": [
            "Montar barraca corretamente",
            "Organizar área de cozinha no acampamento",
            "Participar de acampamento de fim de semana",
            "Demonstrar cuidado com o ambiente (deixar limpo)",
        ],
    },
    {
        "name": "Natação",
        "category": "Saúde e Fitness",
        "icon_key": "swimming",
        "color_hex": "#0ea5e9",
        "requirements": [
            "Demonstrar habilidade básica na água",
            "Conhecer regras de segurança em piscinas e rios",
        ],
    },
    {
        "name": "Música",
        "category": "Artes e Habilidades",
        "icon_key": "music",
        "color_hex": "#ec4899",
        "requirements": [
            "Tocar ou cantar uma música no clube",
            "Participar do ensaio do grupo musical",
        ],
    },
    {
        "name": "Estudo da Bíblia",
        "category": "Espiritual",
        "icon_key": "bible",
        "color_hex": "#a855f7",
        "requirements": [
            "Memorizar versículo indicado pelo conselheiro",
            "Participar de estudo em grupo",
            "Compartilhar aprendizado com a unidade",
        ],
    },
    {
        "name": "Condicionamento Físico",
        "category": "Saúde e Fitness",
        "icon_key": "fitness",
        "color_hex": "#f97316",
        "requirements": [
            "Completar rotina de exercícios por 4 semanas",
            "Registrar progresso no caderno",
            "Participar de desafio físico do clube",
        ],
    },
    {
        "name": "Artesanato",
        "category": "Artes e Habilidades",
        "icon_key": "crafts",
        "color_hex": "#eab308",
        "requirements": [
            "Criar peça artesanal original",
            "Explicar materiais e técnicas utilizadas",
        ],
    },
    {
        "name": "Entomologia",
        "category": "Natureza",
        "icon_key": "nature",
        "color_hex": "#10b981",
        "requirements": [
            "Identificar insetos benéficos e nocivos",
            "Montar coleção ou relatório ilustrado",
        ],
    },
    {
        "name": "Liderança",
        "category": "Vocação",
        "icon_key": "leadership",
        "color_hex": "#f9bc15",
        "difficulty": "intermediaria",
        "requirements": [
            "Liderar devocional ou dinâmica",
            "Ajudar desbravadores mais novos em atividade",
            "Demonstrar responsabilidade por 30 dias",
        ],
    },
    {
        "name": "Comunicação",
        "category": "Vocação",
        "icon_key": "communication",
        "color_hex": "#3b82f6",
        "requirements": [
            "Apresentar tema de 5 minutos para a unidade",
            "Participar de debate ou mesa redonda",
        ],
    },
    {
        "name": "Segurança",
        "category": "Outdoor",
        "icon_key": "safety",
        "color_hex": "#64748b",
        "requirements": [
            "Conhecer regras de segurança do clube",
            "Demonstrar uso correto de equipamentos",
            "Participar de simulação de emergência",
        ],
    },
]


def icon_emoji(key: str | None) -> str:
    return ICON_EMOJI.get((key or "").strip(), ICON_EMOJI["default"])


def icon_color(key: str | None) -> str:
    return ICON_COLORS.get((key or "").strip(), ICON_COLORS["default"])


def ensure_default_specialties(clube_id: str) -> None:
    """Cria catálogo inicial se o clube ainda não tiver especialidades."""
    if Specialty.query.filter_by(clube_id=clube_id).count():
        return
    for i, row in enumerate(DEFAULT_SPECIALTY_SEED):
        sp = Specialty(
            clube_id=clube_id,
            name=row["name"],
            category=row["category"],
            icon_key=row.get("icon_key", "default"),
            color_hex=row.get("color_hex", icon_color(row.get("icon_key"))),
            difficulty=row.get("difficulty", SP_DIFFICULTY_BASICA),
            sort_order=i,
            points=20,
            active=True,
        )
        db.session.add(sp)
        db.session.flush()
        for j, desc in enumerate(row.get("requirements", [])):
            db.session.add(
                SpecialtyRequirement(
                    specialty_id=sp.id,
                    description=desc,
                    sort_order=j,
                )
            )
    db.session.flush()


def catalog_total(clube_id: str) -> int:
    return Specialty.query.filter_by(clube_id=clube_id, active=True).count()


def _requirement_ids(specialty_id: int) -> list[int]:
    return [
        r.id
        for r in SpecialtyRequirement.query.filter_by(specialty_id=specialty_id)
        .order_by(SpecialtyRequirement.sort_order)
        .all()
    ]


def _ensure_checks(enrollment: MemberSpecialtyProgress) -> list[MemberRequirementCheck]:
    """Garante linhas de checklist para todos os requisitos da especialidade."""
    req_ids = _requirement_ids(enrollment.specialty_id)
    existing = {
        c.requirement_id: c
        for c in enrollment.requirement_checks.all()
    }
    for rid in req_ids:
        if rid not in existing:
            chk = MemberRequirementCheck(
                enrollment_id=enrollment.id,
                requirement_id=rid,
                completed=False,
            )
            db.session.add(chk)
            existing[rid] = chk
    db.session.flush()
    return list(existing.values())


def recalc_enrollment_progress(
    enrollment: MemberSpecialtyProgress,
    *,
    user_id: int | None = None,
) -> MemberSpecialtyProgress:
    """Recalcula percentual e status com base nos requisitos marcados."""
    checks = _ensure_checks(enrollment)
    total = len(checks)
    done = sum(1 for c in checks if c.completed)
    pct = round(100 * done / total) if total else 0
    enrollment.progress_percent = pct
    enrollment.updated_at = datetime.utcnow()

    if enrollment.status == SP_STATUS_COMPLETED:
        return enrollment

    if total == 0:
        enrollment.status = SP_STATUS_IN_PROGRESS
        return enrollment

    if done == total:
        if enrollment.status != SP_STATUS_PENDING:
            enrollment.status = SP_STATUS_PENDING
    elif done > 0:
        enrollment.status = SP_STATUS_IN_PROGRESS
    else:
        enrollment.status = SP_STATUS_IN_PROGRESS

    return enrollment


def approve_enrollment(
    enrollment: MemberSpecialtyProgress,
    *,
    approver_id: int | None,
) -> MemberSpecialtyProgress:
    """Marca especialidade como concluída e sincroniza perfil automaticamente."""
    enrollment.status = SP_STATUS_COMPLETED
    enrollment.progress_percent = 100
    enrollment.completed_at = datetime.utcnow()
    enrollment.approved_by_id = approver_id
    enrollment.approved_at = datetime.utcnow()
    enrollment.updated_at = datetime.utcnow()
    sync_member_on_specialty_complete(enrollment)
    return enrollment


def specialty_icon_url(
    specialty: Specialty,
    photo_url_builder,
) -> str | None:
    """URL pública do ícone personalizado, se existir."""
    fn = getattr(specialty, "icon_filename", None)
    if fn and photo_url_builder:
        return photo_url_builder(fn)
    return None


def sync_member_on_specialty_complete(enrollment: MemberSpecialtyProgress) -> None:
    """Atualiza timeline (ActivityRecord) e desempenho geral após conclusão."""
    member = enrollment.member
    specialty = enrollment.specialty
    if not member or not specialty:
        return

    existing = (
        ActivityRecord.query.filter_by(member_id=member.id, title=specialty.name)
        .filter(ActivityRecord.category == "Especialidade")
        .filter(ActivityRecord.completed.is_(True))
        .first()
    )
    if not existing:
        db.session.add(
            ActivityRecord(
                member_id=member.id,
                title=specialty.name,
                category="Especialidade",
                notes=f"Especialidade concluída e aprovada.",
                progress_percent=100,
                completed=True,
                recorded_at=date.today(),
            )
        )

    # Desempenho geral recalculado automaticamente via computed_overall_performance()
    perf = member.computed_overall_performance()
    member.overall_performance = perf


def _remove_specialty_activity_record(member: Member, specialty: Specialty) -> None:
    if not member or not specialty:
        return
    ActivityRecord.query.filter_by(
        member_id=member.id,
        title=specialty.name,
        category="Especialidade",
    ).delete(synchronize_session=False)


def delete_member_enrollment(enrollment: MemberSpecialtyProgress) -> str | None:
    """Remove vínculo/registro de especialidade do desbravador e reverte sincronização."""
    member = enrollment.member
    specialty = enrollment.specialty
    name = specialty.name if specialty else "Especialidade"
    if enrollment.status == SP_STATUS_COMPLETED and member and specialty:
        _remove_specialty_activity_record(member, specialty)
    db.session.delete(enrollment)
    if member:
        member.overall_performance = member.computed_overall_performance()
    return name


def delete_catalog_specialty(specialty: Specialty, upload_folder: str) -> str:
    """Exclui especialidade do catálogo (e todos os vínculos em cascata)."""
    name = specialty.name
    touched_members: set[int] = set()
    for enr in list(specialty.enrollments.all()):
        member = enr.member
        if member:
            touched_members.add(member.id)
        if enr.status == SP_STATUS_COMPLETED and member:
            _remove_specialty_activity_record(member, specialty)
        db.session.delete(enr)
    for mid in touched_members:
        m = db.session.get(Member, mid)
        if m:
            m.overall_performance = m.computed_overall_performance()
    if specialty.icon_filename:
        from app.uploads_util import safe_remove_upload

        safe_remove_upload(upload_folder, specialty.icon_filename)
    db.session.delete(specialty)
    return name


def apply_specialty_icon_upload(
    specialty: Specialty,
    file_storage,
    upload_folder: str,
) -> bool:
    """Salva foto do ícone; retorna True se um arquivo foi gravado."""
    from app.uploads_util import safe_remove_upload, save_upload

    rel = save_upload(file_storage, upload_folder, "specialties")
    if not rel:
        return False
    if specialty.icon_filename:
        safe_remove_upload(upload_folder, specialty.icon_filename)
    specialty.icon_filename = rel
    specialty.icon_key = "custom"
    return True


def enroll_member(
    member: Member,
    specialty: Specialty,
    *,
    user_id: int | None = None,
) -> MemberSpecialtyProgress:
    """Vincula especialidade ao desbravador (idempotente)."""
    row = MemberSpecialtyProgress.query.filter_by(
        member_id=member.id, specialty_id=specialty.id
    ).first()
    if row:
        return recalc_enrollment_progress(row, user_id=user_id)
    row = MemberSpecialtyProgress(
        member_id=member.id,
        specialty_id=specialty.id,
        status=SP_STATUS_IN_PROGRESS,
        progress_percent=0,
    )
    db.session.add(row)
    db.session.flush()
    _ensure_checks(row)
    return recalc_enrollment_progress(row, user_id=user_id)


def toggle_requirement(
    enrollment_id: int,
    requirement_id: int,
    *,
    completed: bool,
    user_id: int | None = None,
) -> MemberSpecialtyProgress | None:
    chk = MemberRequirementCheck.query.filter_by(
        enrollment_id=enrollment_id, requirement_id=requirement_id
    ).first()
    if not chk:
        return None
    chk.completed = completed
    chk.completed_at = datetime.utcnow() if completed else None
    chk.completed_by_id = user_id if completed else None
    enrollment = db.session.get(MemberSpecialtyProgress, enrollment_id)
    if not enrollment:
        return None
    return recalc_enrollment_progress(enrollment, user_id=user_id)


def member_progress_summary(member: Member, clube_id: str | None = None) -> dict:
    """Resumo agregado para painéis e portal dos pais."""
    cid = clube_id or member.clube_id
    total_catalog = catalog_total(cid) if cid else 0
    global_total = max(total_catalog, OFFICIAL_SPECIALTY_COUNT)

    rows = MemberSpecialtyProgress.query.filter_by(member_id=member.id).all()
    completed = [r for r in rows if r.status == SP_STATUS_COMPLETED]
    in_progress = [r for r in rows if r.status == SP_STATUS_IN_PROGRESS]
    pending = [r for r in rows if r.status == SP_STATUS_PENDING]

    points = sum((r.specialty.points or 0) for r in completed if r.specialty)
    categories = {r.specialty.category for r in completed if r.specialty and r.specialty.category}
    all_cats = set(DEFAULT_SPECIALTY_CATEGORIES)
    if cid:
        extra = (
            db.session.query(Specialty.category)
            .filter_by(clube_id=cid, active=True)
            .distinct()
            .all()
        )
        all_cats |= {c[0] for c in extra if c[0]}

    n_done = len(completed)
    pct_global = round(100 * n_done / global_total, 2) if global_total else 0

    return {
        "completed_count": n_done,
        "in_progress_count": len(in_progress),
        "pending_count": len(pending),
        "total_catalog": total_catalog,
        "global_total": global_total,
        "progress_label": f"{n_done} / {global_total}",
        "progress_percent": pct_global,
        "points_total": points,
        "categories_explored": len(categories),
        "categories_total": len(all_cats),
        "categories_label": f"{len(categories)} / {len(all_cats)}",
    }


def serialize_specialty_card(
    specialty: Specialty,
    *,
    enrollment: MemberSpecialtyProgress | None = None,
    locked: bool = False,
    photo_url_builder=None,
) -> dict:
    reqs = specialty.requirements.order_by(SpecialtyRequirement.sort_order).all()
    status = SP_STATUS_LOCKED if locked else (enrollment.status if enrollment else SP_STATUS_NOT_STARTED)
    progress = enrollment.progress_percent if enrollment else 0
    icon_url = specialty_icon_url(specialty, photo_url_builder) if photo_url_builder else None
    return {
        "id": specialty.id,
        "name": specialty.name,
        "category": specialty.category,
        "description": (specialty.description or "")[:200],
        "difficulty": specialty.difficulty,
        "difficulty_label": SP_DIFFICULTY_LABELS.get(specialty.difficulty, specialty.difficulty),
        "icon_key": specialty.icon_key,
        "icon_filename": specialty.icon_filename,
        "icon_url": icon_url,
        "icon_emoji": icon_emoji(specialty.icon_key) if not icon_url else None,
        "color_hex": specialty.color_hex or icon_color(specialty.icon_key),
        "points": specialty.points or 0,
        "status": status,
        "status_label": SP_STATUS_LABELS.get(status, status),
        "progress": progress,
        "requirements_count": len(reqs),
        "enrollment_id": enrollment.id if enrollment else None,
        "completed_at": enrollment.completed_at if enrollment else None,
        "approved_by": (
            enrollment.approved_by.full_name
            if enrollment and enrollment.approved_by
            else None
        ),
        "locked": locked,
    }


def specialty_cards_for_member(
    member: Member,
    *,
    photo_url_builder=None,
) -> list[dict]:
    """Cards gamificados para portal dos pais."""
    cid = member.clube_id
    if not cid:
        return []
    ensure_default_specialties(cid)
    enrollments = {
        e.specialty_id: e
        for e in MemberSpecialtyProgress.query.filter_by(member_id=member.id).all()
    }
    specialties = (
        Specialty.query.filter_by(clube_id=cid, active=True)
        .order_by(Specialty.sort_order, Specialty.name)
        .all()
    )
    cards = []
    for sp in specialties:
        enr = enrollments.get(sp.id)
        cards.append(
            serialize_specialty_card(
                sp,
                enrollment=enr,
                locked=(enr is None),
                photo_url_builder=photo_url_builder,
            )
        )
    return cards


CATEGORY_ICONS = {
    "Natureza": "🍃",
    "Outdoor": "🏕️",
    "Atividades Recreativas": "🎯",
    "Saúde e Fitness": "❤️",
    "Artes e Habilidades": "🎨",
    "Ciência e Tecnologia": "🔬",
    "Vocação": "💼",
    "Espiritual": "✝️",
}


def _category_slug(name: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "-").replace("&", "e") or "outros"


def _parent_card_status(status: str) -> str:
    if status == SP_STATUS_COMPLETED:
        return "concluida"
    if status in (SP_STATUS_IN_PROGRESS, SP_STATUS_PENDING):
        return "em_andamento"
    return "bloqueada"


def _enrollment_requirements(enrollment: MemberSpecialtyProgress | None) -> list[dict]:
    if not enrollment:
        return []
    _ensure_checks(enrollment)
    reqs = []
    for chk in enrollment.requirement_checks.all():
        req = chk.requirement
        if not req:
            continue
        reqs.append(
            {
                "id": req.id,
                "description": req.description,
                "completed": bool(chk.completed),
                "completed_at": chk.completed_at.isoformat() if chk.completed_at else None,
            }
        )
    return reqs


def _enrollment_history(enrollment: MemberSpecialtyProgress | None) -> list[dict]:
    if not enrollment:
        return []
    rows = []
    if enrollment.started_at:
        rows.append({"label": "Iniciada em", "date": enrollment.started_at.isoformat()})
    if enrollment.completed_at:
        rows.append({"label": "Concluída em", "date": enrollment.completed_at.isoformat()})
    if enrollment.approved_at:
        rows.append({"label": "Aprovada em", "date": enrollment.approved_at.isoformat()})
    return rows


def build_parent_specialties_album(
    member: Member,
    *,
    photo_url_builder=None,
) -> dict:
    """Dados completos do álbum de especialidades para o portal dos pais."""
    cid = member.clube_id
    if not cid:
        return {
            "cards": [],
            "categories": [],
            "stats": {
                "completed": 0,
                "in_progress": 0,
                "available": 0,
                "total": OFFICIAL_SPECIALTY_COUNT,
                "percent": 0,
                "progress_label": "0 / 512",
            },
        }

    ensure_default_specialties(cid)
    enrollments = {
        e.specialty_id: e
        for e in MemberSpecialtyProgress.query.filter_by(member_id=member.id).all()
    }
    specialties = (
        Specialty.query.filter_by(clube_id=cid, active=True)
        .order_by(Specialty.sort_order, Specialty.category, Specialty.name)
        .all()
    )
    summary = member_progress_summary(member, cid)

    cards = []
    by_category: dict[str, list[dict]] = {}

    for sp in specialties:
        enr = enrollments.get(sp.id)
        locked = enr is None
        raw = serialize_specialty_card(
            sp,
            enrollment=enr,
            locked=locked,
            photo_url_builder=photo_url_builder,
        )
        status = _parent_card_status(raw["status"])
        card = {
            "id": raw["id"],
            "name": raw["name"],
            "category": raw["category"] or "Outros",
            "category_slug": _category_slug(raw["category"] or "Outros"),
            "description": raw["description"],
            "difficulty": raw["difficulty"],
            "difficulty_label": raw["difficulty_label"],
            "status": status,
            "status_label": raw["status_label"],
            "progress": raw["progress"],
            "points": raw["points"],
            "locked": locked or status == "bloqueada",
            "icon_emoji": raw["icon_emoji"] or icon_emoji(sp.icon_key),
            "icon_url": raw["icon_url"],
            "color_hex": raw["color_hex"],
            "requirements_count": raw["requirements_count"],
            "requirements": _enrollment_requirements(enr),
            "history": _enrollment_history(enr),
            "completed_at": enr.completed_at.isoformat() if enr and enr.completed_at else None,
            "approved_by": raw["approved_by"],
            "enrollment_id": raw["enrollment_id"],
        }
        cards.append(card)
        cat = card["category"]
        by_category.setdefault(cat, []).append(card)

    cat_order = list(DEFAULT_SPECIALTY_CATEGORIES)
    extra_cats = sorted(set(by_category) - set(cat_order))
    cat_order.extend(extra_cats)

    categories = []
    for cat_name in cat_order:
        cat_cards = by_category.get(cat_name)
        if not cat_cards:
            continue
        categories.append(
            {
                "name": cat_name,
                "slug": _category_slug(cat_name),
                "icon": CATEGORY_ICONS.get(cat_name, "🏅"),
                "count": len(cat_cards),
                "cards": cat_cards,
            }
        )

    completed = summary.get("completed_count", 0)
    in_progress = summary.get("in_progress_count", 0) + summary.get("pending_count", 0)
    global_total = summary.get("global_total", OFFICIAL_SPECIALTY_COUNT)
    available = max(0, global_total - completed - in_progress)

    return {
        "cards": cards,
        "categories": categories,
        "stats": {
            "completed": completed,
            "in_progress": in_progress,
            "available": available,
            "total": global_total,
            "percent": summary.get("progress_percent", 0),
            "progress_label": summary.get("progress_label", f"{completed} / {global_total}"),
            "points": summary.get("points_total", 0),
        },
    }


def recent_specialty_achievements(member: Member, limit: int = 5) -> list[dict]:
    rows = (
        MemberSpecialtyProgress.query.filter_by(member_id=member.id, status=SP_STATUS_COMPLETED)
        .order_by(MemberSpecialtyProgress.completed_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        sp = r.specialty
        if not sp:
            continue
        out.append(
            {
                "title": sp.name,
                "date": r.completed_at.date() if r.completed_at else date.today(),
                "kind": "especialidade",
                "icon": "medal",
                "category": sp.category,
            }
        )
    return out


def club_dashboard_stats(clube_id: str) -> dict:
    """KPIs do painel administrativo."""
    member_ids = [m.id for m in Member.query.filter_by(clube_id=clube_id).all()]
    if not member_ids:
        return {
            "total_members": 0,
            "completed_total": 0,
            "in_progress_total": 0,
            "pending_total": 0,
            "catalog_count": catalog_total(clube_id),
            "global_total": OFFICIAL_SPECIALTY_COUNT,
            "completed_trend": "+0%",
            "in_progress_trend": "+0%",
        }

    completed = MemberSpecialtyProgress.query.filter(
        MemberSpecialtyProgress.member_id.in_(member_ids),
        MemberSpecialtyProgress.status == SP_STATUS_COMPLETED,
    ).count()
    in_progress = MemberSpecialtyProgress.query.filter(
        MemberSpecialtyProgress.member_id.in_(member_ids),
        MemberSpecialtyProgress.status == SP_STATUS_IN_PROGRESS,
    ).count()
    pending = MemberSpecialtyProgress.query.filter(
        MemberSpecialtyProgress.member_id.in_(member_ids),
        MemberSpecialtyProgress.status == SP_STATUS_PENDING,
    ).count()

    month_ago = datetime.utcnow() - timedelta(days=30)
    completed_month = MemberSpecialtyProgress.query.filter(
        MemberSpecialtyProgress.member_id.in_(member_ids),
        MemberSpecialtyProgress.status == SP_STATUS_COMPLETED,
        MemberSpecialtyProgress.completed_at >= month_ago,
    ).count()
    trend_pct = round(100 * completed_month / max(completed, 1)) if completed else 0

    return {
        "total_members": len(member_ids),
        "completed_total": completed,
        "in_progress_total": in_progress,
        "pending_total": pending,
        "catalog_count": catalog_total(clube_id),
        "global_total": OFFICIAL_SPECIALTY_COUNT,
        "completed_trend": f"+{min(trend_pct, 99)}%",
        "in_progress_trend": f"+{min(round(in_progress / max(len(member_ids), 1) * 10), 99)}%",
    }


def serialize_member_row(
    member: Member,
    *,
    photo_url: str | None = None,
    clube_id: str | None = None,
) -> dict:
    summary = member_progress_summary(member, clube_id)
    return {
        "id": member.id,
        "full_name": member.full_name,
        "unit": member.unit or "Sem unidade",
        "class_label": member.notebook_current or "—",
        "photo_url": photo_url,
        "initial": (member.full_name or "?")[0].upper(),
        "completed": summary["completed_count"],
        "in_progress": summary["in_progress_count"],
        "pending": summary["pending_count"],
        "progress_label": summary["progress_label"],
        "progress_percent": summary["progress_percent"],
        "global_total": summary["global_total"],
    }


def build_member_detail(
    member: Member,
    clube_id: str,
    *,
    photo_url: str | None = None,
    photo_url_builder=None,
    approver_name: str | None = None,
    tab: str = "concluidas",
) -> dict:
    """Contexto completo do painel central (um desbravador)."""
    ensure_default_specialties(clube_id)
    summary = member_progress_summary(member, clube_id)
    enrollments = {
        e.specialty_id: e
        for e in MemberSpecialtyProgress.query.filter_by(member_id=member.id).all()
    }
    all_sp = (
        Specialty.query.filter_by(clube_id=clube_id, active=True)
        .order_by(Specialty.category, Specialty.name)
        .all()
    )

    completed_cards = []
    in_progress_rows = []
    pending_rows = []
    history_rows = []

    for sp in all_sp:
        enr = enrollments.get(sp.id)
        card = serialize_specialty_card(
            sp, enrollment=enr, locked=False, photo_url_builder=photo_url_builder
        )
        if enr and enr.status == SP_STATUS_COMPLETED:
            completed_cards.append(card)
            history_rows.append(
                {
                    "title": sp.name,
                    "date": enr.completed_at,
                    "category": sp.category,
                    "approver": enr.approved_by.full_name if enr.approved_by else approver_name,
                }
            )
        elif enr and enr.status == SP_STATUS_PENDING:
            pending_rows.append({**card, "enrollment_id": enr.id})
        elif enr and enr.status == SP_STATUS_IN_PROGRESS:
            reqs = []
            _ensure_checks(enr)
            for chk in enr.requirement_checks.all():
                req = chk.requirement
                if req:
                    reqs.append(
                        {
                            "id": req.id,
                            "description": req.description,
                            "completed": chk.completed,
                            "check_id": chk.id,
                        }
                    )
            in_progress_rows.append({**card, "enrollment_id": enr.id, "requirements": reqs})

    catalog_options = [
        {"id": s.id, "name": s.name, "category": s.category}
        for s in all_sp
        if s.id not in enrollments
    ]

    age = member.age_years
    return {
        "member": member,
        "photo_url": photo_url,
        "age": age,
        "summary": summary,
        "completed_cards": completed_cards[:12],
        "completed_total": len(completed_cards),
        "in_progress_rows": in_progress_rows,
        "pending_rows": pending_rows,
        "history_rows": history_rows[:20],
        "catalog_options": catalog_options,
        "active_tab": tab,
        "categories": sorted({s.category for s in all_sp}),
    }


def build_admin_dashboard(
    clube_id: str,
    *,
    photo_url_builder,
    member_id: int | None = None,
    q: str = "",
    unit_filter: str = "",
    status_filter: str = "",
    sort: str = "name",
    page: int = 1,
    per_page: int = 12,
    tab: str = "concluidas",
) -> dict:
    """Monta contexto do painel premium de especialidades."""
    ensure_default_specialties(clube_id)
    stats = club_dashboard_stats(clube_id)

    query = Member.query.filter_by(clube_id=clube_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Member.full_name.ilike(like))
    if unit_filter:
        query = query.filter(Member.unit == unit_filter)

    members = query.order_by(Member.full_name).all()
    rows = []
    for m in members:
        pu = photo_url_builder(m.photo_filename) if m.photo_filename else None
        row = serialize_member_row(m, photo_url=pu, clube_id=clube_id)
        if status_filter == "pending" and row["pending"] == 0:
            continue
        if status_filter == "in_progress" and row["in_progress"] == 0:
            continue
        if status_filter == "completed" and row["completed"] == 0:
            continue
        rows.append(row)

    if sort == "progress":
        rows.sort(key=lambda r: r["progress_percent"], reverse=True)
    elif sort == "completed":
        rows.sort(key=lambda r: r["completed"], reverse=True)
    else:
        rows.sort(key=lambda r: r["full_name"])

    total_pages = max(1, (len(rows) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_rows = rows[start : start + per_page]

    selected = None
    detail = None
    units = sorted({m.unit for m in members if m.unit})

    catalog = (
        Specialty.query.filter_by(clube_id=clube_id, active=True)
        .order_by(Specialty.category, Specialty.sort_order, Specialty.name)
        .all()
    )
    catalog_rows = []
    for sp in catalog:
        n_req = sp.requirements.count()
        n_done = MemberSpecialtyProgress.query.filter_by(
            specialty_id=sp.id, status=SP_STATUS_COMPLETED
        ).count()
        icon_url = specialty_icon_url(sp, photo_url_builder)
        catalog_rows.append(
            {
                "id": sp.id,
                "name": sp.name,
                "category": sp.category,
                "difficulty_label": SP_DIFFICULTY_LABELS.get(sp.difficulty, sp.difficulty),
                "icon_emoji": icon_emoji(sp.icon_key) if not icon_url else None,
                "icon_url": icon_url,
                "color_hex": sp.color_hex or icon_color(sp.icon_key),
                "requirements_count": n_req,
                "completions_count": n_done,
                "active": sp.active,
                "points": sp.points,
            }
        )

    if member_id:
        m = db.session.get(Member, member_id)
        if m and m.clube_id == clube_id:
            selected = m.id
            pu = photo_url_builder(m.photo_filename) if m.photo_filename else None
            detail = build_member_detail(
                m, clube_id, photo_url=pu, photo_url_builder=photo_url_builder, tab=tab
            )

    return {
        "stats": stats,
        "members": page_rows,
        "members_total": len(rows),
        "page": page,
        "total_pages": total_pages,
        "selected_member_id": selected,
        "detail": detail,
        "units": units,
        "catalog_rows": catalog_rows,
        "categories": list(DEFAULT_SPECIALTY_CATEGORIES),
        "icon_keys": SP_ICON_KEYS,
        "difficulty_options": list(SP_DIFFICULTY_LABELS.items()),
    }


def apply_specialty_form(specialty: Specialty, form) -> str | None:
    name = (form.get("name") or "").strip()
    if not name:
        return "Informe o nome da especialidade."
    specialty.name = name
    specialty.category = (form.get("category") or "Natureza").strip() or "Natureza"
    specialty.description = (form.get("description") or "").strip() or None
    specialty.difficulty = (form.get("difficulty") or SP_DIFFICULTY_BASICA).strip()
    if not getattr(specialty, "icon_filename", None):
        specialty.icon_key = (form.get("icon_key") or "default").strip()
    specialty.color_hex = (form.get("color_hex") or icon_color(specialty.icon_key)).strip()
    try:
        specialty.points = max(0, int(form.get("points") or 20))
    except (TypeError, ValueError):
        specialty.points = 20
    specialty.active = (form.get("active") or "1") in ("1", "on", "true", "yes")
    specialty.updated_at = datetime.utcnow()
    return None


def save_requirements_from_form(specialty: Specialty, form) -> None:
    """Substitui requisitos a partir de campos requirement_0, requirement_1, …"""
    SpecialtyRequirement.query.filter_by(specialty_id=specialty.id).delete()
    items = []
    for key in sorted(form.keys()):
        if key.startswith("requirement_"):
            val = (form.get(key) or "").strip()
            if val:
                items.append(val)
    if not items:
        raw = (form.get("requirements_text") or "").strip()
        if raw:
            items = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for i, desc in enumerate(items):
        db.session.add(
            SpecialtyRequirement(specialty_id=specialty.id, description=desc, sort_order=i)
        )
    db.session.flush()
