"""``medminder-admin user`` subcommands."""

from __future__ import annotations

import sys
from datetime import time
from enum import StrEnum
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from medminder.cli._session import run_with_session
from medminder.db.models.admin_audit import AdminAuditAction
from medminder.domain import users as users_domain
from medminder.domain.audit import record_admin_action
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


def _abort(message: str, code: int = 1) -> NoReturn:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=code)


def _parse_hhmm(value: str) -> time:
    """Parse a ``HH:MM`` 24-hour string into a ``time``; abort on bad input."""
    parts = value.split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        hour, minute = int(parts[0]), int(parts[1])
        if 0 <= hour < 24 and 0 <= minute < 60:
            return time(hour, minute)
    _abort(f"Invalid time {value!r}; expected HH:MM (24-hour clock).", code=2)


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
        user = await users_domain.create_user(
            session,
            email=email,
            name=name,
            role=role.value,
            password=password,
            timezone_name=timezone,
        )
        await record_admin_action(
            session,
            actor_id=None,
            action="create",
            target_user_id=user.id,
            details={"via": "cli", "fields": ["email", "name", "role"]},
        )
        return user

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
        user_id = await users_domain.soft_delete_user(session, email=email)
        await record_admin_action(
            session,
            actor_id=None,
            action="deactivate",
            target_user_id=user_id,
            details={"via": "cli"},
        )
        return user_id

    try:
        user_id = run_with_session(op)
    except UserNotFoundError as exc:
        _abort(str(exc), code=1)

    typer.echo(str(user_id))


@app.command("update")
def update(
    email: Annotated[str, typer.Option("--email")],
    new_email: Annotated[str | None, typer.Option("--new-email")] = None,
    name: Annotated[str | None, typer.Option("--name")] = None,
    role: Annotated[Role | None, typer.Option("--role")] = None,
    quiet_hours_start: Annotated[
        str | None,
        typer.Option("--quiet-hours-start", help="Quiet-hours start, HH:MM."),
    ] = None,
    quiet_hours_end: Annotated[
        str | None,
        typer.Option("--quiet-hours-end", help="Quiet-hours end, HH:MM."),
    ] = None,
    clear_quiet_hours: Annotated[
        bool,
        typer.Option(
            "--clear-quiet-hours/--no-clear-quiet-hours",
            help="Clear the user's quiet hours.",
        ),
    ] = False,
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

    if clear_quiet_hours and (
        quiet_hours_start is not None or quiet_hours_end is not None
    ):
        _abort(
            "Use --clear-quiet-hours OR --quiet-hours-start/--quiet-hours-end, "
            "not both.",
            code=2,
        )
    if not clear_quiet_hours and (quiet_hours_start is None) != (
        quiet_hours_end is None
    ):
        _abort(
            "Provide both --quiet-hours-start and --quiet-hours-end together.",
            code=2,
        )
    qh_start = _parse_hhmm(quiet_hours_start) if quiet_hours_start else None
    qh_end = _parse_hhmm(quiet_hours_end) if quiet_hours_end else None

    # Audit descriptor: changed field NAMES only (never values) — FR-020.
    fields: list[str] = []
    if new_email is not None:
        fields.append("email")
    if name is not None:
        fields.append("name")
    if role is not None:
        fields.append("role")
    if new_password is not None:
        fields.append("password")
    if clear_quiet_hours or qh_start is not None:
        fields.append("quiet_hours")
    # Precedence mirrors the web layer's action vocabulary.
    action: AdminAuditAction
    if role is not None:
        action = "role_change"
    elif new_password is not None:
        action = "password_reset"
    else:
        action = "update"

    async def op(session):  # type: ignore[no-untyped-def]
        user = await users_domain.update_user(
            session,
            email=email,
            new_email=new_email,
            new_name=name,
            new_role=(role.value if role is not None else None),
            new_password=new_password,
            new_quiet_hours_start=qh_start,
            new_quiet_hours_end=qh_end,
            clear_quiet_hours=clear_quiet_hours,
        )
        await record_admin_action(
            session,
            actor_id=None,
            action=action,
            target_user_id=user.id,
            details={"via": "cli", "fields": fields},
        )
        return user

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
