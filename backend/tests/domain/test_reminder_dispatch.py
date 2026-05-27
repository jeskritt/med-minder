"""Generate + dispatch orchestration tests (Phase 7, T010).

Real Postgres (session fixture) with a fake push sender — no network.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import (
    Medication,
    PushSubscription,
    Reminder,
    Schedule,
    ScheduleMedication,
)
from medminder.domain.push import PushResult
from medminder.domain.reminder_dispatch import (
    dispatch_due_reminders,
    generate_due_dose_reminders,
)
from tests.db.factories import make_medication, make_schedule, make_user


async def _attach(
    session: AsyncSession, *, schedule: Schedule, medication: Medication
) -> None:
    session.add(
        ScheduleMedication(schedule_id=schedule.id, medication_id=medication.id)
    )
    await session.flush()


async def test_generate_is_per_slot_and_idempotent(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    sched = await make_schedule(
        session, user=user, time_of_day=time(8, 0), days_of_week=127
    )
    med = await make_medication(session, user=user)
    await _attach(session, schedule=sched, medication=med)

    now = datetime(2026, 5, 24, 0, 0, tzinfo=UTC)
    created = await generate_due_dose_reminders(
        session, now=now, horizon=timedelta(days=2)
    )
    assert created >= 1
    # Re-running creates nothing new.
    assert await generate_due_dose_reminders(
        session, now=now, horizon=timedelta(days=2)
    ) == 0

    rows = list(
        (
            await session.execute(
                select(Reminder).where(Reminder.schedule_id == sched.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows
    assert all(
        r.type == "dose"
        and r.status == "pending"
        and r.medication_id is None
        and r.schedule_id == sched.id
        for r in rows
    )


async def test_generate_skips_schedule_without_live_med(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    await make_schedule(session, user=user)  # no medication attached
    now = datetime(2026, 5, 24, 0, 0, tzinfo=UTC)
    assert await generate_due_dose_reminders(
        session, now=now, horizon=timedelta(days=1)
    ) == 0


async def test_dispatch_sends_within_grace_and_marks_sent(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user, label="Morning")
    med = await make_medication(session, user=user, name="Aspirin")
    await _attach(session, schedule=sched, medication=med)
    session.add(
        PushSubscription(
            user_id=user.id,
            endpoint="https://push.example/abc",
            p256dh="p",
            auth="a",
        )
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched.id,
        scheduled_for=now,
        status="pending",
    )
    session.add(rem)
    await session.flush()

    calls: list[dict[str, Any]] = []

    async def fake_send(
        _sub: PushSubscription, payload: dict[str, Any]
    ) -> PushResult:
        calls.append(payload)
        return PushResult(delivered=True, gone=False)

    n = await dispatch_due_reminders(
        session, now=now, grace=timedelta(minutes=15), send=fake_send
    )
    assert n == 1
    await session.refresh(rem)
    assert rem.status == "sent"
    assert calls and "Aspirin" in calls[0]["title"]


async def test_dispatch_overdue_stays_pending(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched.id,
        scheduled_for=now - timedelta(hours=1),  # older than grace
        status="pending",
    )
    session.add(rem)
    await session.flush()

    async def fake_send(
        _sub: PushSubscription, _payload: dict[str, Any]
    ) -> PushResult:
        return PushResult(delivered=True, gone=False)

    n = await dispatch_due_reminders(
        session, now=now, grace=timedelta(minutes=15), send=fake_send
    )
    assert n == 0
    await session.refresh(rem)
    assert rem.status == "pending"


async def test_dispatch_deletes_gone_subscription(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    session.add(
        PushSubscription(
            user_id=user.id,
            endpoint="https://push.example/gone",
            p256dh="p",
            auth="a",
        )
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    session.add(
        Reminder(
            user_id=user.id,
            type="dose",
            schedule_id=sched.id,
            scheduled_for=now,
            status="pending",
        )
    )
    await session.flush()

    async def fake_send(
        _sub: PushSubscription, _payload: dict[str, Any]
    ) -> PushResult:
        return PushResult(delivered=False, gone=True)

    await dispatch_due_reminders(
        session, now=now, grace=timedelta(minutes=15), send=fake_send
    )
    remaining = list(
        (
            await session.execute(
                select(PushSubscription).where(
                    PushSubscription.user_id == user.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert remaining == []


async def test_dispatch_defers_reminder_during_quiet_hours(
    session: AsyncSession,
) -> None:
    user = await make_user(session, timezone_name="UTC")
    user.quiet_hours_start = time(22, 0)
    user.quiet_hours_end = time(7, 0)
    sched = await make_schedule(session, user=user)
    await session.flush()
    now = datetime(2026, 5, 24, 2, 0, tzinfo=UTC)  # inside 22:00-07:00
    rem = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched.id,
        scheduled_for=now,
        status="pending",
    )
    session.add(rem)
    await session.flush()

    sent: list[dict[str, Any]] = []

    async def fake_send(
        _sub: PushSubscription, payload: dict[str, Any]
    ) -> PushResult:
        sent.append(payload)
        return PushResult(delivered=True, gone=False)

    n = await dispatch_due_reminders(
        session, now=now, grace=timedelta(minutes=15), send=fake_send
    )
    assert n == 0  # deferred, not delivered
    assert sent == []
    await session.refresh(rem)
    assert rem.status == "pending"
    assert rem.scheduled_for == datetime(2026, 5, 24, 7, 0, tzinfo=UTC)
