"""Shared test fixtures.

All tests run against the real Postgres service container — SQLite is
not used.  Each test runs inside an outer transaction that is rolled
back at teardown, with a SAVEPOINT for the test body so constraint
failures don't poison the connection.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from medminder.settings import Settings

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_alembic(*args: str) -> None:
    """Run ``python -m alembic ...`` from the backend directory.

    Tests need migrations applied before they can touch any table.
    Running via ``subprocess`` (rather than importing alembic in-process)
    avoids any test-time interaction with the alembic Config singleton.
    """
    env = os.environ.copy()
    subprocess.run(  # noqa: S603 — list argv, sys.executable, shell=False
        [sys.executable, "-m", "alembic", *args],
        cwd=_BACKEND_DIR,
        env=env,
        check=True,
    )


@pytest_asyncio.fixture(scope="session")
async def settings() -> Settings:
    return Settings()


@pytest_asyncio.fixture(scope="session")
async def engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    # NullPool is load-bearing — do NOT swap for a pooled engine.
    # CLI tests invoke ``asyncio.run()`` internally (the Typer commands
    # run their own loop, e.g. backup/restore round-trips), creating
    # and tearing down loops *independently of pytest-asyncio's loop
    # scope*.  asyncpg connections are bound to the loop they were
    # opened in, so a pooled connection from a torn-down loop blows up
    # (or, observed empirically, deadlocks indefinitely) on the next
    # checkout.  Re-verified under pytest-asyncio 1.x session loop
    # scope: removing NullPool still hangs the suite, because the
    # hazard comes from loops the *tests* spawn, not the test/fixture
    # loop pytest-asyncio governs.  NullPool sidesteps it by opening a
    # fresh connection per checkout.
    eng = create_async_engine(
        settings.database_url,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
        poolclass=NullPool,
        future=True,
    )
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def migrated_db(engine: AsyncEngine) -> AsyncIterator[None]:
    """Apply migrations once per session.

    A fresh CI Postgres starts empty; locally, the developer is
    expected to point ``DATABASE_URL`` at a throw-away DB.  The
    migration is idempotent across alembic upgrade head.
    """
    _run_alembic("upgrade", "head")
    yield


@pytest_asyncio.fixture
async def session(
    engine: AsyncEngine, migrated_db: None
) -> AsyncIterator[AsyncSession]:
    """Per-test session wrapped in an outer-transaction-rolled-back."""
    async with engine.connect() as connection:
        trans = await connection.begin()
        async_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        @event.listens_for(async_session.sync_session, "after_transaction_end")
        def _restart_savepoint(sess, transaction):  # type: ignore[no-untyped-def]
            if transaction.nested and not transaction._parent.nested:
                sess.begin_nested()

        try:
            yield async_session
        finally:
            await async_session.close()
            await trans.rollback()
