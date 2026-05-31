"""CLI admin actions write audit rows (G7 — closes the web/CLI divergence)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typer.testing import CliRunner

from medminder.cli._session import run_with_session
from medminder.cli.main import app
from medminder.db.models import AdminAuditLog

GOOD_PASSWORD = "correct horse battery staple"


async def _fetch_audit(session: AsyncSession) -> list[AdminAuditLog]:
    return list(
        (
            await session.execute(
                select(AdminAuditLog).order_by(AdminAuditLog.created_at)
            )
        )
        .scalars()
        .all()
    )


def _audit_rows() -> list[AdminAuditLog]:
    return run_with_session(_fetch_audit)


def _add(cli_runner: CliRunner, email: str = "a@example.com") -> None:
    result = cli_runner.invoke(
        app,
        ["user", "add", "--email", email, "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    assert result.exit_code == 0, result.stdout + result.stderr


def test_add_writes_create_audit_row(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    _add(cli_runner)
    rows = _audit_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "create"
    assert row.actor_id is None  # CLI has no authenticated principal
    assert row.details == {"via": "cli", "fields": ["email", "name", "role"]}


def test_update_name_writes_update_row(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    _add(cli_runner)
    cli_runner.invoke(
        app, ["user", "update", "--email", "a@example.com", "--name", "Renamed"]
    )
    update = [r for r in _audit_rows() if r.action == "update"]
    assert len(update) == 1
    assert update[0].details == {"via": "cli", "fields": ["name"]}


def test_update_role_writes_role_change_row(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    _add(cli_runner)
    cli_runner.invoke(
        app, ["user", "update", "--email", "a@example.com", "--role", "admin"]
    )
    role_change = [r for r in _audit_rows() if r.action == "role_change"]
    assert len(role_change) == 1
    assert "role" in role_change[0].details["fields"]


def test_password_update_records_field_name_not_secret(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    _add(cli_runner)
    new_password = "another correct horse value"
    cli_runner.invoke(
        app,
        ["user", "update", "--email", "a@example.com", "--password-stdin"],
        input=new_password + "\n",
    )
    reset = [r for r in _audit_rows() if r.action == "password_reset"]
    assert len(reset) == 1
    details: dict[str, Any] = reset[0].details
    assert details == {"via": "cli", "fields": ["password"]}
    # FR-020: the plaintext password is never recorded anywhere in details.
    assert new_password not in repr(details)


def test_delete_writes_deactivate_row(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    _add(cli_runner)
    cli_runner.invoke(app, ["user", "delete", "--email", "a@example.com"])
    deactivate = [r for r in _audit_rows() if r.action == "deactivate"]
    assert len(deactivate) == 1
    assert deactivate[0].details == {"via": "cli"}
