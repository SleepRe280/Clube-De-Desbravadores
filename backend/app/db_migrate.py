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
    if "parent_id" not in member_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE members ADD COLUMN parent_id INTEGER"))
            conn.commit()
        member_cols.add("parent_id")
    for col, ddl in [
        ("cpf", "VARCHAR(14)"),
        ("blood_type", "VARCHAR(8)"),
        ("sex", "VARCHAR(20)"),
        ("phone", "VARCHAR(40)"),
        ("email", "VARCHAR(120)"),
        ("joined_at", "DATE"),
        ("unit_role", "VARCHAR(80)"),
        ("member_status", "VARCHAR(30)"),
        ("address_cep", "VARCHAR(12)"),
        ("address_street", "VARCHAR(200)"),
        ("address_number", "VARCHAR(20)"),
        ("address_neighborhood", "VARCHAR(120)"),
        ("address_city", "VARCHAR(120)"),
        ("address_state", "VARCHAR(2)"),
        ("guardians_json", "TEXT"),
        ("emergency_relation", "VARCHAR(60)"),
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

    att_cols = _table_columns(engine, "attendances")
    if "status" not in att_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE attendances ADD COLUMN status VARCHAR(20)"))
            conn.commit()
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE attendances SET status = 'presente' WHERE present = 1 OR present IS NULL"
                )
            )
            conn.execute(
                text("UPDATE attendances SET status = 'falta' WHERE present = 0")
            )
            conn.commit()

    ensure_agenda_events_columns(app)


def ensure_parent_link_schema(app):
    """Colunas de vínculo responsável + histórico + last_seen."""
    engine = db.engine
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    is_sqlite = "sqlite" in uri

    user_cols = _table_columns(engine, "users")
    if "last_seen_at" not in user_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_seen_at DATETIME"))
            conn.commit()

    perfil_cols = _table_columns(engine, "perfis")
    if "phone" not in perfil_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE perfis ADD COLUMN phone VARCHAR(40)"))
            conn.commit()

    member_cols = _table_columns(engine, "members")
    for col, ddl in [
        ("parent_link_type", "VARCHAR(40)"),
        ("parent_linked_at", "DATETIME"),
    ]:
        if col not in member_cols:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE members ADD COLUMN {col} {ddl}"))
                conn.commit()

    insp = inspect(engine)
    if "parent_link_history" not in insp.get_table_names():
        with engine.connect() as conn:
            if is_sqlite:
                conn.execute(
                    text(
                        """
                        CREATE TABLE parent_link_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            clube_id VARCHAR(36),
                            member_id INTEGER NOT NULL,
                            parent_user_id INTEGER,
                            action VARCHAR(20) NOT NULL,
                            link_type VARCHAR(40),
                            performed_by_id INTEGER,
                            parent_name_snapshot VARCHAR(120),
                            member_name_snapshot VARCHAR(120),
                            created_at DATETIME NOT NULL,
                            FOREIGN KEY (clube_id) REFERENCES clubes (id),
                            FOREIGN KEY (member_id) REFERENCES members (id),
                            FOREIGN KEY (parent_user_id) REFERENCES users (id),
                            FOREIGN KEY (performed_by_id) REFERENCES users (id)
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE parent_link_history (
                            id SERIAL PRIMARY KEY,
                            clube_id VARCHAR(36) REFERENCES clubes(id),
                            member_id INTEGER NOT NULL REFERENCES members(id),
                            parent_user_id INTEGER REFERENCES users(id),
                            action VARCHAR(20) NOT NULL,
                            link_type VARCHAR(40),
                            performed_by_id INTEGER REFERENCES users(id),
                            parent_name_snapshot VARCHAR(120),
                            member_name_snapshot VARCHAR(120),
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
            conn.commit()


def ensure_agenda_events_columns(app):
    """Colunas premium da agenda + tabela de confirmações."""
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

    for col, sqlite_ddl, pg_ddl in [
        ("category", "VARCHAR(40)", "VARCHAR(40)"),
        ("location", "VARCHAR(200)", "VARCHAR(200)"),
        ("unit", "VARCHAR(80)", "VARCHAR(80)"),
        ("status", "VARCHAR(30)", "VARCHAR(30)"),
        ("banner_filename", "VARCHAR(200)", "VARCHAR(200)"),
        ("max_capacity", "INTEGER", "INTEGER"),
        ("responsible_name", "VARCHAR(120)", "VARCHAR(120)"),
        ("event_end_date", "DATE", "DATE"),
        ("event_end_time", "VARCHAR(8)", "VARCHAR(8)"),
        ("color_hex", "VARCHAR(7)", "VARCHAR(7)"),
        ("meta_json", "TEXT", "TEXT"),
    ]:
        add_column(
            "agenda_events",
            col,
            f"ALTER TABLE agenda_events ADD COLUMN {col} {sqlite_ddl}",
            f"ALTER TABLE agenda_events ADD COLUMN {col} {pg_ddl}",
        )

    insp = inspect(engine)
    if "agenda_event_rsvps" not in insp.get_table_names():
        with engine.connect() as conn:
            if is_sqlite:
                conn.execute(
                    text(
                        """
                        CREATE TABLE agenda_event_rsvps (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            member_id INTEGER,
                            status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(event_id) REFERENCES agenda_events(id),
                            FOREIGN KEY(user_id) REFERENCES users(id),
                            FOREIGN KEY(member_id) REFERENCES members(id)
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE agenda_event_rsvps (
                            id SERIAL PRIMARY KEY,
                            event_id INTEGER NOT NULL REFERENCES agenda_events(id),
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            member_id INTEGER REFERENCES members(id),
                            status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
                            created_at TIMESTAMP,
                            updated_at TIMESTAMP
                        )
                        """
                    )
                )
            conn.commit()

    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE agenda_events SET category = 'reuniao' WHERE category IS NULL OR category = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE agenda_events SET status = 'planejado' WHERE status IS NULL OR status = ''"
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
        "board_posts",
        "category",
        "ALTER TABLE board_posts ADD COLUMN category VARCHAR(30) DEFAULT 'aviso'",
        "ALTER TABLE board_posts ADD COLUMN category VARCHAR(30) DEFAULT 'aviso'",
    )
    add_column(
        "board_posts",
        "attachment_filename",
        "ALTER TABLE board_posts ADD COLUMN attachment_filename VARCHAR(200)",
        "ALTER TABLE board_posts ADD COLUMN attachment_filename VARCHAR(200)",
    )
    add_column(
        "board_posts",
        "event_date",
        "ALTER TABLE board_posts ADD COLUMN event_date DATE",
        "ALTER TABLE board_posts ADD COLUMN event_date DATE",
    )
    add_column(
        "board_posts",
        "event_time",
        "ALTER TABLE board_posts ADD COLUMN event_time VARCHAR(8)",
        "ALTER TABLE board_posts ADD COLUMN event_time VARCHAR(8)",
    )
    add_column(
        "board_posts",
        "location",
        "ALTER TABLE board_posts ADD COLUMN location VARCHAR(200)",
        "ALTER TABLE board_posts ADD COLUMN location VARCHAR(200)",
    )
    add_column(
        "board_posts",
        "is_featured",
        "ALTER TABLE board_posts ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE board_posts ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT FALSE",
    )
    add_column(
        "board_posts",
        "is_urgent",
        "ALTER TABLE board_posts ADD COLUMN is_urgent BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE board_posts ADD COLUMN is_urgent BOOLEAN NOT NULL DEFAULT FALSE",
    )
    add_column(
        "board_posts",
        "audience_json",
        "ALTER TABLE board_posts ADD COLUMN audience_json TEXT",
        "ALTER TABLE board_posts ADD COLUMN audience_json TEXT",
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
    ensure_finance_premium_columns(app)


def ensure_finance_premium_columns(app):
    """Colunas e tabelas do módulo financeiro premium."""
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
        "finance_ledger",
        "notes",
        "ALTER TABLE finance_ledger ADD COLUMN notes TEXT",
        "ALTER TABLE finance_ledger ADD COLUMN notes TEXT",
    )
    add_column(
        "finance_ledger",
        "attachment_filename",
        "ALTER TABLE finance_ledger ADD COLUMN attachment_filename VARCHAR(200)",
        "ALTER TABLE finance_ledger ADD COLUMN attachment_filename VARCHAR(200)",
    )
    add_column(
        "finance_ledger",
        "created_by_id",
        "ALTER TABLE finance_ledger ADD COLUMN created_by_id INTEGER",
        "ALTER TABLE finance_ledger ADD COLUMN created_by_id INTEGER",
    )
    add_column(
        "finance_ledger",
        "member_fee_id",
        "ALTER TABLE finance_ledger ADD COLUMN member_fee_id INTEGER",
        "ALTER TABLE finance_ledger ADD COLUMN member_fee_id INTEGER",
    )
    add_column(
        "member_fees",
        "category",
        "ALTER TABLE member_fees ADD COLUMN category VARCHAR(40) DEFAULT 'mensalidade'",
        "ALTER TABLE member_fees ADD COLUMN category VARCHAR(40) DEFAULT 'mensalidade'",
    )
    add_column(
        "member_fees",
        "discount_cents",
        "ALTER TABLE member_fees ADD COLUMN discount_cents INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE member_fees ADD COLUMN discount_cents INTEGER NOT NULL DEFAULT 0",
    )
    add_column(
        "member_fees",
        "fine_cents",
        "ALTER TABLE member_fees ADD COLUMN fine_cents INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE member_fees ADD COLUMN fine_cents INTEGER NOT NULL DEFAULT 0",
    )
    add_column(
        "member_fees",
        "status",
        "ALTER TABLE member_fees ADD COLUMN status VARCHAR(20)",
        "ALTER TABLE member_fees ADD COLUMN status VARCHAR(20)",
    )
    add_column(
        "member_fees",
        "installment_group",
        "ALTER TABLE member_fees ADD COLUMN installment_group VARCHAR(36)",
        "ALTER TABLE member_fees ADD COLUMN installment_group VARCHAR(36)",
    )
    add_column(
        "member_fees",
        "installment_n",
        "ALTER TABLE member_fees ADD COLUMN installment_n INTEGER",
        "ALTER TABLE member_fees ADD COLUMN installment_n INTEGER",
    )
    add_column(
        "member_fees",
        "installment_total",
        "ALTER TABLE member_fees ADD COLUMN installment_total INTEGER",
        "ALTER TABLE member_fees ADD COLUMN installment_total INTEGER",
    )

    insp = inspect(engine)
    if "payment_proofs" not in insp.get_table_names():
        from app.models import PaymentProof

        PaymentProof.__table__.create(bind=engine, checkfirst=True)
    if "finance_audit_logs" not in insp.get_table_names():
        from app.models import FinanceAuditLog

        FinanceAuditLog.__table__.create(bind=engine, checkfirst=True)


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


def ensure_email_verification_tokens_table(app):
    """Cria tabela email_verification_tokens em bancos já existentes."""
    from app.models import EmailVerificationToken

    engine = db.engine
    insp = inspect(engine)
    if "email_verification_tokens" not in insp.get_table_names():
        EmailVerificationToken.__table__.create(bind=engine, checkfirst=True)


def mark_all_emails_verified(app):
    """Confirma e-mail de contas legadas (verificação por link desativada)."""
    from app.models import Profile, User

    with app.app_context():
        changed = False
        for user in User.query.filter(User.email_verified.is_(False)).all():
            user.email_verified = True
            changed = True
        for profile in Profile.query.filter(Profile.email_verificado.is_(False)).all():
            profile.email_verificado = True
            changed = True
        if changed:
            db.session.commit()


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
        profile.email_verificado = True
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


def ensure_leadership_premium_schema(app):
    """Colunas premium da diretoria + tabelas de delegação e auditoria."""
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

    dm_cols = [
        ("user_id", "INTEGER", "INTEGER"),
        ("system_role", "VARCHAR(40)", "VARCHAR(40)"),
        ("whatsapp", "VARCHAR(40)", "VARCHAR(40)"),
        ("email", "VARCHAR(120)", "VARCHAR(120)"),
        ("birth_date", "DATE", "DATE"),
        ("sex", "VARCHAR(20)", "VARCHAR(20)"),
        ("cpf", "VARCHAR(14)", "VARCHAR(14)"),
        ("rg", "VARCHAR(30)", "VARCHAR(30)"),
        ("address_cep", "VARCHAR(12)", "VARCHAR(12)"),
        ("address_street", "VARCHAR(200)", "VARCHAR(200)"),
        ("address_neighborhood", "VARCHAR(120)", "VARCHAR(120)"),
        ("address_city", "VARCHAR(120)", "VARCHAR(120)"),
        ("address_state", "VARCHAR(2)", "VARCHAR(2)"),
        ("unit", "VARCHAR(80)", "VARCHAR(80)"),
        ("entry_date", "DATE", "DATE"),
        ("delegation_start", "DATE", "DATE"),
        ("delegation_end", "DATE", "DATE"),
        ("status", "VARCHAR(20) DEFAULT 'ativo'", "VARCHAR(20) DEFAULT 'ativo'"),
        ("notes", "TEXT", "TEXT"),
        ("responsible_area", "VARCHAR(200)", "VARCHAR(200)"),
        ("specialties", "TEXT", "TEXT"),
        ("social_links_json", "TEXT", "TEXT"),
        ("show_phone_public", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("show_email_public", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("show_social_public", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("show_bio_public", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("updated_at", "DATETIME", "TIMESTAMP"),
    ]
    for col, sqlite_type, pg_type in dm_cols:
        add_column(
            "directorate_members",
            col,
            f"ALTER TABLE directorate_members ADD COLUMN {col} {sqlite_type}",
            f"ALTER TABLE directorate_members ADD COLUMN {col} {pg_type}",
        )

    insp = inspect(engine)
    tables = insp.get_table_names()

    if "leadership_delegations" not in tables:
        with engine.connect() as conn:
            if is_sqlite:
                conn.execute(
                    text(
                        """
                        CREATE TABLE leadership_delegations (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            clube_id VARCHAR(36),
                            user_id INTEGER,
                            directorate_member_id INTEGER,
                            role_code VARCHAR(40) NOT NULL,
                            role_label VARCHAR(120),
                            start_date DATE,
                            end_date DATE,
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            permissions_json TEXT,
                            created_at DATETIME,
                            created_by_id INTEGER,
                            FOREIGN KEY (clube_id) REFERENCES clubes (id),
                            FOREIGN KEY (user_id) REFERENCES users (id),
                            FOREIGN KEY (directorate_member_id) REFERENCES directorate_members (id),
                            FOREIGN KEY (created_by_id) REFERENCES users (id)
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE leadership_delegations (
                            id SERIAL PRIMARY KEY,
                            clube_id VARCHAR(36) REFERENCES clubes(id),
                            user_id INTEGER REFERENCES users(id),
                            directorate_member_id INTEGER REFERENCES directorate_members(id),
                            role_code VARCHAR(40) NOT NULL,
                            role_label VARCHAR(120),
                            start_date DATE,
                            end_date DATE,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            permissions_json TEXT,
                            created_at TIMESTAMP DEFAULT NOW(),
                            created_by_id INTEGER REFERENCES users(id)
                        )
                        """
                    )
                )
            conn.commit()

    if "leadership_audit_logs" not in tables:
        with engine.connect() as conn:
            if is_sqlite:
                conn.execute(
                    text(
                        """
                        CREATE TABLE leadership_audit_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            clube_id VARCHAR(36),
                            action VARCHAR(40) NOT NULL,
                            summary VARCHAR(500) NOT NULL,
                            target_user_id INTEGER,
                            target_member_id INTEGER,
                            performed_by_id INTEGER,
                            details_json TEXT,
                            created_at DATETIME NOT NULL,
                            FOREIGN KEY (clube_id) REFERENCES clubes (id),
                            FOREIGN KEY (target_user_id) REFERENCES users (id),
                            FOREIGN KEY (target_member_id) REFERENCES directorate_members (id),
                            FOREIGN KEY (performed_by_id) REFERENCES users (id)
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE leadership_audit_logs (
                            id SERIAL PRIMARY KEY,
                            clube_id VARCHAR(36) REFERENCES clubes(id),
                            action VARCHAR(40) NOT NULL,
                            summary VARCHAR(500) NOT NULL,
                            target_user_id INTEGER REFERENCES users(id),
                            target_member_id INTEGER REFERENCES directorate_members(id),
                            performed_by_id INTEGER REFERENCES users(id),
                            details_json TEXT,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
            conn.commit()


def ensure_specialties_schema(app):
    """Tabelas do módulo de especialidades (catálogo + progresso)."""
    from app.models import (
        MemberRequirementCheck,
        MemberSpecialtyProgress,
        Specialty,
        SpecialtyRequirement,
    )

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

    insp = inspect(engine)
    tables = insp.get_table_names()
    for model in (Specialty, SpecialtyRequirement, MemberSpecialtyProgress, MemberRequirementCheck):
        if model.__tablename__ not in tables:
            model.__table__.create(bind=engine, checkfirst=True)

    add_column(
        "specialties",
        "icon_filename",
        "ALTER TABLE specialties ADD COLUMN icon_filename VARCHAR(200)",
        "ALTER TABLE specialties ADD COLUMN icon_filename VARCHAR(200)",
    )


def ensure_activities_schema(app):
    """Tabelas do módulo premium de atividades / caderno digital."""
    from app.models import (
        HomeworkAssignment,
        HomeworkSubmission,
        MemberNotebookEnrollment,
        MemberNotebookRequirementProgress,
        NotebookClass,
        NotebookClassRequirement,
        NotebookRequirementHistory,
    )

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

    insp = inspect(engine)
    tables = insp.get_table_names()
    for model in (
        NotebookClass,
        NotebookClassRequirement,
        MemberNotebookEnrollment,
        MemberNotebookRequirementProgress,
        HomeworkAssignment,
        HomeworkSubmission,
        NotebookRequirementHistory,
    ):
        if model.__tablename__ not in tables:
            model.__table__.create(bind=engine, checkfirst=True)

    for col, sqlite_type, pg_type in [
        ("min_age", "INTEGER", "INTEGER"),
        ("advanced_title", "VARCHAR(120)", "VARCHAR(120)"),
        ("catalog_version", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        add_column(
            "notebook_classes",
            col,
            f"ALTER TABLE notebook_classes ADD COLUMN {col} {sqlite_type}",
            f"ALTER TABLE notebook_classes ADD COLUMN {col} {pg_type}",
        )

    req_cols = [
        ("req_key", "VARCHAR(80)", "VARCHAR(80)"),
        ("section_code", "VARCHAR(10) DEFAULT 'I'", "VARCHAR(10) DEFAULT 'I'"),
        ("section_title", "VARCHAR(120) DEFAULT 'Gerais'", "VARCHAR(120) DEFAULT 'Gerais'"),
        ("req_number", "INTEGER NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1"),
        ("is_advanced", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("is_optional", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("optional_group", "VARCHAR(80)", "VARCHAR(80)"),
    ]
    for col, st, pt in req_cols:
        add_column(
            "notebook_class_requirements",
            col,
            f"ALTER TABLE notebook_class_requirements ADD COLUMN {col} {st}",
            f"ALTER TABLE notebook_class_requirements ADD COLUMN {col} {pt}",
        )

    for col, st, pt in [
        ("completion_date", "DATE", "DATE"),
        ("instructor_signed", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("instructor_signed_at", "DATETIME", "TIMESTAMP"),
    ]:
        add_column(
            "member_notebook_requirement_progress",
            col,
            f"ALTER TABLE member_notebook_requirement_progress ADD COLUMN {col} {st}",
            f"ALTER TABLE member_notebook_requirement_progress ADD COLUMN {col} {pt}",
        )

    for col, st, pt in [
        ("target_units_json", "TEXT", "TEXT"),
        ("target_members_json", "TEXT", "TEXT"),
        ("requirement_id", "INTEGER", "INTEGER"),
    ]:
        add_column(
            "homework_assignments",
            col,
            f"ALTER TABLE homework_assignments ADD COLUMN {col} {st}",
            f"ALTER TABLE homework_assignments ADD COLUMN {col} {pt}",
        )

    with app.app_context():
        from app.activities_service import backfill_member_notebooks
        from app.notebook_catalog import sync_notebook_catalog

        sync_notebook_catalog(force=True)
        db.session.commit()
        backfill_member_notebooks()
        db.session.commit()


def ensure_units_schema(app):
    """Tabelas do módulo premium de unidades."""
    from app.models import ClubUnit, ClubUnitRole

    engine = db.engine
    insp = inspect(engine)
    tables = insp.get_table_names()
    for model in (ClubUnit, ClubUnitRole):
        if model.__tablename__ not in tables:
            model.__table__.create(bind=engine, checkfirst=True)

    with app.app_context():
        from app.models import Club
        from app.units_service import ensure_club_units

        for club in Club.query.all():
            ensure_club_units(club.id)
        db.session.commit()


def ensure_gallery_schema(app):
    """Tabelas da galeria oficial (álbuns, fotos, atividades)."""
    from app.models import GalleryActivityLog, GalleryAlbum, GalleryPhoto

    engine = db.engine
    insp = inspect(engine)
    tables = insp.get_table_names()
    for model in (GalleryAlbum, GalleryPhoto, GalleryActivityLog):
        if model.__tablename__ not in tables:
            model.__table__.create(bind=engine, checkfirst=True)
