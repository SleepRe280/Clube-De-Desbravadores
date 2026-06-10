#!/usr/bin/env python3
"""Varredura: templates, rotas GET, erros 5xx."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError  # noqa: E402

TPL_ROOT = ROOT / "frontend" / "templates"


def check_templates() -> list[str]:
    env = Environment(loader=FileSystemLoader(str(TPL_ROOT)))
    try:
        from app.template_filters import fmt_date, fmt_time

        env.filters["fmt_date"] = fmt_date
        env.filters["fmt_time"] = fmt_time
    except Exception:
        pass
    errors = []
    for path in sorted(TPL_ROOT.rglob("*.html")):
        rel = path.relative_to(TPL_ROOT).as_posix()
        try:
            env.get_template(rel)
        except TemplateSyntaxError as exc:
            errors.append(f"{rel}: {exc}")
        except Exception as exc:
            errors.append(f"{rel}: {exc}")
    return errors


def login_as(client, user_id: int):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def main() -> int:
    from app import create_app  # noqa: WPS433
    from app.extensions import db  # noqa: WPS433
    from app.models import Member, User  # noqa: WPS433

    print("=== Templates ===")
    tpl_errs = check_templates()
    if tpl_errs:
        for e in tpl_errs:
            print(f"ERRO  {e}")
    else:
        n = len(list(TPL_ROOT.rglob("*.html")))
        print(f"OK  {n} templates")

    app = create_app()
    failures: list[str] = []

    with app.app_context():
        users = {u.id: u.email for u in User.query.all()}
        member = Member.query.first()
        club_id = member.clube_id if member else None

    routes_to_test: list[tuple[str, int | None, dict | None]] = [
        ("/health", None, None),
        ("/login", None, None),
    ]

    admin_paths = [
        "/admin/",
        "/admin/membros",
        "/admin/agenda",
        "/admin/responsaveis",
        "/admin/publicacoes",
        "/admin/diretoria",
        "/admin/financeiro",
        "/admin/presencas",
        "/admin/atividades",
        "/admin/especialidades",
        "/admin/configuracoes",
        "/admin/unidades",
    ]
    parent_paths = [
        "/pais/",
        "/pais/agenda",
        "/pais/financeiro",
        "/pais/comunicados",
        "/pais/clube/diretoria",
        "/pais/clube/membros",
        "/pais/atividades",
        "/pais/especialidades",
        "/pais/progresso",
        "/pais/galeria",
        "/pais/conta",
    ]

    with app.test_client() as client:
        for uid, label in [(10, "diretor"), (7, "super_admin"), (11, "pai")]:
            login_as(client, uid)
            paths = admin_paths if uid != 11 else parent_paths
            if uid == 11:
                print(f"\n=== Parent ({label} id={uid}) ===")
            else:
                print(f"\n=== Admin ({label} id={uid}) ===")
            for path in paths:
                try:
                    r = client.get(path, follow_redirects=True)
                    ok = r.status_code < 500
                    tag = "OK" if ok else "5xx"
                    extra = ""
                    if r.status_code >= 500:
                        extra = (r.data[:200] or b"").decode("utf-8", errors="replace")
                        failures.append(f"{label} {path} -> {r.status_code}")
                    print(f"{tag}  {path} -> {r.status_code} {extra[:80]}")
                except Exception as exc:
                    failures.append(f"{label} {path} EXC: {exc}")
                    print(f"EXC  {path}: {exc}")
                    traceback.print_exc()

            if uid in (7, 10) and member:
                mid = member.id
                for path in (
                    f"/admin/membros/{mid}",
                    f"/admin/membros/{mid}/editar",
                    f"/admin/membros/{mid}/atividades",
                    f"/admin/membros/{mid}/presencas",
                ):
                    try:
                        r = client.get(path, follow_redirects=True)
                        tag = "OK" if r.status_code < 500 else "5xx"
                        print(f"{tag}  {path} -> {r.status_code}")
                        if r.status_code >= 500:
                            failures.append(f"{label} {path} -> {r.status_code}")
                    except Exception as exc:
                        failures.append(f"{label} {path} EXC: {exc}")
                        print(f"EXC  {path}: {exc}")

    print("\n=== Resumo ===")
    if tpl_errs:
        print(f"Templates com erro: {len(tpl_errs)}")
    if failures:
        print(f"Rotas com falha: {len(failures)}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Nenhuma falha crítica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
