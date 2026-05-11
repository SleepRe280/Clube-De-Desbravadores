import os
import socket
import sys

if __name__ == "__main__":
    os.environ.setdefault("FLASK_DEBUG", "1")

try:
    from app import create_app
except ImportError as exc:
    print(
        "Falha ao importar a aplicação. Instale dependências na pasta do projeto:\n"
        "  pip install -r requirements.txt\n"
        f"Detalhe: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

from config import DEV_SERVER_HOST_DEFAULT, DEV_SERVER_PORT_DEFAULT

app = create_app()

_DEFAULT_DEV_HOST = DEV_SERVER_HOST_DEFAULT
_DEFAULT_DEV_PORT = DEV_SERVER_PORT_DEFAULT


def _looks_like_onedrive_path(path: str) -> bool:
    return "onedrive" in path.replace("\\", "/").lower()


def _browser_open_host(bind_host: str) -> str:
    """Host mostrado na URL copiável (0.0.0.0 / :: → 127.0.0.1)."""
    h = (bind_host or "").strip()
    if h in ("0.0.0.0", "", "::"):
        return "127.0.0.1"
    return h


def _can_bind(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def _pick_available_port(host: str, preferred_port: int, max_tries: int = 20) -> int | None:
    for p in range(preferred_port, preferred_port + max_tries):
        if _can_bind(host, p):
            return p
    return None


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    bind_host = (os.environ.get("HOST") or _DEFAULT_DEV_HOST).strip() or _DEFAULT_DEV_HOST
    raw_port = (os.environ.get("PORT") or "").strip()
    try:
        requested_port = int(raw_port) if raw_port else _DEFAULT_DEV_PORT
    except ValueError:
        print(f"PORT inválido: {raw_port!r}. Use um número (ex.: {_DEFAULT_DEV_PORT}).", file=sys.stderr)
        sys.exit(1)
    strict_port = _env_flag("STRICT_PORT", default=False)

    project_root = os.path.abspath(os.path.dirname(__file__))
    rel = os.environ.get("FLASK_RELOADER", "").strip().lower()
    if rel in ("0", "false", "no", "off"):
        use_reloader = False
    elif rel in ("1", "true", "yes", "on"):
        use_reloader = True
    else:
        use_reloader = not _looks_like_onedrive_path(project_root)

    port = requested_port
    if not strict_port:
        fallback = _pick_available_port(bind_host, requested_port)
        if fallback is not None:
            port = fallback

    show = _browser_open_host(bind_host)
    pfx = (app.config.get("URL_PREFIX") or "").strip()
    path = f"{pfx}/login" if pfx else "/login"
    if port != requested_port:
        print(
            f"Porta {requested_port} ocupada. Iniciando automaticamente na porta {port}.",
            flush=True,
        )
    base_url = f"http://{show}:{port}"
    print(f"Servidor local: {base_url}{path}", flush=True)
    print(f"Se o navegador não abrir sozinho, acesse: {base_url}{path}", flush=True)

    try:
        app.run(
            debug=app.config.get("DEBUG", False),
            host=bind_host,
            port=port,
            use_reloader=use_reloader,
        )
    except OSError as exc:
        if strict_port:
            detail = f"Verifique se a porta {port} já está em uso ou altere PORT no ficheiro .env."
        else:
            detail = (
                f"Não foi possível encontrar porta livre a partir de {requested_port}. "
                "Defina PORT no ficheiro .env para uma porta disponível."
            )
        print(
            f"{exc}\n{detail}",
            file=sys.stderr,
        )
        sys.exit(1)
