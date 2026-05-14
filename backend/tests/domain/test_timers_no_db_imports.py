"""Constitution Principle III: domain code must not import the DB or web layer.

Run the import in a subprocess so a sibling test that previously
imported sqlalchemy (conftest.py does) cannot pollute sys.modules and
mask a real violation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_domain_timers_has_no_db_or_fastapi_imports() -> None:
    script = (
        "import sys\n"
        "import medminder.domain.timers  # noqa: F401\n"
        "assert 'sqlalchemy' not in sys.modules, "
        "sorted(m for m in sys.modules if m.startswith('sqlalchemy'))\n"
        "assert 'fastapi' not in sys.modules, "
        "sorted(m for m in sys.modules if m.startswith('fastapi'))\n"
    )
    subprocess.run(  # noqa: S603 — list argv, sys.executable, shell=False
        [sys.executable, "-c", script],
        cwd=_BACKEND_DIR,
        check=True,
    )
