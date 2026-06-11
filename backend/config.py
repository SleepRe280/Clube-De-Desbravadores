import os

BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")
# Raiz do repositório (onde ficam instance/, .env, frontend/)
BASE_DIR = PROJECT_ROOT


def _load_dotenv() -> None:
    """Carrega `.env` na raiz do repositório antes de qualquer leitura de variáveis."""
    path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.isfile(path):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(path)
    except ImportError:
        pass


_load_dotenv()

_DEFAULT_SQLITE = "sqlite:///" + os.path.join(INSTANCE_DIR, "club.db").replace("\\", "/")


def _normalize_database_url(uri: str) -> str:
    """Render/Heroku às vezes enviam postgres://; SQLAlchemy usa postgresql://."""
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


def _database_uri() -> str:
    raw = os.environ.get("DATABASE_URL")
    if raw:
        return _normalize_database_url(raw.strip())
    return _DEFAULT_SQLITE


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _url_prefix() -> str:
    """Ex.: /portal — app atende em https://host/portal/... (vazio = raiz)."""
    raw = (os.environ.get("URL_PREFIX") or "").strip()
    if not raw:
        return ""
    if not raw.startswith("/"):
        raw = "/" + raw
    return raw.rstrip("/") or ""


_CONFIGURED_DATABASE_URI = _database_uri()

# Servidor local (run.py): HOST, PORT, FLASK_APP podem ir em `.env`.
DEV_SERVER_HOST_DEFAULT = "127.0.0.1"
DEV_SERVER_PORT_DEFAULT = 5055

# Gmail SMTP — remetente e conta padrão (senha só via MAIL_PASSWORD no Environment).
DEFAULT_GMAIL_ADDRESS = "sleepre07@gmail.com"
DEFAULT_EMAIL_SENDER = f"Clube de Desbravadores <{DEFAULT_GMAIL_ADDRESS}>"


class Config:
    SECRET_KEY = (os.environ.get("SECRET_KEY") or "").strip() or "troque-esta-chave-em-producao"
    SQLALCHEMY_DATABASE_URI = _CONFIGURED_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite: timeout maior reduz falhas com ficheiro em pasta sincronizada (ex.: OneDrive).
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"connect_args": {"check_same_thread": False, "timeout": 45}}
        if "sqlite" in _CONFIGURED_DATABASE_URI.lower()
        else {}
    )
    UPLOAD_FOLDER = os.path.join(INSTANCE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    DEBUG = _env_flag("FLASK_DEBUG", default=False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", default=False)
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http").strip().lower()
    URL_PREFIX = _url_prefix()
    WTF_CSRF_TIME_LIMIT = None

    # E-mail — Gmail SMTP (padrão). Resend opcional se RESEND_API_KEY estiver definida.
    EMAIL_VERIFICATION_REQUIRED = _env_flag("EMAIL_VERIFICATION_REQUIRED", default=False)

    MAIL_SERVER = (os.environ.get("MAIL_SERVER") or "smtp.gmail.com").strip()
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or "587")
    MAIL_USE_TLS = _env_flag("MAIL_USE_TLS", default=True)
    MAIL_USE_SSL = _env_flag("MAIL_USE_SSL", default=False)
    MAIL_USERNAME = (os.environ.get("MAIL_USERNAME") or DEFAULT_GMAIL_ADDRESS).strip()
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "").strip()
    MAIL_DEFAULT_SENDER = (os.environ.get("MAIL_DEFAULT_SENDER") or DEFAULT_EMAIL_SENDER).strip()

    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
    RESEND_FROM = (os.environ.get("RESEND_FROM") or DEFAULT_EMAIL_SENDER).strip()
