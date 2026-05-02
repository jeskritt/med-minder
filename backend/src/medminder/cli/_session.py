"""Async session scaffolding for CLI commands.

Each command is a single transaction.  ``run_with_session`` constructs
the engine, hands the caller a session inside ``session.begin()``, and
disposes the engine on exit.  Errors propagate so the transaction
rolls back; the CLI maps domain exceptions to non-zero exit codes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db import make_async_engine, make_async_session_factory
from medminder.settings import Settings


async def _run[T](coro_factory: Callable[[AsyncSession], Awaitable[T]]) -> T:
    settings = Settings()
    engine = make_async_engine(settings)
    factory = make_async_session_factory(engine)
    try:
        async with factory() as session:
            async with session.begin():
                return await coro_factory(session)
    finally:
        await engine.dispose()


def run_with_session[T](
    coro_factory: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    """Sync wrapper Typer commands call into."""
    return asyncio.run(_run(coro_factory))
