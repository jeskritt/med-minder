"""Tests for the ``reminders`` table — D3 CHECK constraint + cascades."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Reminder

from .factories import make_medication, make_schedule, make_user, utcnow


async def test_dose_reminder_with_schedule(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    r = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched.id,
        scheduled_for=utcnow(),
    )
    session.add(r)
    await session.flush()
    assert r.status == "pending"


async def test_refill_reminder_with_medication(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    r = Reminder(
        user_id=user.id,
        type="refill",
        medication_id=med.id,
        scheduled_for=utcnow(),
    )
    session.add(r)
    await session.flush()
    assert r.id is not None


async def test_dose_with_medication_rejected(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    bad = Reminder(
        user_id=user.id,
        type="dose",
        medication_id=med.id,
        schedule_id=None,
        scheduled_for=utcnow(),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_refill_with_schedule_rejected(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    bad = Reminder(
        user_id=user.id,
        type="refill",
        medication_id=None,
        schedule_id=sched.id,
        scheduled_for=utcnow(),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_dose_without_schedule_rejected(session: AsyncSession) -> None:
    user = await make_user(session)
    bad = Reminder(
        user_id=user.id,
        type="dose",
        medication_id=None,
        schedule_id=None,
        scheduled_for=utcnow(),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_cascade_via_refill_reminder(session: AsyncSession) -> None:
    """A refill reminder references medications, not schedules.  Both
    medications and reminders depend on the user, but ``medications``
    is RESTRICT and ``reminders`` is CASCADE — deleting the user is
    blocked by the medication, exercising the asymmetry.
    """
    user = await make_user(session)
    med = await make_medication(session, user=user)
    session.add(
        Reminder(
            user_id=user.id,
            type="refill",
            medication_id=med.id,
            scheduled_for=utcnow(),
        )
    )
    await session.flush()
    await session.delete(user)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_schedule_delete_cascades_reminder(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    r = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched.id,
        scheduled_for=utcnow(),
    )
    session.add(r)
    await session.flush()
    await session.delete(sched)
    await session.flush()
    rows = (
        await session.execute(select(Reminder).where(Reminder.user_id == user.id))
    ).all()
    assert rows == []
