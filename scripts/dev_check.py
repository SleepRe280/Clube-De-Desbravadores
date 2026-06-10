#!/usr/bin/env python3
"""Verifica se o projeto está pronto para abrir no navegador."""
from __future__ import annotations

import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

PORT = int(os.environ.get("PORT", "5055"))
HOST = os.environ.get("HOST", "127.0.0.1")


def main() -> int:
    print("=== Verificação do Clube de Desbravadores ===\n")
    ok = True

    for rel in ("frontend/templates", "frontend/static", "backend/app", "instance"):
        p = os.path.join(ROOT, rel)
        exists = os.path.isdir(p) or os.path.isfile(p)
        print(f"{'OK' if exists else 'FALTA'}  {rel}")
        ok = ok and exists

    prod_req = os.path.join(BACKEND, "requirements-prod.txt")
    if os.path.isfile(prod_req):
        print("OK  backend/requirements-prod.txt (deploy)")
    else:
        print("FALTA  backend/requirements-prod.txt — Render/Docker não instalam dependências")
        ok = False

    try:
        from app import create_app  # noqa: WPS433

        app = create_app()
        print("OK  importar create_app")
    except Exception as exc:
        print(f"FALHA importar app: {exc}")
        return 1

    with app.app_context():
        try:
            from app.extensions import db
            from app.models import User

            n = User.query.count()
            print(f"OK  base de dados ({n} utilizador(es))")
        except Exception as exc:
            print(f"AVISO base de dados: {exc}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex((HOST if HOST not in ("0.0.0.0", "::") else "127.0.0.1", PORT)) == 0
    if in_use:
        print(f"AVISO  porta {PORT} já em uso — feche outro servidor ou mude PORT no .env")
    else:
        print(f"OK  porta {PORT} livre")

    with app.test_client() as c:
        for path in ("/health", "/login"):
            r = c.get(path)
            status = "OK" if r.status_code < 500 else "FALHA"
            print(f"{status}  GET {path} -> {r.status_code}")
            if r.status_code >= 500:
                ok = False

    print("\nPara iniciar: python run.py  ou  run.bat")
    print(f"Depois abra: http://127.0.0.1:{PORT}/login")
    print("Mantenha o terminal aberto. Se vir 'conexão recusada', o servidor não está rodando.\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
