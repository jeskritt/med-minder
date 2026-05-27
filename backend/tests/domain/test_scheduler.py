"""Scheduler wiring tests (Phase 7)."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine

from medminder.db import make_async_session_factory
from medminder.scheduler import build_scheduler, run_dispatch_tick
from medminder.settings import Settings


async def test_build_scheduler_registers_the_tick(engine: AsyncEngine) -> None:
    scheduler = build_scheduler(
        Settings(env="development", reminder_tick_seconds=30),
        make_async_session_factory(engine),
    )
    assert isinstance(scheduler, AsyncIOScheduler)
    assert scheduler.get_job("reminder_dispatch_tick") is not None


async def test_run_dispatch_tick_is_noop_without_data(
    engine: AsyncEngine, migrated_db: None
) -> None:
    # No schedules or reminders committed → a tick is a harmless no-op that
    # exercises the generate + dispatch wiring end to end.
    await run_dispatch_tick(
        Settings(env="development"),
        make_async_session_factory(engine),
    )
