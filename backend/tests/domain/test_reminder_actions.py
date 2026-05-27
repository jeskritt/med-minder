"""Snooze / dismiss / resolve-on-take orchestration tests (Phase 7, T030)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Reminder, Schedule, ScheduleMedication, User
from medminder.domain.reminder_dispatch import (
    SNOOZE_DURATION,
    ReminderNotFoundError,
    dismiss_reminder,
    resolve_dose_reminders,
    snooze_reminder,
)
from tests.db.factories import make_medication, make_schedule, make_user


async def _dose_reminder(
    session: AsyncSession,
    *,
    user: User,
    schedule: Schedule,
    scheduled_for: datetime,
    status: str = "pending",
) -> Reminder:
    rem = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=schedule.id,
        scheduled_for=scheduled_for,
        status=status,
    )
    session.add(rem)
    await session.flush()
    return rem


async def test_snooze_marks_original_and_creates_successor(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = await _dose_reminder(session, user=user, schedule=sched, scheduled_for=now)

    successor = await snooze_reminder(
        session, user=user, reminder_id=rem.id, now=now
    )
    await session.refresh(rem)

    assert rem.status == "snoozed"
    assert successor.status == "pending"
    assert successor.scheduled_for == now + SNOOZE_DURATION
    assert successor.schedule_id == sched.id
    assert successor.type == "dose"


async def test_snooze_can_repeat(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = await _dose_reminder(session, user=user, schedule=sched, scheduled_for=now)

    first = await snooze_reminder(session, user=user, reminder_id=rem.id, now=now)
    later = now + timedelta(hours=1)
    second = await snooze_reminder(
        session, user=user, reminder_id=first.id, now=later
    )
    assert second.scheduled_for == later + SNOOZE_DURATION


async def test_snooze_foreign_reminder_raises(session: AsyncSession) -> None:
    owner = await make_user(session, email="owner-snz@example.com")
    intruder = await make_user(session, email="intruder-snz@example.com")
    sched = await make_schedule(session, user=owner)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = await _dose_reminder(session, user=owner, schedule=sched, scheduled_for=now)
    with pytest.raises(ReminderNotFoundError):
        await snooze_reminder(session, user=intruder, reminder_id=rem.id, now=now)


async def test_dismiss_is_idempotent(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = await _dose_reminder(session, user=user, schedule=sched, scheduled_for=now)

    await dismiss_reminder(session, user=user, reminder_id=rem.id)
    await session.refresh(rem)
    assert rem.status == "dismissed"
    await dismiss_reminder(session, user=user, reminder_id=rem.id)
    await session.refresh(rem)
    assert rem.status == "dismissed"


async def test_dismiss_foreign_reminder_raises(session: AsyncSession) -> None:
    owner = await make_user(session, email="owner-dis@example.com")
    intruder = await make_user(session, email="intruder-dis@example.com")
    sched = await make_schedule(session, user=owner)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = await _dose_reminder(session, user=owner, schedule=sched, scheduled_for=now)
    with pytest.raises(ReminderNotFoundError):
        await dismiss_reminder(session, user=intruder, reminder_id=rem.id)


async def test_resolve_dismisses_todays_slot_reminders(
    session: AsyncSession,
) -> None:
    user = await make_user(session, timezone_name="UTC")
    sched = await make_schedule(session, user=user)
    med = await make_medication(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await session.flush()

    pending = await _dose_reminder(
        session,
        user=user,
        schedule=sched,
        scheduled_for=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
    )
    snoozed = await _dose_reminder(
        session,
        user=user,
        schedule=sched,
        scheduled_for=datetime(2026, 5, 24, 9, 0, tzinfo=UTC),
        status="snoozed",
    )
    other_day = await _dose_reminder(
        session,
        user=user,
        schedule=sched,
        scheduled_for=datetime(2026, 5, 23, 8, 0, tzinfo=UTC),
    )

    n = await resolve_dose_reminders(
        session,
        user=user,
        schedule_id=sched.id,
        taken_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    assert n == 2
    await session.refresh(pending)
    await session.refresh(snoozed)
    await session.refresh(other_day)
    assert pending.status == "dismissed"
    assert snoozed.status == "dismissed"
    assert other_day.status == "pending"  # different day untouched


async def test_resolve_is_noop_for_unscheduled_dose(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    n = await resolve_dose_reminders(
        session,
        user=user,
        schedule_id=None,
        taken_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    assert n == 0


async def test_snooze_refill_moves_forward_without_duplicate(
    session: AsyncSession,
) -> None:
    # A refill reminder snooze must not create a second open row for the med
    # (uq_reminders_open_refill). It moves the existing warning forward.
    user = await make_user(session)
    med = await make_medication(session, user=user)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rem = Reminder(
        user_id=user.id,
        type="refill",
        medication_id=med.id,
        scheduled_for=now,
        status="sent",
    )
    session.add(rem)
    await session.flush()

    out = await snooze_reminder(session, user=user, reminder_id=rem.id, now=now)
    assert out.id == rem.id
    assert out.status == "pending"
    assert out.scheduled_for == now + SNOOZE_DURATION

    rows = list(
        (
            await session.execute(
                select(Reminder).where(
                    Reminder.medication_id == med.id, Reminder.type == "refill"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
