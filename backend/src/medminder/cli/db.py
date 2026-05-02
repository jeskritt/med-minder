"""``medminder-admin db backup|restore`` subcommands.

Both commands shell out to the standard Postgres client tools
(``pg_dump`` / ``pg_restore``) using ``subprocess.run`` with a list
argv (``shell=False``) so user-supplied paths cannot be interpreted
as shell metacharacters.

Connection details flow via libpq env vars derived from
``DATABASE_URL`` — never as command-line flags — to keep credentials
out of process listings.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from medminder.cli._dsn import to_pg_env
from medminder.settings import Settings

app = typer.Typer(no_args_is_help=True, help="Database backup and restore.")

PHI_WARNING = (
    "Treat the backup file as protected health information: it contains "
    "every Argon2id password hash and every medication record."
)
WINDOWS_ACL_WARNING = (
    "Note: chmod 0600 is not applied on Windows. Restrict the file's "
    "ACL manually (e.g. icacls) so only you can read it."
)


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _require_tool(name: str) -> str:
    """Resolve an executable on PATH or abort with a helpful message."""
    found = shutil.which(name)
    if found is None:
        typer.secho(
            f"{name} not found on PATH. Install Postgres client tools "
            "(e.g. https://www.postgresql.org/download/) and ensure "
            f"{name} is on PATH.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    return found


@app.command("backup")
def backup(
    out: Annotated[
        Path, typer.Option("--out", help="Destination dump file")
    ],
) -> None:
    """Run ``pg_dump --format=custom`` against ``DATABASE_URL``."""
    pg_dump = _require_tool("pg_dump")

    settings = Settings()
    env = os.environ.copy()
    env.update(to_pg_env(settings.database_url))

    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603 — list argv, shell=False
        [pg_dump, "--format=custom", "--file", str(out)],
        env=env,
        check=True,
    )

    if not _is_windows():
        os.chmod(out, 0o600)
    else:
        typer.secho(WINDOWS_ACL_WARNING, fg=typer.colors.YELLOW)

    typer.secho(PHI_WARNING, fg=typer.colors.YELLOW)
    typer.echo(str(out))


@app.command("restore")
def restore(
    in_file: Annotated[
        Path, typer.Option("--in", help="Source dump file")
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Confirm overwrite of the target database.",
        ),
    ] = False,
) -> None:
    """Run ``pg_restore --clean --if-exists`` against ``DATABASE_URL``.

    Refuses to run without ``--yes`` — restoring overwrites the
    target database.
    """
    if not yes:
        typer.secho(
            "Refusing to restore without --yes. This will overwrite "
            "data in the target database.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    pg_restore = _require_tool("pg_restore")

    if not in_file.exists():
        typer.secho(
            f"Backup file not found: {in_file}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=2)

    settings = Settings()
    env = os.environ.copy()
    env.update(to_pg_env(settings.database_url))

    db_name = env.get("PGDATABASE", "")
    subprocess.run(  # noqa: S603 — list argv, shell=False
        [
            pg_restore,
            "--clean",
            "--if-exists",
            "--dbname",
            db_name,
            str(in_file),
        ],
        env=env,
        check=True,
    )
    typer.echo(str(in_file))


__all__ = ["PHI_WARNING", "WINDOWS_ACL_WARNING", "app"]
