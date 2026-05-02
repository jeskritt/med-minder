"""Root Typer app for ``medminder-admin``."""

from __future__ import annotations

import typer

from medminder.cli import db as db_cmd
from medminder.cli import users as users_cmd

app = typer.Typer(
    no_args_is_help=True,
    help="MedMinder admin CLI: user management and DB backup/restore.",
)
app.add_typer(users_cmd.app, name="user")
app.add_typer(db_cmd.app, name="db")


__all__ = ["app"]
