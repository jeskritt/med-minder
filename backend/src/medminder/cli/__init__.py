"""``medminder-admin`` CLI entry point.

Re-exports the Typer ``app`` so ``python -m medminder.cli`` and the
``medminder-admin`` console script (declared in ``pyproject.toml``)
both behave identically.
"""

from medminder.cli.main import app

__all__ = ["app"]
