"""Servidor de desenvolvimento — execute pela raiz com `python run.py` ou `run.bat`."""
import os
import socket
import sys
import webbrowser

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
os.chdir(_BACKEND_DIR)

# .env na raiz do repositório
_env_file = os.path.join(_REPO_ROOT, ".env")
if os.path.isfile(_env_file):
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        pass

if __name__ == "__main__":
    os.environ.setdefault("FLASK_DEBUG", "1")

try:
    from app import create_app
except ImportError as exc:
    print(
        "Falha ao importar a aplicação.\n"
        "1) Abra o terminal na pasta do projeto\n"
        "2) Instale dependências:\n"
        f"   pip install -r \"{os.path.join(_BACKEND_DIR, 'requirements.txt')}\"\n"
        f"Detalhe: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

from config import DEV_SERVER_HOST_DEFAULT, DEV_SERVER_PORT_DEFAULT

try:
    app = create_app()
except Exception as exc:
    print(
        "Erro ao criar a aplicação Flask.\n"
        f"  Pasta backend: {_BACKEND_DIR}\n"
        f"  Raiz do repo: {_REPO_ROOT}\n"
        "  Confirme que as pastas frontend/templates e frontend/static existem.\n"
        f"Detalhe: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

_DEFAULT_DEV_HOST = DEV_SERVER_HOST_DEFAULT
_DEFAULT_DEV_PORT = DEV_SERVER_PORT_DEFAULT


def _looks_like_onedrive_path(path: str) -> bool:
    return "onedrive" in path.replace("\\", "/").lower()


def _browser_open_host(bind_host: str) -> str:
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


def _port_busy_message(host: str, port: int) -> str:
    show = _browser_open_host(host)
    return (
        f"\nERRO: a porta {port} já está em uso ({show}:{port}).\n"
        "Outra instância do site pode estar aberta.\n\n"
        "Como resolver:\n"
        "  • Feche outras janelas do terminal com python run.py\n"
        "  • No Cursor/VS Code: pare depurações Flask antigas (Shift+F5)\n"
        "  • Ou altere PORT no ficheiro .env (ex.: PORT=5056)\n"
        "  • Para permitir outra porta automaticamente: ALLOW_PORT_FALLBACK=1 no .env\n"
    )


if __name__ == "__main__":
    bind_host = (os.environ.get("HOST") or _DEFAULT_DEV_HOST).strip() or _DEFAULT_DEV_HOST
    raw_port = (os.environ.get("PORT") or "").strip()
    try:
        requested_port = int(raw_port) if raw_port else _DEFAULT_DEV_PORT
    except ValueError:
        print(f"PORT inválido: {raw_port!r}. Use um número (ex.: {_DEFAULT_DEV_PORT}).", file=sys.stderr)
        sys.exit(1)

    allow_fallback = _env_flag("ALLOW_PORT_FALLBACK", default=False)
    strict_port = _env_flag("STRICT_PORT", default=not allow_fallback)

    # Reloader desligado por padrão: em OneDrive/Windows reinicia ao navegar e gera
    # ERR_CONNECTION_REFUSED entre abas. Ative só com FLASK_RELOADER=1 no .env.
    rel = os.environ.get("FLASK_RELOADER", "").strip().lower()
    if rel in ("1", "true", "yes", "on"):
        use_reloader = True
    else:
        use_reloader = False

    port = requested_port
    if not _can_bind(bind_host, requested_port):
        if strict_port and not allow_fallback:
            print(_port_busy_message(bind_host, requested_port), file=sys.stderr)
            sys.exit(1)
        alt = _pick_available_port(bind_host, requested_port + 1)
        if alt is None:
            print(
                f"Não há porta livre perto de {requested_port}. Defina PORT no .env.",
                file=sys.stderr,
            )
            sys.exit(1)
        port = alt
        print(
            f"\nAVISO: porta {requested_port} ocupada. Servidor em http://{_browser_open_host(bind_host)}:{port}/login\n",
            flush=True,
        )

    show = _browser_open_host(bind_host)
    pfx = (app.config.get("URL_PREFIX") or "").strip()
    path = f"{pfx}/login" if pfx else "/login"
    base_url = f"http://{show}:{port}"
    start_url = f"{base_url}{path}"
    print(f"Servidor local: {start_url}", flush=True)
    print(f"Teste rápido: {base_url}/health", flush=True)
    if any(r.rule == "/admin/galeria" for r in app.url_map.iter_rules()):
        print(f"Galeria: {base_url}/admin/galeria", flush=True)
    else:
        print(
            "AVISO: rota /admin/galeria não encontrada — reinicie após atualizar o código.",
            flush=True,
        )
    if port != requested_port:
        print(
            f"IMPORTANTE: use sempre a porta {port} nos favoritos do navegador "
            f"(não http://127.0.0.1 sem porta).",
            flush=True,
        )
    else:
        print(
            f"Mantenha este terminal aberto enquanto navega. URL base: {base_url}",
            flush=True,
        )

    try:
        import json

        meta_path = os.path.join(_REPO_ROOT, "instance", "dev-server.json")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "url": base_url,
                    "port": port,
                    "host": show,
                    "pid": os.getpid(),
                },
                fh,
            )
    except OSError:
        pass

    if _env_flag("OPEN_BROWSER", default=True):
        if (not use_reloader) or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            try:
                webbrowser.open(start_url)
            except OSError:
                pass

    try:
        app.run(
            debug=app.config.get("DEBUG", False),
            host=bind_host,
            port=port,
            use_reloader=use_reloader,
        )
    except OSError as exc:
        print(f"{exc}\n{_port_busy_message(bind_host, port)}", file=sys.stderr)
        sys.exit(1)
