"""End-to-end backup/restore round-trip tests.

These tests require ``pg_dump`` and ``pg_restore`` on PATH.  They fail
loudly if missing — Phase 1 deliberately does not silently skip.
"""

from __future__ import annotations

import platform
import shutil
import stat
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from typer.testing import CliRunner

from medminder.cli.db import PHI_WARNING, WINDOWS_ACL_WARNING
from medminder.cli.main import app
from medminder.domain.users import (
    get_user_by_email,
    verify_password,
)

GOOD_PASSWORD = "correct horse battery staple"

@pytest.fixture(autouse=True)
def _require_pg_client_tools() -> None:
    """Fail loudly (don't silently skip) if pg_dump/pg_restore are absent."""
    missing = [
        tool for tool in ("pg_dump", "pg_restore") if shutil.which(tool) is None
    ]
    if missing:
        pytest.fail(
            f"{', '.join(missing)} not found on PATH. Install Postgres "
            "client tools (Linux: apt-get install postgresql-client; "
            "Windows: https://www.postgresql.org/download/windows/) "
            "and ensure they are on PATH.",
            pytrace=False,
        )


def test_backup_writes_file_with_phi_warning(
    cli_runner: CliRunner,
    truncate_users: None,
    tmp_path: Path,
) -> None:
    cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    out = tmp_path / "backup.dump"
    result = cli_runner.invoke(app, ["db", "backup", "--out", str(out)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out.exists()
    assert out.stat().st_size > 0
    combined = result.stdout + result.stderr
    assert PHI_WARNING in combined

    if platform.system() == "Windows":
        assert WINDOWS_ACL_WARNING in combined
    else:
        mode = stat.S_IMODE(out.stat().st_mode)
        assert mode == 0o600


def test_restore_requires_yes(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    fake = tmp_path / "any.dump"
    fake.write_bytes(b"x")
    result = cli_runner.invoke(
        app, ["db", "restore", "--in", str(fake)]
    )
    assert result.exit_code != 0


async def _row_count(engine: AsyncEngine, table: str) -> int:
    """Count rows in a table.

    The table name is interpolated into the SQL string because count(*)
    cannot bind an identifier.  ``table`` is a hard-coded test literal,
    not user input — bandit's warning is irrelevant here.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608
        return int(result.scalar_one())


def test_round_trip(
    cli_runner: CliRunner,
    truncate_users: None,
    tmp_path: Path,
    engine: AsyncEngine,
) -> None:
    """Seed → backup → drop schema → restore → verify rows + password."""
    import asyncio

    cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    cli_runner.invoke(
        app,
        ["user", "add", "--email", "b@example.com", "--name", "B", "--role", "admin"],
        input=GOOD_PASSWORD + "\n",
    )
    pre_count = asyncio.run(_row_count(engine, "users"))
    assert pre_count == 2

    out = tmp_path / "round.dump"
    backed = cli_runner.invoke(app, ["db", "backup", "--out", str(out)])
    assert backed.exit_code == 0, backed.stdout + backed.stderr

    # Wipe everything so restore has work to do.
    async def _wipe() -> None:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE users CASCADE"))

    asyncio.run(_wipe())
    assert asyncio.run(_row_count(engine, "users")) == 0

    restored = cli_runner.invoke(
        app, ["db", "restore", "--in", str(out), "--yes"]
    )
    assert restored.exit_code == 0, restored.stdout + restored.stderr
    assert asyncio.run(_row_count(engine, "users")) == 2

    # Argon2id passwords still verify post-restore.
    from medminder.cli._session import run_with_session

    async def fetch(session):  # type: ignore[no-untyped-def]
        return await get_user_by_email(session, email="a@example.com")

    user = run_with_session(fetch)
    assert user is not None
    assert verify_password(user.password_hash, GOOD_PASSWORD)
