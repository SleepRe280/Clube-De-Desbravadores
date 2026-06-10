"""Vínculo desbravador ↔ responsável (cadastro no site + gestão em /admin/responsaveis)."""
from __future__ import annotations

import json
from datetime import datetime

from flask import flash
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.access import cargos_for_profile
from app.extensions import db
from app.models import (
    CARGO_CONSELHEIRO,
    CARGO_DIRETOR,
    CARGO_PAI,
    CARGO_SECRETARIO,
    CARGO_SUPER_ADMIN,
    CARGO_TESOUREIRO,
    BoardPost,
    LINK_TYPE_PAI,
    PARENT_LINK_TYPES,
    Member,
    ParentLinkHistory,
    PasswordResetToken,
    Profile,
    User,
)

def normalize_link_type(raw: str | None) -> str:
    token = (raw or "").strip().lower()
    valid = {code for code, _ in PARENT_LINK_TYPES}
    return token if token in valid else LINK_TYPE_PAI


def record_link_history(
    *,
    member: Member,
    parent: User | None,
    action: str,
    link_type: str | None = None,
    performed_by: User | None = None,
) -> None:
    row = ParentLinkHistory(
        clube_id=member.clube_id,
        member_id=member.id,
        parent_user_id=parent.id if parent else None,
        action=action,
        link_type=link_type,
        performed_by_id=performed_by.id if performed_by else None,
        parent_name_snapshot=(parent.full_name or parent.email) if parent else None,
        member_name_snapshot=member.full_name,
    )
    db.session.add(row)


_LEADERSHIP_CARGOS = frozenset(
    {
        CARGO_SUPER_ADMIN,
        CARGO_DIRETOR,
        CARGO_SECRETARIO,
        CARGO_TESOUREIRO,
        CARGO_CONSELHEIRO,
    }
)


def portal_children_for_user(user: User, member_id: int | None = None) -> tuple[Member | None, list[Member]]:
    """Filho ativo + lista — consulta direta ao banco."""
    children = children_for_parent(user.id)
    if not children:
        return None, []
    if member_id:
        for c in children:
            if c.id == member_id:
                return c, children
    return children[0], children


def children_for_parent(user_id: int) -> list[Member]:
    """Filhos vinculados via Member.parent_id."""
    return (
        Member.query.filter_by(parent_id=user_id)
        .order_by(Member.full_name.asc(), Member.id.asc())
        .all()
    )


def parent_has_children(user: User | None) -> bool:
    if not user or not getattr(user, "id", None):
        return False
    return (
        db.session.query(Member.id).filter_by(parent_id=user.id).limit(1).first()
        is not None
    )


def _user_is_super_admin(user: User) -> bool:
    profile = db.session.get(Profile, user.id)
    return CARGO_SUPER_ADMIN in cargos_for_profile(profile)


def is_registered_parent_account(user: User | None) -> bool:
    """Conta criada pelo cadastro do site como responsável (não liderança)."""
    if not user or user.role != "parent":
        return False
    if _user_is_super_admin(user):
        return False
    profile = db.session.get(Profile, user.id)
    cargos = cargos_for_profile(profile)
    if cargos & _LEADERSHIP_CARGOS:
        return False
    return True


def _merge_cargo_pai(profile: Profile) -> None:
    cargos = cargos_for_profile(profile)
    if CARGO_PAI in cargos:
        return
    cargos.add(CARGO_PAI)
    if not profile.cargo or profile.cargo == CARGO_PAI:
        profile.cargo = CARGO_PAI
    profile.cargos_json = json.dumps(sorted(cargos))


def sync_parent_profile_clube(parent: User, member: Member) -> None:
    """Alinha perfil do responsável ao clube do desbravador após vínculo."""
    if not member or not getattr(member, "clube_id", None):
        return
    profile = db.session.get(Profile, parent.id)
    if not profile:
        profile = Profile(id=parent.id, cargo=CARGO_PAI, clube_id=member.clube_id)
        db.session.add(profile)
    if not profile.clube_id:
        profile.clube_id = member.clube_id
    _merge_cargo_pai(profile)


def find_parent_user_for_link(
    *,
    user_id: int | None = None,
    email: str | None = None,
) -> User | None:
    """Localiza conta de responsável já cadastrada no site."""
    user: User | None = None
    if user_id:
        user = db.session.get(User, user_id)
    elif email:
        user = User.query.filter_by(email=(email or "").strip().lower()).first()
    if not user or not is_registered_parent_account(user):
        return None
    return user


def link_member_to_parent(
    member: Member,
    parent: User,
    *,
    link_type: str | None = None,
    performed_by: User | None = None,
    allow_reassign: bool = False,
) -> str | None:
    """
    Vincula desbravador do clube à conta de responsável cadastrada no site.
    Única forma do filho aparecer em /pais/.
    """
    if not member or not parent:
        return "Dados inválidos."
    if not is_registered_parent_account(parent):
        return (
            "Esta conta não é de responsável cadastrado no site. "
            "Peça para criar conta em «Criar conta» e depois vincule aqui."
        )
    if not getattr(member, "clube_id", None):
        return "Cadastre o desbravador em um clube antes de vincular."

    profile = db.session.get(Profile, parent.id)
    if profile and profile.clube_id and profile.clube_id != member.clube_id:
        return "Este responsável está cadastrado em outro clube."

    if member.parent_id is not None and member.parent_id != parent.id:
        if not allow_reassign:
            return "Este desbravador já está vinculado a outro responsável."
        unlink_member_from_parent(member, member.parent_id, performed_by=performed_by)
    elif member.parent_id == parent.id:
        return change_member_link_type(
            member, link_type, performed_by=performed_by
        )

    member.parent_id = parent.id
    member.parent_link_type = normalize_link_type(link_type)
    member.parent_linked_at = datetime.utcnow()
    sync_parent_profile_clube(parent, member)
    record_link_history(
        member=member,
        parent=parent,
        action="link",
        link_type=member.parent_link_type,
        performed_by=performed_by,
    )
    db.session.flush()
    stored = (
        db.session.query(Member.parent_id).filter(Member.id == member.id).scalar()
    )
    if stored != parent.id:
        return "Não foi possível gravar o vínculo. Tente novamente."
    return None


def change_member_link_type(
    member: Member,
    link_type: str | None,
    *,
    performed_by: User | None = None,
) -> str | None:
    """Atualiza o tipo de vínculo (pai, mãe, tutor…) sem trocar o responsável."""
    if not member or not member.parent_id:
        return "Desbravador sem responsável vinculado."
    parent = db.session.get(User, member.parent_id)
    if not parent:
        return "Responsável vinculado não encontrado."
    new_type = normalize_link_type(link_type)
    if member.parent_link_type == new_type:
        return None
    member.parent_link_type = new_type
    record_link_history(
        member=member,
        parent=parent,
        action="link",
        link_type=new_type,
        performed_by=performed_by,
    )
    return None


def transfer_member_to_parent(
    member: Member,
    new_parent: User,
    *,
    link_type: str | None = None,
    performed_by: User | None = None,
) -> str | None:
    """Transfere o desbravador para outro responsável (desvincula o anterior)."""
    return link_member_to_parent(
        member,
        new_parent,
        link_type=link_type,
        performed_by=performed_by,
        allow_reassign=True,
    )


def unlink_member_from_parent(
    member: Member,
    parent_id: int,
    *,
    performed_by: User | None = None,
) -> bool:
    if member.parent_id == parent_id:
        parent = db.session.get(User, parent_id)
        link_type = member.parent_link_type
        member.parent_id = None
        member.parent_link_type = None
        member.parent_linked_at = None
        record_link_history(
            member=member,
            parent=parent,
            action="unlink",
            link_type=link_type,
            performed_by=performed_by,
        )
        return True
    return False


def delete_parent_account(user: User, *, club_id: str | None = None) -> str | None:
    """Remove conta de responsável; desbravadores permanecem sem vínculo."""
    if not is_registered_parent_account(user):
        return "Esta conta não é de responsável do portal família."
    try:
        with db.session.begin_nested():
            db.session.execute(
                text("DELETE FROM email_confirmation_tokens WHERE user_id = :uid"),
                {"uid": user.id},
            )
    except Exception:
        pass
    mq = Member.query.filter_by(parent_id=user.id)
    if club_id:
        mq = mq.filter(Member.clube_id == club_id)
    for m in mq.all():
        m.parent_id = None
    if club_id:
        BoardPost.query.filter_by(author_id=user.id, clube_id=club_id).update(
            {BoardPost.author_id: None}, synchronize_session=False
        )
    else:
        BoardPost.query.filter_by(author_id=user.id).update(
            {BoardPost.author_id: None}, synchronize_session=False
        )
    PasswordResetToken.query.filter_by(user_id=user.id).delete()
    profile = db.session.get(Profile, user.id)
    if profile:
        db.session.delete(profile)
    db.session.delete(user)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return "Não foi possível excluir: ainda há registros ligados a esta conta."
    return None


def purge_all_parent_accounts() -> dict[str, int]:
    """Apaga todas as contas role=parent e limpa vínculos (manutenção)."""
    n_links = (
        Member.query.filter(Member.parent_id.isnot(None))
        .update({Member.parent_id: None}, synchronize_session=False)
    )
    parents = User.query.filter(User.role == "parent").all()
    deleted = 0
    errors = 0
    for p in list(parents):
        err = delete_parent_account(p)
        if err:
            errors += 1
        else:
            deleted += 1
    db.session.commit()
    return {"links_cleared": n_links, "accounts_deleted": deleted, "errors": errors}


def link_summary_message(member: Member, parent: User) -> str:
    return (
        f"{parent.email} verá {member.full_name} em /pais/ após entrar com este e-mail."
    )
