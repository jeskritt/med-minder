"""``medminder-admin user`` subcommands."""

from __future__ import annotations

import sys
from enum import StrEnum
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from medminder.cli._session import run_with_session
from medminder.domain import users as users_domain
from medminder.domain.users import (
    DuplicateEmailError,
    NoChangesSpecifiedError,
    PasswordTooShortError,
    UserNotFoundError,
)

app = typer.Typer(no_args_is_help=True, help="Manage MedMinder users.")
_console = Console()


class Role(StrEnum):
    admin = "admin"
    user = "user"


def _read_password_from_stdin() -> str:
    """Read exactly one line from stdin; refuse anything else."""
    line = sys.stdin.readline()
    if not line:
        typer.secho(
            "Expected password on stdin (one line) but got nothing.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    return line.rstrip("\n").rstrip("\r")


def _abort(message: str, code: int = 1) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=code)


@app.command("add")
def add(
    email: Annotated[str, typer.Option("--email")],
    name: Annotated[str, typer.Option("--name")],
    role: Annotated[Role, typer.Option("--role")],
    timezone: Annotated[str, typer.Option("--timezone")] = "UTC",
    password_stdin: Annotated[
        bool,
        typer.Option(
            "--password-stdin/--no-password-stdin",
            help="Read the password as one line from stdin (default).",
        ),
    ] = True,
) -> None:
    """Create a new user.

    The password is read from stdin (one line) — there is no
    ``--password`` flag by design (process listings, shell history).
    """
    if not password_stdin:
        _abort("Passwords must be supplied via --password-stdin.", code=2)
    password = _read_password_from_stdin()

    async def op(session):  # type: ignore[no-untyped-def]
        return await users_domain.create_user(
            session,
            email=email,
            name=name,
            role=role.value,
            password=password,
            timezone_name=timezone,
        )

    try:
        user = run_with_session(op)
    except PasswordTooShortError as exc:
        _abort(str(exc), code=2)
    except DuplicateEmailError as exc:
        _abort(str(exc), code=1)

    typer.echo(str(user.id))


@app.command("delete")
def delete(
    email: Annotated[str, typer.Option("--email")],
) -> None:
    """Soft-delete a user (sets ``deleted_at``)."""

    async def op(session):  # type: ignore[no-untyped-def]
        return await users_domain.soft_delete_user(session, email=email)

    try:
        user_id = run_with_session(op)
    except UserNotFoundError as exc:
        _abort(str(exc), code=1)

    typer.echo(str(user_id))


@app.command("update")
def update(
    email: Annotated[str, typer.Option("--email")],
    new_email: Annotated[
        str | None, typer.Option("--new-email")
    ] = None,
    name: Annotated[str | None, typer.Option("--name")] = None,
    role: Annotated[Role | None, typer.Option("--role")] = None,
    password_stdin: Annotated[
        bool,
        typer.Option(
            "--password-stdin/--no-password-stdin",
            help="Also read a new password from stdin.",
        ),
    ] = False,
) -> None:
    """Update a user's mutable fields.  At least one flag is required."""
    new_password = _read_password_from_stdin() if password_stdin else None

    async def op(session):  # type: ignore[no-untyped-def]
        return await users_domain.update_user(
            session,
            email=email,
            new_email=new_email,
            new_name=name,
            new_role=(role.value if role is not None else None),
            new_password=new_password,
        )

    try:
        user = run_with_session(op)
    except NoChangesSpecifiedError as exc:
        _abort(str(exc), code=2)
    except UserNotFoundError as exc:
        _abort(str(exc), code=1)
    except DuplicateEmailError as exc:
        _abort(str(exc), code=1)
    except PasswordTooShortError as exc:
        _abort(str(exc), code=2)

    typer.echo(str(user.id))


@app.command("list")
def list_(
    role: Annotated[Role | None, typer.Option("--role")] = None,
    include_deleted: Annotated[
        bool, typer.Option("--include-deleted/--no-include-deleted")
    ] = False,
) -> None:
    """Print the user table."""

    async def op(session):  # type: ignore[no-untyped-def]
        return await users_domain.list_users(
            session,
            role=(role.value if role is not None else None),
            include_deleted=include_deleted,
        )

    rows = run_with_session(op)

    table = Table(show_header=True, header_style="bold")
    for col in ("id", "email", "name", "role", "created_at", "deleted_at"):
        table.add_column(col)
    for u in rows:
        table.add_row(
            str(u.id),
            u.email,
            u.name,
            u.role,
            u.created_at.isoformat(),
            u.deleted_at.isoformat() if u.deleted_at is not None else "",
        )
    _console.print(table)
