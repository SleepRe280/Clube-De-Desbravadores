"""Progressão gamificada do desbravador — XP, níveis, classes e conquistas."""
from __future__ import annotations

from datetime import date, datetime

from app.activities_service import CLASS_COLORS, CLASS_ICON, _slug, ensure_default_classes, normalize_class_name
from app.models import (
    Member,
    MemberNotebookEnrollment,
    MemberSpecialtyProgress,
    NB_STATUS_COMPLETED,
    OFFICIAL_SPECIALTY_COUNT,
    SP_STATUS_COMPLETED,
)

MAX_LEVEL = 100
MAX_TOTAL_XP = 12_000
CLASS_XP_POOL = 9_600  # ~80% — todas as classes regulares ≈ nível 80
SPECIALTY_XP_POOL = 2_400  # ~20%
SPECIALTY_TARGET_COUNT = max(1, round(OFFICIAL_SPECIALTY_COUNT * 0.1))  # ~51 para nível máximo
CLASS_XP_EACH = CLASS_XP_POOL // 5

REGULAR_CLASS_SLUGS = ("amigo", "companheiro", "pesquisador", "pioneiro", "excursionista")

REGULAR_CLASSES = tuple(
    {
        "slug": slug,
        "name": name,
        "color": CLASS_COLORS.get(slug, "#3b82f6"),
        "icon": CLASS_ICON.get(slug, "📘"),
    }
    for slug, name in (
        ("amigo", "Amigo"),
        ("companheiro", "Companheiro"),
        ("pesquisador", "Pesquisador"),
        ("pioneiro", "Pioneiro"),
        ("excursionista", "Excursionista"),
    )
)

JOURNEY_MILESTONES = (
    {"level": 20, "label": "Iniciante"},
    {"level": 40, "label": "Explorador"},
    {"level": 60, "label": "Aventureiro"},
    {"level": 80, "label": "Desbravador"},
    {"level": 100, "label": "Grande Mestre"},
)

LEVEL_TITLE_TIERS = (
    (100, "Grande Mestre"),
    (80, "Desbravador"),
    (70, "Veterano"),
    (60, "Aventureiro"),
    (40, "Explorador"),
    (20, "Iniciante"),
    (1, "Novato"),
)

ACHIEVEMENT_DEFS = (
    {"id": "first_specialty", "title": "Primeira Especialidade", "icon": "medal"},
    {"id": "first_class", "title": "Primeira Classe Completa", "icon": "shield"},
    {"id": "level_25", "title": "Nível 25 Atingido", "icon": "star"},
    {"id": "level_50", "title": "Nível 50 Atingido", "icon": "star"},
    {"id": "level_75", "title": "Nível 75 Atingido", "icon": "star"},
    {"id": "all_classes", "title": "Todas as Classes Concluídas", "icon": "trophy"},
    {"id": "activities_100", "title": "100 Atividades Concluídas", "icon": "book"},
)


def _current_regular_index(member: Member) -> int:
    norm = normalize_class_name(member.notebook_current)
    if not norm:
        return 0
    slug = _slug(norm)
    if slug == "guia":
        return len(REGULAR_CLASS_SLUGS)
    try:
        return REGULAR_CLASS_SLUGS.index(slug)
    except ValueError:
        return 0


def _enrollments_by_slug(member: Member) -> dict[str, MemberNotebookEnrollment]:
    out: dict[str, MemberNotebookEnrollment] = {}
    for enr in member.notebook_enrollments.all():
        nc = enr.notebook_class
        if nc and nc.slug:
            out[nc.slug] = enr
    return out


def member_regular_classes(member: Member) -> list[dict]:
    """Progresso das cinco classes regulares com XP por classe."""
    ensure_default_classes()
    current_idx = _current_regular_index(member)
    enrollments = _enrollments_by_slug(member)
    rows: list[dict] = []

    for i, meta in enumerate(REGULAR_CLASSES):
        slug = meta["slug"]
        enr = enrollments.get(slug)
        if enr:
            pct = int(enr.progress_percent or 0)
            completed = enr.status == NB_STATUS_COMPLETED or pct >= 100
            status = "completed" if completed else "in_progress"
            pct = 100 if completed else pct
        elif i < current_idx:
            pct = 100
            status = "completed"
        elif i == current_idx:
            pct = 0
            status = "in_progress"
        else:
            pct = 0
            status = "locked"

        xp_earned = round(CLASS_XP_EACH * pct / 100)
        rows.append(
            {
                "slug": slug,
                "name": meta["name"],
                "color": meta["color"],
                "icon": meta["icon"],
                "percent": pct,
                "status": status,
                "status_label": {
                    "completed": "Concluída",
                    "in_progress": "Em andamento",
                    "locked": "Bloqueada",
                }[status],
                "xp_earned": xp_earned,
                "xp_max": CLASS_XP_EACH,
                "completed_at": enr.completed_at if enr else None,
            }
        )
    return rows


def specialty_xp_from_count(completed_count: int) -> int:
    if completed_count <= 0:
        return 0
    return min(
        SPECIALTY_XP_POOL,
        round(SPECIALTY_XP_POOL * completed_count / SPECIALTY_TARGET_COUNT),
    )


def level_from_xp(xp: int) -> int:
    xp = max(0, min(xp, MAX_TOTAL_XP))
    if xp >= MAX_TOTAL_XP:
        return MAX_LEVEL
    return max(1, min(MAX_LEVEL - 1, (xp + 119) // 120))


def level_title(level: int) -> str:
    for threshold, label in LEVEL_TITLE_TIERS:
        if level >= threshold:
            return label
    return "Novato"


def xp_threshold_for_level(level: int) -> int:
    level = max(1, min(MAX_LEVEL, level))
    return min(MAX_TOTAL_XP, (level - 1) * 120)


def xp_for_next_level(level: int) -> int:
    if level >= MAX_LEVEL:
        return MAX_TOTAL_XP
    return min(MAX_TOTAL_XP, level * 120)


def compute_xp(member: Member, *, sp_completed: int | None = None) -> dict:
    """Calcula XP total e decomposição classes / especialidades."""
    classes = member_regular_classes(member)
    class_xp = sum(c["xp_earned"] for c in classes)
    if sp_completed is None:
        try:
            from app.specialties_service import member_progress_summary

            sp_completed = member_progress_summary(member, member.clube_id).get("completed_count", 0)
        except Exception:
            sp_completed = 0
    specialty_xp = specialty_xp_from_count(int(sp_completed or 0))
    total = min(MAX_TOTAL_XP, class_xp + specialty_xp)
    return {
        "total": total,
        "class_xp": class_xp,
        "specialty_xp": specialty_xp,
        "class_xp_max": CLASS_XP_POOL,
        "specialty_xp_max": SPECIALTY_XP_POOL,
        "classes": classes,
        "specialties_completed": int(sp_completed or 0),
    }


def level_progress(xp: int) -> dict:
    level = level_from_xp(xp)
    next_level = min(MAX_LEVEL, level + 1)
    level_start = xp_threshold_for_level(level)
    next_xp = xp_for_next_level(level)
    span = max(1, next_xp - level_start)
    in_level = max(0, min(span, xp - level_start))
    pct = round(100 * in_level / span)
    return {
        "level": level,
        "level_title": level_title(level),
        "next_level": next_level,
        "xp": xp,
        "xp_level_start": level_start,
        "xp_level_max": next_xp,
        "xp_in_level": in_level,
        "xp_to_next": max(0, next_xp - xp),
        "progress_pct": pct,
        "is_max_level": level >= MAX_LEVEL and xp >= MAX_TOTAL_XP,
    }


def journey_map(level: int) -> list[dict]:
    """Marcos da jornada (20 → 100) com estado visual."""
    rows = []
    prev = 0
    for m in JOURNEY_MILESTONES:
        lv = m["level"]
        if level >= lv:
            state = "done"
        elif prev < level < lv:
            state = "current"
        else:
            state = "locked"
        prev = lv
        rows.append({"level": lv, "label": m["label"], "state": state})
    return rows


def _first_completed_class_date(classes: list[dict]) -> datetime | None:
    dates = [c["completed_at"] for c in classes if c.get("completed_at")]
    return min(dates) if dates else None


def _all_classes_completed(classes: list[dict]) -> bool:
    return bool(classes) and all(c["percent"] >= 100 for c in classes)


def gamification_achievements(
    member: Member,
    *,
    level: int,
    classes: list[dict],
    sp_completed: int,
    activities_done: int,
    limit: int = 5,
) -> list[dict]:
    """Conquistas desbloqueadas, ordenadas da mais recente."""
    unlocked: list[dict] = []

    first_sp = (
        MemberSpecialtyProgress.query.filter_by(
            member_id=member.id, status=SP_STATUS_COMPLETED
        )
        .order_by(MemberSpecialtyProgress.completed_at.desc())
        .first()
    )
    if first_sp:
        unlocked.append(
            {
                "id": "first_specialty",
                "title": "Primeira Especialidade",
                "icon": "medal",
                "date": first_sp.completed_at,
            }
        )

    first_class_dt = _first_completed_class_date(classes)
    if first_class_dt:
        unlocked.append(
            {
                "id": "first_class",
                "title": "Primeira Classe Completa",
                "icon": "shield",
                "date": first_class_dt,
            }
        )

    for threshold, title in ((25, "Nível 25 Atingido"), (50, "Nível 50 Atingido"), (75, "Nível 75 Atingido")):
        if level >= threshold:
            unlocked.append(
                {
                    "id": f"level_{threshold}",
                    "title": title,
                    "icon": "star",
                    "date": None,
                }
            )

    if _all_classes_completed(classes):
        dates = [c["completed_at"] for c in classes if c.get("completed_at")]
        unlocked.append(
            {
                "id": "all_classes",
                "title": "Todas as Classes Concluídas",
                "icon": "trophy",
                "date": max(dates) if dates else None,
            }
        )

    if activities_done >= 100:
        unlocked.append(
            {
                "id": "activities_100",
                "title": "100 Atividades Concluídas",
                "icon": "book",
                "date": None,
            }
        )

    def sort_key(item):
        dt = item.get("date")
        if isinstance(dt, datetime):
            return dt
        if isinstance(dt, date):
            return datetime.combine(dt, datetime.min.time())
        return datetime.min

    unlocked.sort(key=sort_key, reverse=True)
    return unlocked[:limit]


def next_objective(
    member: Member,
    *,
    classes: list[dict],
    level: int,
    sp_summary: dict,
) -> dict:
    """Próximo objetivo gamificado para incentivar evolução."""
    for c in classes:
        if c["percent"] < 100:
            return {
                "headline": f"Concluir a Classe {c['name']}",
                "detail": f"Complete as atividades do caderno {c['name']}.",
                "reward": f"XP para avançar ao Nível {min(MAX_LEVEL, level + 1)}",
                "kind": "class",
                "target_label": c["name"],
            }

    sp_in_progress = int(sp_summary.get("in_progress_count", 0) or 0)
    if sp_in_progress > 0:
        return {
            "headline": "Concluir especialidade em andamento",
            "detail": "Finalize os requisitos da especialidade atual.",
            "reward": f"XP complementar rumo ao Nível {min(MAX_LEVEL, level + 1)}",
            "kind": "specialty",
            "target_label": "Especialidade",
        }

    sp_done = int(sp_summary.get("completed_count", 0) or 0)
    if sp_done < SPECIALTY_TARGET_COUNT:
        return {
            "headline": "Iniciar nova especialidade",
            "detail": f"Conclua cerca de {SPECIALTY_TARGET_COUNT} especialidades para o nível máximo.",
            "reward": f"Rumo ao Nível {min(MAX_LEVEL, level + 1)}",
            "kind": "specialty",
            "target_label": "Nova especialidade",
        }

    if level < MAX_LEVEL:
        return {
            "headline": f"Alcançar o Nível {level + 1}",
            "detail": "Continue participando das atividades do clube.",
            "reward": f"Desbloqueie o título {level_title(level + 1)}",
            "kind": "level",
            "target_label": f"Nível {level + 1}",
        }

    return {
        "headline": "Grande Mestre!",
        "detail": "Todas as metas principais foram alcançadas.",
        "reward": "Jornada completa",
        "kind": "max",
        "target_label": "Nível 100",
    }


def build_parent_progress_page(member: Member, stats: dict) -> dict:
    """Payload completo para a aba Progresso do portal dos pais."""
    try:
        from app.activities_service import ensure_member_notebook

        ensure_member_notebook(member)
    except Exception:
        pass
    try:
        from app.specialties_service import member_progress_summary

        sp_summary = member_progress_summary(member, member.clube_id)
    except Exception:
        sp_summary = {
            "completed_count": stats.get("specialties_completed", 0),
            "global_total": OFFICIAL_SPECIALTY_COUNT,
            "progress_percent": stats.get("specialties_progress_percent", 0),
            "progress_label": stats.get("specialties_progress_label", f"0 / {OFFICIAL_SPECIALTY_COUNT}"),
            "in_progress_count": stats.get("specialties_in_progress", 0),
        }

    xp_data = compute_xp(member, sp_completed=sp_summary.get("completed_count", 0))
    lvl = level_progress(xp_data["total"])
    classes = xp_data["classes"]
    achievements = gamification_achievements(
        member,
        level=lvl["level"],
        classes=classes,
        sp_completed=xp_data["specialties_completed"],
        activities_done=int(stats.get("activities_done", 0) or 0),
    )
    objective = next_objective(
        member,
        classes=classes,
        level=lvl["level"],
        sp_summary=sp_summary,
    )

    sp_total = int(sp_summary.get("global_total") or OFFICIAL_SPECIALTY_COUNT)
    sp_done = int(sp_summary.get("completed_count") or 0)
    sp_pct = round(float(sp_summary.get("progress_percent") or 0))

    all_classes_done = _all_classes_completed(classes)
    next_milestone = None
    for m in JOURNEY_MILESTONES:
        if lvl["level"] < m["level"]:
            next_milestone = m
            break

    return {
        "hero": {
            "level": lvl["level"],
            "level_title": lvl["level_title"],
            "xp": lvl["xp"],
            "xp_level_max": lvl["xp_level_max"],
            "xp_to_next": lvl["xp_to_next"],
            "progress_pct": lvl["progress_pct"],
            "next_level": lvl["next_level"],
            "is_max_level": lvl["is_max_level"],
            "class_label": stats.get("class_label") or member.notebook_current or "Desbravador",
        },
        "xp_sources": {
            "classes": classes,
            "class_xp_total": xp_data["class_xp"],
            "class_xp_max": xp_data["class_xp_max"],
            "all_classes_done": all_classes_done,
            "specialty_xp": xp_data["specialty_xp"],
            "specialty_xp_max": xp_data["specialty_xp_max"],
            "specialties_completed": sp_done,
            "specialties_total": sp_total,
            "specialties_percent": sp_pct,
            "specialties_label": f"{sp_done} / {sp_total}",
            "specialty_target_count": SPECIALTY_TARGET_COUNT,
        },
        "journey": {
            "milestones": journey_map(lvl["level"]),
            "current_level": lvl["level"],
            "next_milestone": next_milestone,
            "next_milestone_xp": (
                xp_for_next_level(next_milestone["level"]) if next_milestone else MAX_TOTAL_XP
            ),
        },
        "achievements": achievements,
        "next_objective": objective,
        "max_level_hint": {
            "requires_all_classes": True,
            "requires_specialty_percent": 10,
            "specialty_target": SPECIALTY_TARGET_COUNT,
        },
    }


def journey_xp_from_stats(stats: dict) -> int:
    """Estimativa de XP quando não há membro disponível (ex.: fallback do dashboard)."""
    notebook_pct = int(stats.get("notebook_pct", 0) or 0)
    sp_done = int(stats.get("specialties_completed", 0) or 0)
    approx_class_xp = round(CLASS_XP_POOL * min(100, notebook_pct) / 100)
    return min(MAX_TOTAL_XP, approx_class_xp + specialty_xp_from_count(sp_done))
