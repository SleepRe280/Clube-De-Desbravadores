"""Atalho para iniciar o servidor a partir da raiz do repositório."""
import os
import runpy
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)
try:
    runpy.run_path(os.path.join(_BACKEND, "run.py"), run_name="__main__")
except SystemExit:
    raise
except Exception as exc:
    print(f"Falha ao iniciar o servidor: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc
