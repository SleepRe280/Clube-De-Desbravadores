import json
from datetime import date, datetime
import uuid

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

CARGO_SUPER_ADMIN = "super_admin"
CARGO_DIRETOR = "diretor"
CARGO_TESOUREIRO = "tesoureiro"
CARGO_SECRETARIO = "secretario"
CARGO_CONSELHEIRO = "conselheiro"
CARGO_PAI = "pai"

# Publicações unificadas (mural dos responsáveis)
POST_KIND_COMUNICADO = "comunicado"
POST_KIND_NOTICIA = "noticia"

POST_CATEGORY_AVISO = "aviso"
POST_CATEGORY_EVENTO = "evento"
POST_CATEGORY_REUNIAO = "reuniao"
POST_CATEGORY_ESPIRITUAL = "espiritual"
POST_CATEGORY_FINANCEIRO = "financeiro"
POST_CATEGORY_INFORMATIVO = "informativo"

POST_CATEGORIES = (
    POST_CATEGORY_AVISO,
    POST_CATEGORY_EVENTO,
    POST_CATEGORY_REUNIAO,
    POST_CATEGORY_ESPIRITUAL,
    POST_CATEGORY_FINANCEIRO,
    POST_CATEGORY_INFORMATIVO,
)

POST_CATEGORY_LABELS = {
    POST_CATEGORY_AVISO: "Aviso",
    POST_CATEGORY_EVENTO: "Evento",
    POST_CATEGORY_REUNIAO: "Reunião",
    POST_CATEGORY_ESPIRITUAL: "Espiritual",
    POST_CATEGORY_FINANCEIRO: "Financeiro",
    POST_CATEGORY_INFORMATIVO: "Informativo",
}

POST_CATEGORY_CSS = {
    POST_CATEGORY_AVISO: "cm-tag--aviso",
    POST_CATEGORY_EVENTO: "cm-tag--evento",
    POST_CATEGORY_REUNIAO: "cm-tag--reuniao",
    POST_CATEGORY_ESPIRITUAL: "cm-tag--espiritual",
    POST_CATEGORY_FINANCEIRO: "cm-tag--financeiro",
    POST_CATEGORY_INFORMATIVO: "cm-tag--informativo",
}


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    last_seen_at = db.Column(db.DateTime, nullable=True)

    children = db.relationship(
        "Member", back_populates="parent", foreign_keys="Member.parent_id"
    )
    posts = db.relationship("BoardPost", backref="author", lazy="dynamic")
    reset_tokens = db.relationship(
        "PasswordResetToken", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Club(db.Model):
    """Cadastro de clubes (multi-clube) e identidade visual por clube."""

    __tablename__ = "clubes"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(160), nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=True)
    brasao_url = db.Column(db.String(500), nullable=True)
    cor_primaria = db.Column(db.String(20), nullable=True)
    cor_secundaria = db.Column(db.String(20), nullable=True)
    cor_accent = db.Column(db.String(20), nullable=True)
    cidade = db.Column(db.String(120), nullable=True)
    regiao = db.Column(db.String(120), nullable=True)
    titulo_sistema = db.Column(db.String(160), nullable=True)
    template_slug = db.Column(db.String(40), nullable=False, default="duque_de_caxias")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    perfis = db.relationship("Profile", back_populates="clube", lazy="dynamic")


class Profile(db.Model):
    """Perfil de acesso por usuário (cargo + vínculo de clube)."""

    __tablename__ = "perfis"
    id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    nome_completo = db.Column(db.String(160), nullable=True)
    cargo = db.Column(db.String(40), nullable=False, default=CARGO_PAI, index=True)
    cargos_json = db.Column(db.Text, nullable=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    phone = db.Column(db.String(40), nullable=True)
    email_verificado = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("perfil", uselist=False))
    clube = db.relationship("Club", back_populates="perfis")


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Member(db.Model):
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(60), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    photo_filename = db.Column(db.String(200), nullable=True)
    cpf = db.Column(db.String(14), unique=True, nullable=True, index=True)
    blood_type = db.Column(db.String(8), nullable=True)
    sex = db.Column(db.String(20), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    joined_at = db.Column(db.Date, nullable=True)
    unit_role = db.Column(db.String(80), nullable=True)
    member_status = db.Column(db.String(30), nullable=True, default="ativo")
    address_cep = db.Column(db.String(12), nullable=True)
    address_street = db.Column(db.String(200), nullable=True)
    address_number = db.Column(db.String(20), nullable=True)
    address_neighborhood = db.Column(db.String(120), nullable=True)
    address_city = db.Column(db.String(120), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)
    guardians_json = db.Column(db.Text, nullable=True)
    emergency_relation = db.Column(db.String(60), nullable=True)
    father_name = db.Column(db.String(120), nullable=True)
    mother_name = db.Column(db.String(120), nullable=True)
    emergency_contact_name = db.Column(db.String(120), nullable=True)
    emergency_contact_phone = db.Column(db.String(40), nullable=True)
    notebook_current = db.Column(db.String(200), nullable=True)
    overall_performance = db.Column(db.Integer, default=0)
    activities_30_json = db.Column(db.Text, nullable=True)
    notebook_checklist_30_json = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    parent_link_type = db.Column(db.String(40), nullable=True)
    parent_linked_at = db.Column(db.DateTime, nullable=True)
    parent = db.relationship("User", back_populates="children", foreign_keys=[parent_id])
    activities = db.relationship("ActivityRecord", backref="member", lazy="dynamic")
    attendances = db.relationship("Attendance", backref="member", lazy="dynamic")
    duques_entries = db.relationship(
        "MeetingDuque", backref="member", lazy="dynamic", cascade="all, delete-orphan"
    )
    fees = db.relationship(
        "MemberFee", back_populates="member", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def age_years(self):
        if not self.birth_date:
            return None
        today = date.today()
        y = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            y -= 1
        return y

    def attendance_stats(self):
        from app.attendance_service import member_attendance_stats

        rows = list(self.attendances)
        st = member_attendance_stats(rows)
        if not st["total"]:
            return 0, 0, 0
        denom = st["present"] + st["absent"]
        rate = round(100 * st["present"] / denom) if denom else 0
        return st["present"], st["total"], rate

    def activity_progress_avg(self):
        rows = list(self.activities)
        if not rows:
            return None
        return round(sum(r.progress_percent or 0 for r in rows) / len(rows))

    def specialty_completion_percent(self) -> int:
        """Percentual global de especialidades concluídas (referência 512)."""
        n = MemberSpecialtyProgress.query.filter_by(
            member_id=self.id, status=SP_STATUS_COMPLETED
        ).count()
        if not OFFICIAL_SPECIALTY_COUNT:
            return 0
        return round(100 * n / OFFICIAL_SPECIALTY_COUNT)

    def computed_overall_performance(self):
        """Desempenho automático: média entre atividades, presença e especialidades."""
        components = []
        activity_avg = self.activity_progress_avg()
        if activity_avg is not None:
            components.append(activity_avg)
        _, total_att, att_rate = self.attendance_stats()
        if total_att > 0:
            components.append(att_rate)
        sp_pct = self.specialty_completion_percent()
        if sp_pct > 0:
            components.append(sp_pct)
        if not components:
            return 0
        return round(sum(components) / len(components))

    def _legacy_ints_to_bools(self, data):
        out = []
        for i in range(30):
            if i < len(data):
                x = data[i]
                if isinstance(x, bool):
                    out.append(x)
                else:
                    try:
                        out.append(int(x) > 0)
                    except (TypeError, ValueError):
                        out.append(False)
            else:
                out.append(False)
        return out

    def get_notebook_checklist_30(self):
        """Checklist 1–30 do caderno atual: True/False por item."""
        if self.notebook_checklist_30_json:
            try:
                data = json.loads(self.notebook_checklist_30_json)
                if isinstance(data, list):
                    return self._legacy_ints_to_bools(data)
            except json.JSONDecodeError:
                pass
        if self.activities_30_json:
            try:
                data = json.loads(self.activities_30_json)
                if isinstance(data, list):
                    return self._legacy_ints_to_bools(data)
            except json.JSONDecodeError:
                pass
        return [False] * 30

    def notebook_checklist_progress_percent(self):
        c = self.get_notebook_checklist_30()
        n = sum(1 for x in c if x)
        return round(100 * n / 30)


class AgendaEvent(db.Model):
    """Compromissos e eventos da agenda do clube (visível aos pais)."""

    __tablename__ = "agenda_events"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=False, index=True)
    event_time = db.Column(db.String(8), nullable=True)
    category = db.Column(db.String(40), nullable=True, default="reuniao")
    location = db.Column(db.String(200), nullable=True)
    unit = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(30), nullable=True, default="planejado")
    banner_filename = db.Column(db.String(200), nullable=True)
    max_capacity = db.Column(db.Integer, nullable=True)
    responsible_name = db.Column(db.String(120), nullable=True)
    event_end_date = db.Column(db.Date, nullable=True)
    event_end_time = db.Column(db.String(8), nullable=True)
    color_hex = db.Column(db.String(7), nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rsvps = db.relationship(
        "AgendaEventRSVP",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def confirmed_rsvp_count(self) -> int:
        return self.rsvps.filter_by(status="confirmed").count()


class AgendaEventRSVP(db.Model):
    """Confirmação de presença em evento (pais / portal)."""

    __tablename__ = "agenda_event_rsvps"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("agenda_events.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="confirmed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = db.relationship("AgendaEvent", back_populates="rsvps")


class DirectorateMember(db.Model):
    """Equipe de diretoria — ficha completa, portal família e vínculo opcional com conta."""

    __tablename__ = "directorate_members"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    cargo = db.Column(db.String(120), nullable=False)
    system_role = db.Column(db.String(40), nullable=True, index=True)
    photo_filename = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    whatsapp = db.Column(db.String(40), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    email_public = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    sex = db.Column(db.String(20), nullable=True)
    cpf = db.Column(db.String(14), nullable=True)
    rg = db.Column(db.String(30), nullable=True)
    address_cep = db.Column(db.String(12), nullable=True)
    address_street = db.Column(db.String(200), nullable=True)
    address_neighborhood = db.Column(db.String(120), nullable=True)
    address_city = db.Column(db.String(120), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)
    unit = db.Column(db.String(80), nullable=True)
    entry_date = db.Column(db.Date, nullable=True)
    delegation_start = db.Column(db.Date, nullable=True)
    delegation_end = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ativo", index=True)
    notes = db.Column(db.Text, nullable=True)
    responsible_area = db.Column(db.String(200), nullable=True)
    specialties = db.Column(db.Text, nullable=True)
    social_links_json = db.Column(db.Text, nullable=True)
    show_phone_public = db.Column(db.Boolean, default=True, nullable=False)
    show_email_public = db.Column(db.Boolean, default=True, nullable=False)
    show_social_public = db.Column(db.Boolean, default=False, nullable=False)
    show_bio_public = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    def effective_status(self) -> str:
        return (self.status or "ativo").strip().lower()

    def is_active(self) -> bool:
        return self.effective_status() == "ativo"


class LeadershipDelegation(db.Model):
    """Histórico de delegação de cargo (sistema + ficha pública)."""

    __tablename__ = "leadership_delegations"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    directorate_member_id = db.Column(
        db.Integer, db.ForeignKey("directorate_members.id"), nullable=True, index=True
    )
    role_code = db.Column(db.String(40), nullable=False)
    role_label = db.Column(db.String(120), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    permissions_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    member = db.relationship("DirectorateMember", foreign_keys=[directorate_member_id])
    user = db.relationship("User", foreign_keys=[user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class LeadershipAuditLog(db.Model):
    """Log de alterações na gestão da liderança."""

    __tablename__ = "leadership_audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    action = db.Column(db.String(40), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    target_member_id = db.Column(db.Integer, db.ForeignKey("directorate_members.id"), nullable=True)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    performed_by = db.relationship("User", foreign_keys=[performed_by_id])


class ActivityRecord(db.Model):
    __tablename__ = "activity_records"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    progress_percent = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    recorded_at = db.Column(db.Date, default=date.today)


class MeetingDuque(db.Model):
    """Duques registrados por reunião (moeda do clube), por desbravador."""

    __tablename__ = "meeting_duques"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False, index=True)
    meeting_date = db.Column(db.Date, nullable=False, index=True)
    duques = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Attendance(db.Model):
    __tablename__ = "attendances"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)
    meeting_date = db.Column(db.Date, nullable=False)
    present = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), nullable=True, default="presente", index=True)
    note = db.Column(db.String(200), nullable=True)

    def effective_status(self) -> str:
        from app.attendance_service import (
            ATT_FALTA,
            ATT_PRESENTE,
            normalize_attendance_status,
        )

        if self.status:
            return normalize_attendance_status(self.status, present=self.present)
        return ATT_PRESENTE if self.present else ATT_FALTA


class BoardPost(db.Model):
    __tablename__ = "board_posts"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    post_kind = db.Column(
        db.String(20), nullable=False, default=POST_KIND_COMUNICADO, index=True
    )
    category = db.Column(
        db.String(30), nullable=True, default=POST_CATEGORY_AVISO, index=True
    )
    level = db.Column(db.String(20), nullable=True, index=True)
    image_filename = db.Column(db.String(200), nullable=True)
    attachment_filename = db.Column(db.String(200), nullable=True)
    event_date = db.Column(db.Date, nullable=True)
    event_time = db.Column(db.String(8), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_urgent = db.Column(db.Boolean, default=False, nullable=False)
    audience_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    reads = db.relationship(
        "BoardPostRead",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def audience_list(self) -> list[str]:
        if not self.audience_json:
            return ["clube"]
        try:
            data = json.loads(self.audience_json)
            if isinstance(data, list) and data:
                return [str(x) for x in data]
        except (json.JSONDecodeError, TypeError):
            pass
        return ["clube"]

    def read_count(self) -> int:
        return self.reads.count()

    def is_read_by(self, user_id: int | None) -> bool:
        if not user_id:
            return False
        return self.reads.filter_by(user_id=user_id).first() is not None


class BoardPostRead(db.Model):
    """Registro de leitura de comunicado por responsável."""

    __tablename__ = "board_post_reads"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("board_posts.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("BoardPost", back_populates="reads")
    user = db.relationship("User", backref=db.backref("post_reads", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("post_id", "user_id", name="uq_board_post_read_user"),
    )


FEE_STATUS_PAGO = "pago"
FEE_STATUS_PENDENTE = "pendente"
FEE_STATUS_ATRASADO = "atrasado"
FEE_STATUS_CANCELADO = "cancelado"

FEE_CATEGORIES = (
    "mensalidade",
    "eventos",
    "alimentacao",
    "transporte",
    "uniforme",
    "materiais",
    "doacoes",
    "campori",
    "outros",
)

LEDGER_CATEGORIES = FEE_CATEGORIES

PROOF_STATUS_PENDING = "pendente"
PROOF_STATUS_APPROVED = "aprovado"
PROOF_STATUS_REJECTED = "rejeitado"
PROOF_STATUS_REVISION = "revisao"


class FinanceLedgerEntry(db.Model):
    """Entradas e saídas do caixa do clube (visão diretoria)."""

    __tablename__ = "finance_ledger"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    occurred_at = db.Column(db.Date, nullable=False, index=True)
    direction = db.Column(db.String(16), nullable=False)  # income | expense
    amount_cents = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(400), nullable=False)
    category = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    attachment_filename = db.Column(db.String(200), nullable=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    member_fee_id = db.Column(
        db.Integer,
        db.ForeignKey("member_fees.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    member = db.relationship("Member", backref=db.backref("ledger_entries", lazy="dynamic"))
    member_fee = db.relationship("MemberFee", backref=db.backref("ledger_entry", uselist=False))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ClubSetting(db.Model):
    """Configurações globais do clube (uma linha por chave), ex.: chave PIX para pagamentos."""

    __tablename__ = "club_settings"
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=True)


CLUB_SETTING_PIX_KEY = "pix_key"


def get_club_setting_value(key: str, default: str = "") -> str:
    row = db.session.get(ClubSetting, key)
    if row is None or row.value is None:
        return default
    s = str(row.value).strip()
    return s if s else default


class MemberFee(db.Model):
    """Cobrança (ex.: mensalidade) ligada a um desbravador — pais veem só do(s) filho(s)."""

    __tablename__ = "member_fees"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    member = db.relationship("Member", back_populates="fees")
    title = db.Column(db.String(200), nullable=False, default="Mensalidade")
    category = db.Column(db.String(40), nullable=True, default="mensalidade")
    amount_cents = db.Column(db.Integer, nullable=False)
    discount_cents = db.Column(db.Integer, default=0, nullable=False)
    fine_cents = db.Column(db.Integer, default=0, nullable=False)
    due_date = db.Column(db.Date, nullable=False, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=True, index=True)
    installment_group = db.Column(db.String(36), nullable=True, index=True)
    installment_n = db.Column(db.Integer, nullable=True)
    installment_total = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    proofs = db.relationship(
        "PaymentProof",
        back_populates="fee",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def effective_amount_cents(self) -> int:
        return max(0, int(self.amount_cents) - int(self.discount_cents or 0) + int(self.fine_cents or 0))

    def computed_status(self, today: date | None = None) -> str:
        if self.status == FEE_STATUS_CANCELADO:
            return FEE_STATUS_CANCELADO
        if self.paid_at:
            return FEE_STATUS_PAGO
        ref = today or date.today()
        if self.due_date < ref:
            return FEE_STATUS_ATRASADO
        return FEE_STATUS_PENDENTE


class PaymentProof(db.Model):
    """Comprovante enviado por responsável — aguarda validação da diretoria."""

    __tablename__ = "payment_proofs"
    id = db.Column(db.Integer, primary_key=True)
    member_fee_id = db.Column(
        db.Integer, db.ForeignKey("member_fees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(200), nullable=False)
    note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=PROOF_STATUS_PENDING, index=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fee = db.relationship("MemberFee", back_populates="proofs")
    user = db.relationship("User", foreign_keys=[user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


class FinanceAuditLog(db.Model):
    """Histórico de ações financeiras (auditoria)."""

    __tablename__ = "finance_audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(40), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# —— Almoxarifado ——

WH_STOCK_OK = "ok"
WH_STOCK_LOW = "low"
WH_STOCK_OUT = "out"

WH_MOVEMENT_IN = "in"
WH_MOVEMENT_OUT = "out"

WH_UNIT_OPTIONS = ("un", "cx", "par", "kg", "L", "pct", "rol", "kit")

WH_UNIT_LABELS = {
    "un": "Unidade",
    "cx": "Caixa",
    "par": "Par",
    "kg": "Quilograma",
    "L": "Litro",
    "pct": "Pacote",
    "rol": "Rolo",
    "kit": "Kit",
}

DEFAULT_WAREHOUSE_CATEGORIES = (
    "Uniforme",
    "Campori",
    "Equipamentos",
    "Papelaria",
    "Alimentação",
    "Outros",
)


class WarehouseCategory(db.Model):
    """Categoria de itens do almoxarifado por clube."""

    __tablename__ = "warehouse_categories"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    items = db.relationship("WarehouseItem", back_populates="category", lazy="dynamic")


class WarehouseItem(db.Model):
    """Item cadastrado no almoxarifado do clube."""

    __tablename__ = "warehouse_items"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("warehouse_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name = db.Column(db.String(160), nullable=False)
    internal_code = db.Column(db.String(40), nullable=True, index=True)
    unit = db.Column(db.String(20), nullable=False, default="un")
    quantity = db.Column(db.Integer, default=0, nullable=False)
    min_stock = db.Column(db.Integer, default=0, nullable=False)
    location = db.Column(db.String(120), nullable=True)
    photo_filename = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    unit_price_cents = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = db.relationship("WarehouseCategory", back_populates="items")
    movements = db.relationship(
        "WarehouseMovement",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="WarehouseMovement.created_at.desc()",
    )

    def stock_status(self) -> str:
        qty = int(self.quantity or 0)
        minimum = int(self.min_stock or 0)
        if qty <= 0:
            return WH_STOCK_OUT
        if minimum > 0 and qty <= minimum:
            return WH_STOCK_LOW
        return WH_STOCK_OK

    def estimated_value_cents(self) -> int:
        return max(0, int(self.quantity or 0)) * max(0, int(self.unit_price_cents or 0))


class WarehouseMovement(db.Model):
    """Entrada ou saída de estoque."""

    __tablename__ = "warehouse_movements"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    item_id = db.Column(
        db.Integer, db.ForeignKey("warehouse_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction = db.Column(db.String(8), nullable=False)  # in | out
    quantity = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    balance_after = db.Column(db.Integer, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    item = db.relationship("WarehouseItem", back_populates="movements")
    created_by = db.relationship("User", foreign_keys=[created_by_id])


# —— Especialidades (catálogo + progresso por desbravador) ——

SP_DIFFICULTY_BASICA = "basica"
SP_DIFFICULTY_INTERMEDIARIA = "intermediaria"
SP_DIFFICULTY_AVANCADA = "avancada"

SP_DIFFICULTY_LABELS = {
    SP_DIFFICULTY_BASICA: "Básica",
    SP_DIFFICULTY_INTERMEDIARIA: "Intermediária",
    SP_DIFFICULTY_AVANCADA: "Avançada",
}

SP_STATUS_NOT_STARTED = "nao_iniciada"
SP_STATUS_IN_PROGRESS = "em_andamento"
SP_STATUS_PENDING = "aguardando_aprovacao"
SP_STATUS_COMPLETED = "concluida"
SP_STATUS_LOCKED = "bloqueada"

SP_STATUS_LABELS = {
    SP_STATUS_NOT_STARTED: "Não iniciada",
    SP_STATUS_IN_PROGRESS: "Em andamento",
    SP_STATUS_PENDING: "Aguardando aprovação",
    SP_STATUS_COMPLETED: "Concluída",
    SP_STATUS_LOCKED: "Bloqueada",
}

DEFAULT_SPECIALTY_CATEGORIES = (
    "Natureza",
    "Artes e Habilidades",
    "Atividades Recreativas",
    "Vocação",
    "Saúde e Fitness",
    "Ciência e Tecnologia",
    "Outdoor",
    "Espiritual",
)

# Total oficial de especialidades do programa (referência para barra global)
OFFICIAL_SPECIALTY_COUNT = 512

SP_ICON_KEYS = (
    "first_aid",
    "knots",
    "trees",
    "astronomy",
    "cooking",
    "camping",
    "swimming",
    "music",
    "bible",
    "fitness",
    "crafts",
    "nature",
    "leadership",
    "communication",
    "safety",
    "default",
)


class Specialty(db.Model):
    """Catálogo de especialidades do clube."""

    __tablename__ = "specialties"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Natureza", index=True)
    description = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(30), nullable=False, default=SP_DIFFICULTY_BASICA)
    icon_key = db.Column(db.String(40), nullable=False, default="default")
    icon_filename = db.Column(db.String(200), nullable=True)
    color_hex = db.Column(db.String(7), nullable=True, default="#3b82f6")
    points = db.Column(db.Integer, default=20, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requirements = db.relationship(
        "SpecialtyRequirement",
        back_populates="specialty",
        cascade="all, delete-orphan",
        order_by="SpecialtyRequirement.sort_order",
        lazy="dynamic",
    )
    enrollments = db.relationship(
        "MemberSpecialtyProgress",
        back_populates="specialty",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class SpecialtyRequirement(db.Model):
    """Requisito individual de uma especialidade."""

    __tablename__ = "specialty_requirements"
    id = db.Column(db.Integer, primary_key=True)
    specialty_id = db.Column(
        db.Integer, db.ForeignKey("specialties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    specialty = db.relationship("Specialty", back_populates="requirements")
    checks = db.relationship(
        "MemberRequirementCheck",
        back_populates="requirement",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class MemberSpecialtyProgress(db.Model):
    """Progresso de um desbravador em uma especialidade."""

    __tablename__ = "member_specialty_progress"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    specialty_id = db.Column(
        db.Integer, db.ForeignKey("specialties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = db.Column(db.String(30), nullable=False, default=SP_STATUS_IN_PROGRESS, index=True)
    progress_percent = db.Column(db.Integer, default=0, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = db.relationship("Member", backref=db.backref("specialty_progress", lazy="dynamic"))
    specialty = db.relationship("Specialty", back_populates="enrollments")
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    requirement_checks = db.relationship(
        "MemberRequirementCheck",
        back_populates="enrollment",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        db.UniqueConstraint("member_id", "specialty_id", name="uq_member_specialty"),
    )


class MemberRequirementCheck(db.Model):
    """Checklist: requisito marcado para um desbravador."""

    __tablename__ = "member_requirement_checks"
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer,
        db.ForeignKey("member_specialty_progress.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id = db.Column(
        db.Integer,
        db.ForeignKey("specialty_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    enrollment = db.relationship("MemberSpecialtyProgress", back_populates="requirement_checks")
    requirement = db.relationship("SpecialtyRequirement", back_populates="checks")
    completed_by = db.relationship("User", foreign_keys=[completed_by_id])

    __table_args__ = (
        db.UniqueConstraint("enrollment_id", "requirement_id", name="uq_enrollment_requirement"),
    )


# —— Caderno digital / classes dos Desbravadores ——

PATHFINDER_CLASS_NAMES = (
    "Amigo",
    "Companheiro",
    "Pesquisador",
    "Pioneiro",
    "Excursionista",
    "Guia",
)

NOTEBOOK_CLASS_ALIASES = {
    "clube de líderes": "Guia",
    "clube de lideres": "Guia",
    "explorador": "Pesquisador",
}

NB_STATUS_NOT_STARTED = "not_started"
NB_STATUS_IN_PROGRESS = "in_progress"
NB_STATUS_PENDING = "pending_review"
NB_STATUS_COMPLETED = "completed"
NB_STATUS_REJECTED = "rejected"
NB_STATUS_REVISION = "revision"

NB_STATUS_LABELS = {
    NB_STATUS_NOT_STARTED: "Não iniciado",
    NB_STATUS_IN_PROGRESS: "Em andamento",
    NB_STATUS_PENDING: "Enviado para avaliação",
    NB_STATUS_COMPLETED: "Concluído",
    NB_STATUS_REJECTED: "Reprovado",
    NB_STATUS_REVISION: "Correção solicitada",
}

NB_STATUS_CSS = {
    NB_STATUS_NOT_STARTED: "act-status--muted",
    NB_STATUS_IN_PROGRESS: "act-status--amber",
    NB_STATUS_PENDING: "act-status--blue",
    NB_STATUS_COMPLETED: "act-status--green",
    NB_STATUS_REJECTED: "act-status--red",
    NB_STATUS_REVISION: "act-status--purple",
}

DEFAULT_NOTEBOOK_CATEGORIES = (
    "Espiritual",
    "Físico",
    "Intelectual",
    "Social",
    "Profissional",
    "Natureza",
)

HW_STATUS_OPEN = "open"
HW_STATUS_SUBMITTED = "submitted"
HW_STATUS_APPROVED = "approved"
HW_STATUS_REJECTED = "rejected"
HW_STATUS_REVISION = "revision"
HW_STATUS_OVERDUE = "overdue"

HW_STATUS_LABELS = {
    HW_STATUS_OPEN: "Em andamento",
    HW_STATUS_SUBMITTED: "Aguardando avaliação",
    HW_STATUS_APPROVED: "Aprovado",
    HW_STATUS_REJECTED: "Reprovado",
    HW_STATUS_REVISION: "Correção solicitada",
    HW_STATUS_OVERDUE: "Atrasado",
}


class NotebookClass(db.Model):
    """Classe oficial do programa (Amigo, Companheiro, …)."""

    __tablename__ = "notebook_classes"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    color_hex = db.Column(db.String(7), nullable=False, default="#3b82f6")
    icon_key = db.Column(db.String(40), nullable=False, default="book")
    min_age = db.Column(db.Integer, nullable=True)
    advanced_title = db.Column(db.String(120), nullable=True)
    catalog_version = db.Column(db.Integer, default=0, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    requirements = db.relationship(
        "NotebookClassRequirement",
        back_populates="notebook_class",
        cascade="all, delete-orphan",
        order_by="NotebookClassRequirement.sort_order",
        lazy="dynamic",
    )
    enrollments = db.relationship(
        "MemberNotebookEnrollment",
        back_populates="notebook_class",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class NotebookClassRequirement(db.Model):
    """Requisito de uma classe (catálogo global)."""

    __tablename__ = "notebook_class_requirements"
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(
        db.Integer, db.ForeignKey("notebook_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    req_key = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    section_code = db.Column(db.String(10), nullable=False, default="I", index=True)
    section_title = db.Column(db.String(120), nullable=False, default="Gerais")
    req_number = db.Column(db.Integer, nullable=False, default=1)
    category = db.Column(db.String(80), nullable=False, default="Espiritual", index=True)
    is_advanced = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_optional = db.Column(db.Boolean, default=False, nullable=False)
    optional_group = db.Column(db.String(80), nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("class_id", "req_key", name="uq_notebook_class_req_key"),
    )

    notebook_class = db.relationship("NotebookClass", back_populates="requirements")
    progress_rows = db.relationship(
        "MemberNotebookRequirementProgress",
        back_populates="requirement",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class MemberNotebookEnrollment(db.Model):
    """Caderno digital do desbravador em uma classe."""

    __tablename__ = "member_notebook_enrollments"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id = db.Column(
        db.Integer, db.ForeignKey("notebook_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = db.Column(db.String(30), nullable=False, default=NB_STATUS_IN_PROGRESS, index=True)
    progress_percent = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = db.relationship("Member", backref=db.backref("notebook_enrollments", lazy="dynamic"))
    notebook_class = db.relationship("NotebookClass", back_populates="enrollments")
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    requirement_progress = db.relationship(
        "MemberNotebookRequirementProgress",
        back_populates="enrollment",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        db.UniqueConstraint("member_id", "class_id", name="uq_member_notebook_class"),
    )


class MemberNotebookRequirementProgress(db.Model):
    """Progresso individual em cada requisito do caderno."""

    __tablename__ = "member_notebook_requirement_progress"
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer,
        db.ForeignKey("member_notebook_enrollments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id = db.Column(
        db.Integer,
        db.ForeignKey("notebook_class_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(db.String(30), nullable=False, default=NB_STATUS_NOT_STARTED, index=True)
    notes = db.Column(db.Text, nullable=True)
    completion_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    instructor_signed = db.Column(db.Boolean, default=False, nullable=False)
    instructor_signed_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enrollment = db.relationship("MemberNotebookEnrollment", back_populates="requirement_progress")
    requirement = db.relationship("NotebookClassRequirement", back_populates="progress_rows")
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    history = db.relationship(
        "NotebookRequirementHistory",
        back_populates="progress",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        db.UniqueConstraint("enrollment_id", "requirement_id", name="uq_notebook_enrollment_req"),
    )


class NotebookRequirementHistory(db.Model):
    """Histórico de alterações em um requisito do caderno."""

    __tablename__ = "notebook_requirement_history"
    id = db.Column(db.Integer, primary_key=True)
    progress_id = db.Column(
        db.Integer,
        db.ForeignKey("member_notebook_requirement_progress.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = db.Column(db.String(40), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=True)
    note = db.Column(db.Text, nullable=True)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    progress = db.relationship("MemberNotebookRequirementProgress", back_populates="history")
    performed_by = db.relationship("User", foreign_keys=[performed_by_id])


class HomeworkAssignment(db.Model):
    """Atividade para casa enviada pela diretoria (sempre vinculada a um requisito oficial)."""

    __tablename__ = "homework_assignments"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    requirement_id = db.Column(
        db.Integer,
        db.ForeignKey("notebook_class_requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    class_slug = db.Column(db.String(40), nullable=True, index=True)
    category = db.Column(db.String(80), nullable=True)
    target_units_json = db.Column(db.Text, nullable=True)
    target_members_json = db.Column(db.Text, nullable=True)
    attachment_filename = db.Column(db.String(200), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    requirement = db.relationship("NotebookClassRequirement")
    submissions = db.relationship(
        "HomeworkSubmission",
        back_populates="assignment",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class HomeworkSubmission(db.Model):
    """Envio de evidência por desbravador (portal dos pais ou diretoria)."""

    __tablename__ = "homework_submissions"
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(
        db.Integer, db.ForeignKey("homework_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = db.Column(db.String(30), nullable=False, default=HW_STATUS_SUBMITTED, index=True)
    evidence_type = db.Column(db.String(30), nullable=True)
    text_content = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(200), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)

    assignment = db.relationship("HomeworkAssignment", back_populates="submissions")
    member = db.relationship("Member", backref=db.backref("homework_submissions", lazy="dynamic"))
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (
        db.UniqueConstraint("assignment_id", "member_id", name="uq_homework_member"),
    )


UNIT_STATUS_ATIVA = "ativa"
UNIT_STATUS_INATIVA = "inativa"
UNIT_STATUS_ARQUIVADA = "arquivada"

UNIT_STATUS_OPTIONS = (
    (UNIT_STATUS_ATIVA, "Unidade ativa"),
    (UNIT_STATUS_INATIVA, "Inativa"),
    (UNIT_STATUS_ARQUIVADA, "Arquivada"),
)

UNIT_THEME_COLORS = (
    ("gold", "Dourado"),
    ("purple", "Roxo"),
    ("blue", "Azul"),
    ("emerald", "Esmeralda"),
    ("rose", "Rosa"),
    ("amber", "Âmbar"),
)

UNIT_ROLE_COLOR_KEYS = (
    "purple",
    "blue",
    "mint",
    "amber",
    "pink",
    "teal",
    "gray",
    "emerald",
    "rose",
)


class ClubUnit(db.Model):
    """Unidade do clube (equipe de desbravadores)."""

    __tablename__ = "club_units"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), nullable=False, index=True)
    initials = db.Column(db.String(8), nullable=True)
    logo_filename = db.Column(db.String(200), nullable=True)
    description = db.Column(db.String(200), nullable=True)
    unit_type = db.Column(db.String(40), nullable=True)
    status = db.Column(db.String(30), nullable=False, default=UNIT_STATUS_ATIVA, index=True)
    theme_color = db.Column(db.String(20), nullable=False, default="gold")
    founded_at = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    roles = db.relationship(
        "ClubUnitRole",
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="ClubUnitRole.sort_order",
    )

    __table_args__ = (
        db.UniqueConstraint("clube_id", "slug", name="uq_club_unit_slug"),
        db.UniqueConstraint("clube_id", "name", name="uq_club_unit_name"),
    )


class ClubUnitRole(db.Model):
    """Cargo personalizado dentro de uma unidade."""

    __tablename__ = "club_unit_roles"
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(
        db.Integer, db.ForeignKey("club_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(80), nullable=False)
    color_key = db.Column(db.String(30), nullable=False, default="gray")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    unit = db.relationship("ClubUnit", back_populates="roles")

    __table_args__ = (db.UniqueConstraint("unit_id", "name", name="uq_unit_role_name"),)


# Tipos de vínculo portal (desbravador ↔ responsável)
LINK_TYPE_PAI = "pai"
LINK_TYPE_MAE = "mae"
LINK_TYPE_AVO = "avo"
LINK_TYPE_AVA = "ava"
LINK_TYPE_TUTOR = "tutor"
LINK_TYPE_RESPONSAVEL_LEGAL = "responsavel_legal"

PARENT_LINK_TYPES = (
    (LINK_TYPE_PAI, "Pai"),
    (LINK_TYPE_MAE, "Mãe"),
    (LINK_TYPE_AVO, "Avô"),
    (LINK_TYPE_AVA, "Avó"),
    (LINK_TYPE_TUTOR, "Tutor"),
    (LINK_TYPE_RESPONSAVEL_LEGAL, "Responsável legal"),
)

PARENT_LINK_TYPE_LABELS = dict(PARENT_LINK_TYPES)

# Papéis de responsável na ficha do desbravador (contatos)
GUARDIAN_ROLE_PAI = "pai"
GUARDIAN_ROLE_MAE = "mae"
GUARDIAN_ROLE_RESPONSAVEL_LEGAL = "responsavel_legal"
GUARDIAN_ROLE_TUTOR = "tutor"

GUARDIAN_ROLES = (
    (GUARDIAN_ROLE_PAI, "Pai"),
    (GUARDIAN_ROLE_MAE, "Mãe"),
    (GUARDIAN_ROLE_RESPONSAVEL_LEGAL, "Responsável legal"),
    (GUARDIAN_ROLE_TUTOR, "Tutor"),
)


# —— Galeria oficial do clube ——

GALLERY_CAT_CAMPORI = "campori"
GALLERY_CAT_ACAMPAMENTO = "acampamento"
GALLERY_CAT_INVESTIDURA = "investidura"
GALLERY_CAT_CLASSES = "classes"
GALLERY_CAT_ACOES = "acoes"
GALLERY_CAT_REUNIOES = "reunioes"
GALLERY_CAT_ESPECIALIDADES = "especialidades"
GALLERY_CAT_GERAL = "geral"

GALLERY_CATEGORIES = (
    GALLERY_CAT_CAMPORI,
    GALLERY_CAT_ACAMPAMENTO,
    GALLERY_CAT_INVESTIDURA,
    GALLERY_CAT_CLASSES,
    GALLERY_CAT_ACOES,
    GALLERY_CAT_REUNIOES,
    GALLERY_CAT_ESPECIALIDADES,
    GALLERY_CAT_GERAL,
)

GALLERY_CATEGORY_LABELS = {
    GALLERY_CAT_CAMPORI: "Campori",
    GALLERY_CAT_ACAMPAMENTO: "Acampamento",
    GALLERY_CAT_INVESTIDURA: "Investidura",
    GALLERY_CAT_CLASSES: "Classes",
    GALLERY_CAT_ACOES: "Ações sociais",
    GALLERY_CAT_REUNIOES: "Reuniões",
    GALLERY_CAT_ESPECIALIDADES: "Especialidades",
    GALLERY_CAT_GERAL: "Geral",
}

GALLERY_ACT_UPLOAD = "photos_uploaded"
GALLERY_ACT_COVER = "cover_changed"
GALLERY_ACT_DELETE = "photos_deleted"
GALLERY_ACT_ALBUM = "album_created"
GALLERY_ACT_MOVE = "photo_moved"
GALLERY_ACT_FEATURED = "featured_set"


class GalleryAlbum(db.Model):
    """Álbum de fotos do clube."""

    __tablename__ = "gallery_albums"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(40), nullable=False, default=GALLERY_CAT_GERAL, index=True)
    event_date = db.Column(db.Date, nullable=True)
    cover_photo_id = db.Column(db.Integer, db.ForeignKey("gallery_photos.id", ondelete="SET NULL"), nullable=True)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    is_trashed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    photos = db.relationship(
        "GalleryPhoto",
        back_populates="album",
        foreign_keys="GalleryPhoto.album_id",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    cover_photo = db.relationship("GalleryPhoto", foreign_keys=[cover_photo_id], post_update=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class GalleryPhoto(db.Model):
    """Foto em um álbum da galeria."""

    __tablename__ = "gallery_photos"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    album_id = db.Column(
        db.Integer, db.ForeignKey("gallery_albums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename = db.Column(db.String(220), nullable=False)
    thumb_filename = db.Column(db.String(220), nullable=True)
    title = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.Text, nullable=True)
    taken_at = db.Column(db.Date, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_trashed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    album = db.relationship("GalleryAlbum", back_populates="photos", foreign_keys=[album_id])
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])


class GalleryActivityLog(db.Model):
    """Atividades recentes na galeria (auditoria leve)."""

    __tablename__ = "gallery_activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=False, index=True)
    action = db.Column(db.String(40), nullable=False, index=True)
    album_id = db.Column(db.Integer, db.ForeignKey("gallery_albums.id", ondelete="SET NULL"), nullable=True)
    photo_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    message = db.Column(db.String(280), nullable=False)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", foreign_keys=[user_id])
    album = db.relationship("GalleryAlbum", foreign_keys=[album_id])


class ParentLinkHistory(db.Model):
    """Histórico de vínculos desbravador ↔ responsável (portal)."""

    __tablename__ = "parent_link_history"
    id = db.Column(db.Integer, primary_key=True)
    clube_id = db.Column(db.String(36), db.ForeignKey("clubes.id"), nullable=True, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False, index=True)
    parent_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(20), nullable=False)  # link | unlink
    link_type = db.Column(db.String(40), nullable=True)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    parent_name_snapshot = db.Column(db.String(120), nullable=True)
    member_name_snapshot = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    member = db.relationship("Member", foreign_keys=[member_id])
    parent_user = db.relationship("User", foreign_keys=[parent_user_id])
    performed_by = db.relationship("User", foreign_keys=[performed_by_id])
