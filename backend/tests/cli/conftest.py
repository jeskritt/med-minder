"""CLI test fixtures.

CLI commands open their own sessions and run real transactions, so
they bypass the savepoint-rolled-back ``session`` fixture used by
db-level tests.  Instead we truncate the relevant tables after each
CLI test to keep them isolated.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from typer.testing import CliRunner

from medminder.cli.main import app


@pytest.fixture
def cli_runner(monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "200")
    return CliRunner()


@pytest.fixture
def cli_app():  # type: ignore[no-untyped-def]
    return app


@pytest_asyncio.fixture
async def truncate_users(
    engine: AsyncEngine, migrated_db: None
) -> AsyncIterator[None]:
    """Wipe ``users`` (cascading to dependent tables) after each test."""
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users CASCADE"))
