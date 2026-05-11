"""Adiciona colunas em bancos SQLite já existentes (create_all não altera tabelas)."""

import json
from datetime import datetime

from sqlalchemy import inspect, text

from app.extensions import db


def _coerce_sqlite_datetime(val):
    """SQLite devolve DATETIME como str em alguns drivers; SQLAlchemy exige datetime."""
    if val is None:
        return datetime.utcnow()
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def _table_columns(engine, table: str) -> set:
    insp = inspect(engine)
    try:
        return {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return set()


def migrate_sqlite_schema(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if "sqlite" not in uri:
        return

    engine = db.engine
    perfil_cols = _table_columns(engine, "perfis")
    if "cargos_json" not in perfil_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE perfis ADD COLUMN cargos_json TEXT"))
            conn.commit()

    member_cols = _table_columns(engine, "members")
    for col, ddl in [
        ("cpf", "VARCHAR(14)"),
        ("blood_type", "VARCHAR(8)"),
        ("father_name", "VARCHAR(120)"),
        ("mother_name", "VARCHAR(120)"),
        ("emergency_contact_name", "VARCHAR(120)"),
        ("emergency_contact_phone", "VARCHAR(40)"),
        ("notebook_current", "VARCHAR(200)"),
        ("overall_performance", "INTEGER DEFAULT 0"),
        ("photo_filename", "VARCHAR(200)"),
        ("activities_30_json", "TEXT"),
        ("notebook_checklist_30_json", "TEXT"),
    ]:
        if col not in member_cols:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE members ADD COLUMN {col} {ddl}"))
                conn.commit()
            member_cols.add(col)

    act_cols = _table_columns(engine, "activity_records")
    if "completed" not in act_cols:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE activity_records ADD COLUMN completed INTEGER DEFAULT 0"
                )
            )
            conn.commit()


def ensure_multiclub_scope_columns(app):
    """Adiciona colunas de escopo por clube (SQLite e PostgreSQL)."""
    engine = db.engine
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    is_sqlite = "sqlite" in uri

    def add_column(table: str, col: str, sqlite_ddl: str, pg_ddl: str) -> None:
        cols = _table_columns(engine, table)
        if col in cols:
            return
        ddl = sqlite_ddl if is_sqlite else pg_ddl
        with engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()

    add_column(
        "clubes",
        "descricao",
        "ALTER TABLE clubes ADD COLUMN descricao TEXT",
        "ALTER TABLE clubes ADD COLUMN descricao TEXT",
    )
    add_column(
        "members",
        "clube_id",
        "ALTER TABLE members ADD COLUMN clube_id VARCHAR(36)",
        "ALTER TABLE members ADD COLUMN clube_id VARCHAR(36)",
    )
    add_column(
        "agenda_events",
        "clube_id",
        "ALTER TABLE agenda_events ADD COLUMN clube_id VARCHAR(36)",
        "ALTER TABLE agenda_events ADD COLUMN clube_id VARCHAR(36)",
    )
    add_column(
        "board_posts",
        "clube_id",
        "ALTER TABLE board_posts ADD COLUMN clube_id VARCHAR(36)",
        "ALTER TABLE board_posts ADD COLUMN clube_id VARCHAR(36)",
    )
    add_column(
        "board_posts",
        "post_kind",
        "ALTER TABLE board_posts ADD COLUMN post_kind VARCHAR(20) NOT NULL DEFAULT 'comunicado'",
        "ALTER TABLE board_posts ADD COLUMN post_kind VARCHAR(20) NOT NULL DEFAULT 'comunicado'",
    )
    add_column(
        "board_posts",
        "level",
        "ALTER TABLE board_posts ADD COLUMN level VARCHAR(20)",
        "ALTER TABLE board_posts ADD COLUMN level VARCHAR(20)",
    )
    add_column(
        "board_posts",
        "image_filename",
        "ALTER TABLE board_posts ADD COLUMN image_filename VARCHAR(200)",
        "ALTER TABLE board_posts ADD COLUMN image_filename VARCHAR(200)",
    )
    add_column(
        "directorate_members",
        "clube_id",
        "ALTER TABLE directorate_members ADD COLUMN clube_id VARCHAR(36)",
        "ALTER TABLE directorate_members ADD COLUMN clube_id VARCHAR(36)",
    )
    add_column(
        "finance_ledger",
        "clube_id",
        "ALTER TABLE finance_ledger ADD COLUMN clube_id VARCHAR(36)",
        "ALTER TABLE finance_ledger ADD COLUMN clube_id VARCHAR(36)",
    )


def merge_club_news_into_board_posts(app):
    """Migra dados legados de club_news para board_posts e remove a tabela antiga."""
    from sqlalchemy import inspect

    from app.models import POST_KIND_NOTICIA, BoardPost

    insp = inspect(db.engine)
    if "club_news" not in insp.get_table_names():
        return

    engine = db.engine
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT clube_id, title, body, level, image_filename, created_at, author_id "
                "FROM club_news"
            )
        ).mappings().all()

    for r in rows:
        db.session.add(
            BoardPost(
                clube_id=r["clube_id"],
                title=r["title"] or "",
                body=r["body"] or "",
                post_kind=POST_KIND_NOTICIA,
                level=(r["level"] or "local").strip() or "local",
                image_filename=r["image_filename"],
                created_at=_coerce_sqlite_datetime(r["created_at"]),
                author_id=r["author_id"],
            )
        )
    db.session.commit()

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE club_news"))
        conn.commit()


def backfill_clube_scope_data(app):
    """Preenche clube_id nulo com o clube padrão e propaga para lançamentos."""
    from app.models import (
        AgendaEvent,
        BoardPost,
        Club,
        DirectorateMember,
        FinanceLedgerEntry,
        Member,
    )

    default_club = Club.query.filter_by(template_slug="duque_de_caxias").first()
    if not default_club:
        return
    cid = default_club.id
    Member.query.filter(Member.clube_id.is_(None)).update({Member.clube_id: cid}, synchronize_session=False)
    AgendaEvent.query.filter(AgendaEvent.clube_id.is_(None)).update(
        {AgendaEvent.clube_id: cid}, synchronize_session=False
    )
    BoardPost.query.filter(BoardPost.clube_id.is_(None)).update(
        {BoardPost.clube_id: cid}, synchronize_session=False
    )
    DirectorateMember.query.filter(DirectorateMember.clube_id.is_(None)).update(
        {DirectorateMember.clube_id: cid}, synchronize_session=False
    )
    for row in FinanceLedgerEntry.query.filter(FinanceLedgerEntry.clube_id.is_(None)).all():
        if row.member_id:
            m = db.session.get(Member, row.member_id)
            row.clube_id = m.clube_id if m and m.clube_id else cid
        else:
            row.clube_id = cid
    db.session.commit()


def ensure_users_email_verified_column(app):
    """Adiciona users.email_verified em bancos já existentes (SQLite ou PostgreSQL)."""
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    engine = db.engine
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("users")}
    except Exception:
        return
    if "email_verified" in cols:
        return
    if "sqlite" in uri:
        ddl = "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1"
    else:
        ddl = "ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT TRUE"
    with engine.connect() as conn:
        conn.execute(text(ddl))
        conn.commit()


def ensure_default_club_and_profiles(app):
    """
    Cria clube-base e backfill de perfis para usuários existentes.

    Esta etapa prepara a estrutura de hierarquia/multi-clube sem quebrar o fluxo atual.
    """
    from app.models import (
        CARGO_CONSELHEIRO,
        CARGO_DIRETOR,
        CARGO_PAI,
        CARGO_SECRETARIO,
        CARGO_SUPER_ADMIN,
        CARGO_TESOUREIRO,
        Club,
        Profile,
        User,
    )

    default_club = Club.query.filter_by(template_slug="duque_de_caxias").first()
    if not default_club:
        default_club = Club(
            nome="Clube de Desbravadores",
            titulo_sistema="Portal do Clube de Desbravadores",
            template_slug="duque_de_caxias",
            cor_primaria="#003580",
            cor_secundaria="#FFD700",
            cor_accent="#CC0000",
            brasao_url="/static/img/brasao-desbravadores-oficial.png",
            criado_em=datetime.utcnow(),
        )
        db.session.add(default_club)
        db.session.flush()
    else:
        # IMPORTANTE: não sobrescrever personalizações feitas no painel.
        # Apenas faz backfill de campos vazios em bases legadas.
        if not (default_club.nome or "").strip():
            default_club.nome = "Clube de Desbravadores"
        if not (default_club.titulo_sistema or "").strip():
            default_club.titulo_sistema = "Portal do Clube de Desbravadores"
        if not (default_club.brasao_url or "").strip():
            default_club.brasao_url = "/static/img/brasao-desbravadores-oficial.png"
        if not (default_club.cor_primaria or "").strip():
            default_club.cor_primaria = "#003580"
        if not (default_club.cor_secundaria or "").strip():
            default_club.cor_secundaria = "#FFD700"
        if not (default_club.cor_accent or "").strip():
            default_club.cor_accent = "#CC0000"

    users = User.query.all()
    for user in users:
        profile = db.session.get(Profile, user.id)
        if profile is None:
            profile = Profile(id=user.id)
            db.session.add(profile)

        if not profile.nome_completo:
            profile.nome_completo = user.full_name
        profile.email_verificado = bool(user.email_verified)
        if user.role == "admin" and profile.cargo not in (
            CARGO_SUPER_ADMIN,
            CARGO_DIRETOR,
            CARGO_TESOUREIRO,
            CARGO_SECRETARIO,
            CARGO_CONSELHEIRO,
        ):
            profile.cargo = CARGO_DIRETOR
        elif not profile.cargo:
            profile.cargo = CARGO_PAI
        if profile.cargo == CARGO_SUPER_ADMIN:
            profile.clube_id = None
        elif not profile.clube_id:
            profile.clube_id = default_club.id
        if not profile.cargos_json and profile.cargo:
            profile.cargos_json = json.dumps([profile.cargo])

    db.session.commit()


def ensure_leadership_accounts_admin_role(app):
    """Contas com cargo de liderança no clube passam a role admin (deixam de listar como só responsáveis)."""
    from app.models import (
        CARGO_CONSELHEIRO,
        CARGO_DIRETOR,
        CARGO_SECRETARIO,
        CARGO_TESOUREIRO,
        Profile,
        User,
    )

    leadership = {CARGO_DIRETOR}
    changed = False
    for profile in Profile.query.all():
        user = db.session.get(User, profile.id)
        if not user or user.role != "parent":
            continue
        if profile.cargo in leadership:
            user.role = "admin"
            changed = True
            continue
        raw = profile.cargos_json
        if not raw:
            continue
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                continue
            codes = {str(x).strip() for x in data if str(x).strip()}
            if codes & leadership:
                user.role = "admin"
                changed = True
        except Exception:
            continue
    if changed:
        db.session.commit()


def normalize_profile_roles(app):
    """Normaliza cargos legados para os códigos canônicos e corrige role do usuário."""
    from app.models import (
        CARGO_CONSELHEIRO,
        CARGO_DIRETOR,
        CARGO_PAI,
        CARGO_SECRETARIO,
        CARGO_SUPER_ADMIN,
        CARGO_TESOUREIRO,
        Profile,
        User,
    )

    aliases = {
        "diretor(a)": CARGO_DIRETOR,
        "diretora": CARGO_DIRETOR,
        "tesouraria": CARGO_TESOUREIRO,
        "tesoureiro(a)": CARGO_TESOUREIRO,
        "secretaria": CARGO_SECRETARIO,
        "secretário": CARGO_SECRETARIO,
        "secretaria(a)": CARGO_SECRETARIO,
        "conselheiros": CARGO_CONSELHEIRO,
        "conselheiro(a)": CARGO_CONSELHEIRO,
        "responsavel": CARGO_PAI,
        "responsável": CARGO_PAI,
    }
    leadership = {CARGO_DIRETOR}
    valid = leadership | {CARGO_SUPER_ADMIN, CARGO_PAI}

    changed = False
    for profile in Profile.query.all():
        user = db.session.get(User, profile.id)
        if not user:
            continue

        raw_cargo = (profile.cargo or "").strip().lower()
        norm_cargo = aliases.get(raw_cargo, raw_cargo)
        if norm_cargo and norm_cargo in valid and profile.cargo != norm_cargo:
            profile.cargo = norm_cargo
            changed = True

        roles = set()
        raw_json = getattr(profile, "cargos_json", None)
        if raw_json:
            try:
                data = json.loads(raw_json)
                if isinstance(data, list):
                    for item in data:
                        token = aliases.get(str(item).strip().lower(), str(item).strip().lower())
                        if token in valid:
                            roles.add(token)
            except Exception:
                roles = set()

        if not roles and profile.cargo in valid:
            roles = {profile.cargo}
        if not roles:
            roles = {CARGO_DIRETOR} if user.role == "admin" else {CARGO_PAI}

        # Garante coerência do cargo principal.
        if CARGO_SUPER_ADMIN in roles:
            main = CARGO_SUPER_ADMIN
            profile.clube_id = None
        elif CARGO_DIRETOR in roles:
            main = CARGO_DIRETOR
        elif CARGO_SECRETARIO in roles:
            main = CARGO_SECRETARIO
        elif CARGO_TESOUREIRO in roles:
            main = CARGO_TESOUREIRO
        elif CARGO_CONSELHEIRO in roles:
            main = CARGO_CONSELHEIRO
        else:
            main = CARGO_PAI

        if profile.cargo != main:
            profile.cargo = main
            changed = True
        normalized_json = json.dumps(sorted(roles))
        if profile.cargos_json != normalized_json:
            profile.cargos_json = normalized_json
            changed = True

        expected_role = "admin" if (roles & leadership or CARGO_SUPER_ADMIN in roles) else "parent"
        if user.role != expected_role:
            user.role = expected_role
            changed = True

    if changed:
        db.session.commit()
