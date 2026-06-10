#!/usr/bin/env python3
"""Lista url_for em templates que apontam para endpoints inexistentes."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app import create_app  # noqa: E402

app = create_app()
endpoints = set(app.view_functions.keys())
pat = re.compile(r"""url_for\(\s*['"]([^'"]+)['"]""")
tpl_root = ROOT / "frontend" / "templates"
missing: dict[str, list[str]] = {}
for p in sorted(tpl_root.rglob("*.html")):
    text = p.read_text(encoding="utf-8")
    for m in pat.finditer(text):
        ep = m.group(1)
        if ep in ("static", "uploaded_file"):
            continue
        if ep not in endpoints:
            missing.setdefault(ep, []).append(p.relative_to(tpl_root).as_posix())

if missing:
    for ep, files in sorted(missing.items()):
        print(f"MISSING {ep}: {files[0]}")
    print(f"\nTotal: {len(missing)} endpoint(s)")
    raise SystemExit(1)
print("OK — todos os url_for verificados existem.")
