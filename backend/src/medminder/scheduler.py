"""In-process reminder scheduler (Phase 7, ADR-0002 / plan research D1).

A single recurring ``AsyncIOScheduler`` job (the "dispatch tick") generates
upcoming dose reminders and dispatches due ones. The durable state is the
``reminders`` table — the scheduler uses the default in-memory job store and
re-registers its one job on every startup, so no ``SQLAlchemyJobStore`` (and
no extra DDL under the DML-only runtime role) is needed.

Started/stopped from the FastAPI lifespan, gated by ``reminders_enabled`` so
tests / CI / Alembic never spin up a background loop.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# APScheduler ships no type stubs (not py.typed); isolated suppression here.
from apscheduler.schedulers.asyncio import (  # type: ignore[import-untyped]
    AsyncIOScheduler,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medminder.db.models import PushSubscription
from medminder.domain.push import PushResult, send_web_push
from medminder.domain.reminder_dispatch import (
    dispatch_due_reminders,
    generate_due_dose_reminders,
)
from medminder.settings import Settings

_TICK_JOB_ID = "reminder_dispatch_tick"


def build_scheduler(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIOScheduler:
    """Build the scheduler with its single recurring dispatch tick.

    Call ``.start()`` on the returned scheduler from the app lifespan and
    ``.shutdown(wait=False)`` on teardown.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def _tick() -> None:
        async with session_factory() as session, session.begin():
            now = datetime.now(UTC)
            await generate_due_dose_reminders(session, now=now)

            async def _send(
                subscription: PushSubscription, payload: dict[str, Any]
            ) -> PushResult:
                return await send_web_push(
                    subscription=subscription,
                    payload=payload,
                    settings=settings,
                )

            await dispatch_due_reminders(
                session,
                now=now,
                grace=timedelta(minutes=settings.reminder_grace_minutes),
                send=_send,
            )

    scheduler.add_job(
        _tick,
        "interval",
        seconds=settings.reminder_tick_seconds,
        id=_TICK_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


__all__ = ["build_scheduler"]
