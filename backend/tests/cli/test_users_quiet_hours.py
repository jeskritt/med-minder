"""CLI quiet-hours config tests (Phase 7, T036b).

CLI commands run their own event loop (Typer + asyncio.run), so these tests
are synchronous and verify DB effects via a fresh ``asyncio.run`` over the
NullPool engine (the same pattern the CLI uses internally).
"""

from __future__ import annotations

import asyncio
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from typer.testing import CliRunner

from medminder.cli.main import app
from medminder.db.models import User

GOOD_PASSWORD = "correct horse battery staple"


def _add_user(cli_runner: CliRunner, email: str) -> None:
    result = cli_runner.invoke(
        app,
        ["user", "add", "--email", email, "--name", "Q", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    assert result.exit_code == 0, result.stdout + result.stderr


def _read_quiet_hours(
    engine: AsyncEngine, email: str
) -> tuple[time | None, time | None]:
    async def _query() -> tuple[time | None, time | None]:
        async with engine.connect() as conn, AsyncSession(bind=conn) as s:
            row = (
                await s.execute(
                    select(
                        User.quiet_hours_start, User.quiet_hours_end
                    ).where(func.lower(User.email) == email.lower())
                )
            ).one()
            return (row[0], row[1])

    return asyncio.run(_query())


def test_update_sets_quiet_hours(
    cli_runner: CliRunner, truncate_users: None, engine: AsyncEngine
) -> None:
    email = "qh-set@example.com"
    _add_user(cli_runner, email)
    result = cli_runner.invoke(
        app,
        [
            "user", "update", "--email", email,
            "--quiet-hours-start", "22:00",
            "--quiet-hours-end", "07:00",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert _read_quiet_hours(engine, email) == (time(22, 0), time(7, 0))


def test_update_clears_quiet_hours(
    cli_runner: CliRunner, truncate_users: None, engine: AsyncEngine
) -> None:
    email = "qh-clear@example.com"
    _add_user(cli_runner, email)
    cli_runner.invoke(
        app,
        [
            "user", "update", "--email", email,
            "--quiet-hours-start", "22:00", "--quiet-hours-end", "07:00",
        ],
    )
    result = cli_runner.invoke(
        app, ["user", "update", "--email", email, "--clear-quiet-hours"]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert _read_quiet_hours(engine, email) == (None, None)


def test_update_invalid_time_rejected(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    email = "qh-bad@example.com"
    _add_user(cli_runner, email)
    result = cli_runner.invoke(
        app,
        [
            "user", "update", "--email", email,
            "--quiet-hours-start", "25:00", "--quiet-hours-end", "07:00",
        ],
    )
    assert result.exit_code != 0


def test_update_requires_both_bounds(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    email = "qh-half@example.com"
    _add_user(cli_runner, email)
    result = cli_runner.invoke(
        app,
        ["user", "update", "--email", email, "--quiet-hours-start", "22:00"],
    )
    assert result.exit_code != 0
