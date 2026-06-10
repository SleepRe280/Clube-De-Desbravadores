"""Cadastro em etapas — novo desbravador (admin)."""
from __future__ import annotations

import json
from datetime import date

from app.models import Member

NOTEBOOK_ACTIVITY_OPTIONS = (
    "Amigo",
    "Companheiro",
    "Pesquisador",
    "Pioneiro",
    "Excursionista",
    "Guia",
    "Clube de líderes",
)


def normalize_cpf_digits(value: str | None) -> str | None:
    if not value:
        return None
    d = "".join(c for c in value if c.isdigit())
    if len(d) != 11:
        return None
    return d


def format_cpf_display(digits: str) -> str:
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _emergency_phone_ok(phone: str) -> bool:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return len(digits) >= 10

MEMBER_STATUS_OPTIONS = (
    ("ativo", "Ativo"),
    ("visitante", "Visitante"),
    ("em_treinamento", "Em treinamento"),
    ("inativo", "Inativo"),
)

SEX_OPTIONS = (
    ("masculino", "Masculino"),
    ("feminino", "Feminino"),
    ("outro", "Outro"),
    ("nao_informado", "Prefiro não informar"),
)

UNIT_ROLE_OPTIONS = (
    ("desbravador", "Desbravador"),
    ("lider", "Líder de unidade"),
    ("secretario_unidade", "Secretário da unidade"),
    ("instrutor", "Instrutor"),
)

BLOOD_TYPES = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Não informado")

WIZARD_STEPS = (
    {"id": "geral", "num": 1, "title": "Informações Gerais", "icon": "👤", "short": "Geral"},
    {"id": "clube", "num": 2, "title": "Informações no Clube", "icon": "🌲", "short": "Clube"},
    {"id": "responsaveis", "num": 3, "title": "Responsáveis", "icon": "👪", "short": "Família"},
    {"id": "endereco", "num": 4, "title": "Endereço", "icon": "📍", "short": "Endereço"},
    {"id": "final", "num": 5, "title": "Finalização", "icon": "✓", "short": "Revisão"},
)

CLUB_UNIT_OPTIONS = (
    "Embaixadoras Reais",
    "Exército do Rei",
)


def unit_options_for_club(clube_id: str | None = None) -> list[str]:
    """Unidades do clube (catálogo em banco ou fallback fixo)."""
    try:
        from app.units_service import unit_options_for_club as _dynamic_units

        return _dynamic_units(clube_id)
    except Exception:
        return list(CLUB_UNIT_OPTIONS)


def parse_guardians_from_form(form) -> list[dict]:
    raw = form.get("guardians_json") or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [
                {
                    "name": (g.get("name") or "").strip(),
                    "relation": (g.get("relation") or "").strip(),
                    "phone": (g.get("phone") or "").strip(),
                    "whatsapp": (g.get("whatsapp") or "").strip(),
                    "email": (g.get("email") or "").strip().lower(),
                }
                for g in data
                if (g.get("name") or "").strip()
            ]
    except (json.JSONDecodeError, TypeError):
        pass
    guardians = []
    for i in range(3):
        name = (form.get(f"guardian_{i}_name") or "").strip()
        if not name:
            continue
        guardians.append(
            {
                "name": name,
                "relation": (form.get(f"guardian_{i}_relation") or "").strip(),
                "phone": (form.get(f"guardian_{i}_phone") or "").strip(),
                "whatsapp": (form.get(f"guardian_{i}_whatsapp") or "").strip(),
                "email": (form.get(f"guardian_{i}_email") or "").strip().lower(),
            }
        )
    return guardians


def guardians_for_member(member: Member | None) -> list[dict]:
    if not member:
        return [{"name": "", "relation": "", "phone": "", "whatsapp": "", "email": ""}]
    if member.guardians_json:
        try:
            data = json.loads(member.guardians_json)
            if isinstance(data, list) and data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    out = []
    if member.father_name:
        out.append(
            {
                "name": member.father_name,
                "relation": "Pai",
                "phone": member.phone or "",
                "whatsapp": "",
                "email": member.email or "",
            }
        )
    if member.mother_name:
        out.append(
            {
                "name": member.mother_name,
                "relation": "Mãe",
                "phone": "",
                "whatsapp": "",
                "email": "",
            }
        )
    if not out:
        out.append({"name": "", "relation": "", "phone": "", "whatsapp": "", "email": ""})
    return out


def member_to_form_dict(member: Member | None) -> dict:
    if not member:
        return {
            "joined_at": date.today().isoformat(),
            "member_status": "ativo",
            "unit_role": "desbravador",
            "guardians": [{"name": "", "relation": "", "phone": "", "whatsapp": "", "email": ""}],
        }
    return {
        "full_name": member.full_name or "",
        "birth_date": member.birth_date.isoformat() if member.birth_date else "",
        "cpf": format_cpf_display(member.cpf) if member.cpf else "",
        "sex": member.sex or "",
        "blood_type": member.blood_type or "",
        "phone": member.phone or "",
        "email": member.email or "",
        "joined_at": member.joined_at.isoformat() if member.joined_at else "",
        "unit": member.unit or "",
        "notebook_current": member.notebook_current or "",
        "unit_role": member.unit_role or "desbravador",
        "member_status": member.member_status or "ativo",
        "address_cep": member.address_cep or "",
        "address_street": member.address_street or "",
        "address_number": member.address_number or "",
        "address_neighborhood": member.address_neighborhood or "",
        "address_city": member.address_city or "",
        "address_state": member.address_state or "",
        "emergency_contact_name": member.emergency_contact_name or "",
        "emergency_contact_phone": member.emergency_contact_phone or "",
        "emergency_relation": member.emergency_relation or "",
        "guardians": guardians_for_member(member),
    }


def apply_wizard_form(m: Member, form, *, member_id_exclude: int | None = None) -> None:
    """Aplica dados do wizard de cadastro ao membro."""
    name = (form.get("full_name") or "").strip()
    if not name:
        raise ValueError("Informe o nome completo do desbravador.")

    bd_raw = (form.get("birth_date") or "").strip()
    if not bd_raw:
        raise ValueError("Informe a data de nascimento.")
    try:
        m.birth_date = date.fromisoformat(bd_raw)
    except ValueError:
        raise ValueError("Data de nascimento inválida.")

    cpf_field = (form.get("cpf") or "").strip()
    if cpf_field:
        cpf_raw = normalize_cpf_digits(cpf_field)
        if not cpf_raw:
            raise ValueError("CPF inválido.")
        from app.extensions import db

        q = Member.query.filter(Member.cpf == cpf_raw)
        if m.clube_id:
            q = q.filter(Member.clube_id == m.clube_id)
        if member_id_exclude:
            q = q.filter(Member.id != member_id_exclude)
        if q.first():
            raise ValueError("CPF já cadastrado para outro desbravador.")
        m.cpf = cpf_raw
    else:
        m.cpf = None

    blood = (form.get("blood_type") or "").strip()
    if not blood:
        raise ValueError("Selecione o tipo sanguíneo.")
    m.blood_type = blood

    sex = (form.get("sex") or "").strip()
    if not sex:
        raise ValueError("Selecione o sexo.")
    m.sex = sex
    m.phone = (form.get("phone") or "").strip() or None
    m.email = (form.get("email") or "").strip().lower() or None

    joined_raw = (form.get("joined_at") or "").strip()
    if joined_raw:
        try:
            m.joined_at = date.fromisoformat(joined_raw)
        except ValueError:
            raise ValueError("Data de entrada no clube inválida.")
    elif not m.joined_at:
        m.joined_at = date.today()

    unit = (form.get("unit") or "").strip()
    if not unit:
        raise ValueError("Selecione a unidade do desbravador.")
    if unit not in CLUB_UNIT_OPTIONS:
        raise ValueError("Unidade inválida. Escolha Embaixadoras Reais ou Exército do Rei.")
    m.unit = unit

    nb = (form.get("notebook_current") or "").strip()
    allowed = set(NOTEBOOK_ACTIVITY_OPTIONS)
    if member_id_exclude:
        from app.extensions import db

        existing = db.session.get(Member, member_id_exclude)
        if existing and existing.notebook_current:
            allowed.add(existing.notebook_current.strip())
    if not nb or nb not in allowed:
        raise ValueError("Selecione a classe/caderno atual.")
    m.notebook_current = nb

    m.unit_role = (form.get("unit_role") or "desbravador").strip() or "desbravador"
    status = (form.get("member_status") or "ativo").strip()
    if status not in {s[0] for s in MEMBER_STATUS_OPTIONS}:
        raise ValueError("Status do membro inválido.")
    m.member_status = status

    guardians = parse_guardians_from_form(form)
    if not guardians:
        raise ValueError("Informe ao menos um responsável.")
    m.guardians_json = json.dumps(guardians, ensure_ascii=False)

    m.father_name = guardians[0]["name"] if guardians else None
    m.mother_name = guardians[1]["name"] if len(guardians) > 1 else None

    em_name = (form.get("emergency_contact_name") or "").strip()
    em_phone = (form.get("emergency_contact_phone") or "").strip()
    if not em_name:
        raise ValueError("Informe o nome do contato de emergência.")
    if not em_phone or not _emergency_phone_ok(em_phone):
        raise ValueError("Telefone de emergência inválido (mínimo 10 dígitos).")
    m.emergency_contact_name = em_name
    m.emergency_contact_phone = em_phone
    m.emergency_relation = (form.get("emergency_relation") or "").strip() or "Contato de emergência"

    m.address_cep = (form.get("address_cep") or "").strip() or None
    m.address_street = (form.get("address_street") or "").strip() or None
    m.address_number = (form.get("address_number") or "").strip() or None
    m.address_neighborhood = (form.get("address_neighborhood") or "").strip() or None
    m.address_city = (form.get("address_city") or "").strip() or None
    m.address_state = ((form.get("address_state") or "").strip().upper()[:2] or None)

    m.full_name = name
    m.overall_performance = m.computed_overall_performance()


def wizard_context(member: Member | None, *, clube_id: str | None = None, **extra) -> dict:
    opts = list(NOTEBOOK_ACTIVITY_OPTIONS)
    if member and member.notebook_current and member.notebook_current not in opts:
        opts = [member.notebook_current] + opts
    form_data = member_to_form_dict(member)
    cid = clube_id or (member.clube_id if member else None)
    ctx = {
        "wizard_steps": WIZARD_STEPS,
        "notebook_options": opts,
        "unit_options": unit_options_for_club(cid),
        "status_options": MEMBER_STATUS_OPTIONS,
        "sex_options": SEX_OPTIONS,
        "unit_role_options": UNIT_ROLE_OPTIONS,
        "blood_types": BLOOD_TYPES,
        "form_data": form_data,
        "is_edit": member is not None,
    }
    ctx.update(extra)
    return ctx
