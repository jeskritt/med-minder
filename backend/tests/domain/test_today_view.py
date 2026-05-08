"""Tests for ``today_view`` (Phase 4)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication
from medminder.domain.doses import today_view, void_dose
from tests.db.factories import (
    make_dose,
    make_medication,
    make_schedule,
    make_user,
)


async def _link(
    session: AsyncSession, schedule_id: object, medication_id: object
) -> None:
    session.add(
        ScheduleMedication(schedule_id=schedule_id, medication_id=medication_id)
    )
    await session.flush()


async def test_per_slot_keying(session: AsyncSession) -> None:
    """A medication on two schedules appears as two items, ordered by time."""
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user, name="Lisinopril")
    morning = await make_schedule(
        session, user=user, label="Morning", time_of_day=time(8, 0)
    )
    evening = await make_schedule(
        session, user=user, label="Evening", time_of_day=time(20, 0)
    )
    await _link(session, morning.id, med.id)
    await _link(session, evening.id, med.id)

    view = await today_view(session, user=user, target_date=date(2026, 5, 8))
    assert len(view.items) == 2
    assert view.items[0].schedule_id == morning.id
    assert view.items[1].schedule_id == evening.id
    assert all(item.dose is None for item in view.items)


async def test_only_session_user_data_returned(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    other = await make_user(session, timezone_name="UTC")
    user_med = await make_medication(session, user=user)
    other_med = await make_medication(session, user=other)
    user_sched = await make_schedule(session, user=user)
    other_sched = await make_schedule(session, user=other)
    await _link(session, user_sched.id, user_med.id)
    await _link(session, other_sched.id, other_med.id)

    view = await today_view(session, user=user, target_date=date(2026, 5, 8))
    assert len(view.items) == 1
    assert view.items[0].medication_id == user_med.id


async def test_voided_dose_excluded(session: AsyncSession) -> None:
    """A voided dose must not surface; the slot looks "untaken" again."""
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    await _link(session, sched.id, med.id)

    dose = await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )
    await void_dose(session, user=user, dose_id=dose.id)

    view = await today_view(session, user=user, target_date=date(2026, 5, 8))
    assert len(view.items) == 1
    assert view.items[0].dose is None


async def test_effective_dose_surfaces(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    await _link(session, sched.id, med.id)

    dose = await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )
    view = await today_view(session, user=user, target_date=date(2026, 5, 8))
    assert len(view.items) == 1
    assert view.items[0].dose is not None
    assert view.items[0].dose.id == dose.id


async def test_soft_deleted_medication_excluded(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    await _link(session, sched.id, med.id)
    med.deleted_at = datetime.now(UTC)
    await session.flush()
    view = await today_view(session, user=user, target_date=date(2026, 5, 8))
    assert view.items == []


async def test_soft_deleted_schedule_excluded(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    await _link(session, sched.id, med.id)
    sched.deleted_at = datetime.now(UTC)
    await session.flush()
    view = await today_view(session, user=user, target_date=date(2026, 5, 8))
    assert view.items == []


async def test_timezone_override_changes_window(session: AsyncSession) -> None:
    """Same fixture, two zones, different days — different item sets.

    A dose taken at 2026-05-08 03:00 UTC is on 2026-05-08 in UTC but on
    2026-05-07 in America/Los_Angeles. Asking for date=2026-05-08 in
    each zone surfaces the dose in only one of them.
    """
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user, days_of_week=127)
    await _link(session, sched.id, med.id)
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 3, 0, tzinfo=UTC),
    )

    utc_view = await today_view(
        session, user=user, target_date=date(2026, 5, 8)
    )
    pacific_view = await today_view(
        session,
        user=user,
        timezone_override="America/Los_Angeles",
        target_date=date(2026, 5, 8),
    )

    assert utc_view.items[0].dose is not None
    assert pacific_view.items[0].dose is None
