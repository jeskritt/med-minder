"""Tests for the derived adherence domain (Phase 9 / ADR-0016)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication
from medminder.domain.adherence import (
    AdherenceRangeError,
    DayStatus,
    MedicationNotFoundError,
    classify_day,
    compute_course_progress,
    compute_medication_adherence,
    window_adherence_pct,
)
from medminder.domain.doses import void_dose
from tests.db.factories import make_dose, make_medication, make_schedule, make_user

# A reference "now" well past early-May target days, so those slots are
# unambiguously past the 4h missed tolerance.
NOW = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)


async def _link(session: AsyncSession, schedule_id: object, med_id: object) -> None:
    session.add(ScheduleMedication(schedule_id=schedule_id, medication_id=med_id))
    await session.flush()


def _bit(d: date) -> int:
    return 1 << d.weekday()


# --- pure classifiers -------------------------------------------------------


def test_classify_no_schedule_with_dose_is_taken() -> None:
    status, expected, taken = classify_day(
        expected_slot_times=[], doses_count=1, now=NOW
    )
    assert (status, expected, taken) == (DayStatus.TAKEN, 0, 0)


def test_classify_no_schedule_no_dose_is_inactive() -> None:
    status, expected, taken = classify_day(
        expected_slot_times=[], doses_count=0, now=NOW
    )
    assert (status, expected, taken) == (DayStatus.INACTIVE, 0, 0)


def test_classify_future_when_all_slots_within_tolerance() -> None:
    soon = NOW + timedelta(hours=1)
    status, _, taken = classify_day(
        expected_slot_times=[soon], doses_count=0, now=NOW
    )
    assert status is DayStatus.FUTURE
    assert taken == 0


def test_classify_missed_when_past_tolerance() -> None:
    past = NOW - timedelta(hours=5)
    status, _, _ = classify_day(expected_slot_times=[past], doses_count=0, now=NOW)
    assert status is DayStatus.MISSED


def test_classify_partial_some_taken() -> None:
    past = NOW - timedelta(hours=5)
    status, expected, taken = classify_day(
        expected_slot_times=[past, past], doses_count=1, now=NOW
    )
    assert (status, expected, taken) == (DayStatus.PARTIAL, 2, 1)


def test_window_pct_excludes_inactive_and_future() -> None:
    from medminder.domain.adherence import DayAdherence

    days = [
        DayAdherence(date(2026, 5, 1), expected=2, taken=2, status=DayStatus.TAKEN),
        DayAdherence(date(2026, 5, 2), expected=2, taken=1, status=DayStatus.PARTIAL),
        DayAdherence(date(2026, 5, 3), expected=0, taken=0, status=DayStatus.INACTIVE),
        DayAdherence(date(2026, 5, 4), expected=1, taken=0, status=DayStatus.FUTURE),
    ]
    # taken 3 / expected 4 over scored days (inactive + future excluded) = 75.0
    assert window_adherence_pct(days) == 75.0


def test_window_pct_none_when_nothing_scored() -> None:
    assert window_adherence_pct([]) is None


# --- compute_medication_adherence (DB) --------------------------------------


async def test_all_doses_taken_day_is_green(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user, time_of_day=time(8, 0))
    await _link(session, sched.id, med.id)
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 8, 5, tzinfo=UTC),
    )

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 8),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    assert len(result.days) == 1
    assert result.days[0].status is DayStatus.TAKEN
    assert result.adherence_pct == 100.0


async def test_partial_day(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    morning = await make_schedule(session, user=user, time_of_day=time(8, 0))
    evening = await make_schedule(session, user=user, time_of_day=time(20, 0))
    await _link(session, morning.id, med.id)
    await _link(session, evening.id, med.id)
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=morning,
        taken_at=datetime(2026, 5, 8, 8, 5, tzinfo=UTC),
    )

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 8),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    assert result.days[0].status is DayStatus.PARTIAL
    assert result.days[0].expected == 2
    assert result.days[0].taken == 1
    assert result.adherence_pct == 50.0


async def test_missed_past_day(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user, time_of_day=time(8, 0))
    await _link(session, sched.id, med.id)

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 8),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    assert result.days[0].status is DayStatus.MISSED
    assert result.adherence_pct == 0.0


async def test_off_day_of_week_is_inactive_not_missed(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    target = date(2026, 5, 9)  # Saturday
    # Schedule excludes Saturday's weekday bit.
    weekday_only = 127 & ~_bit(target)
    sched = await make_schedule(
        session, user=user, time_of_day=time(8, 0), days_of_week=weekday_only
    )
    await _link(session, sched.id, med.id)

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=target,
        to_date=target,
        now=NOW,
    )
    assert result.days[0].status is DayStatus.INACTIVE
    # No scored day → no percentage.
    assert result.adherence_pct is None


async def test_prn_med_never_missed(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)  # no schedules linked
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 7),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    by_day = {d.date: d.status for d in result.days}
    assert by_day[date(2026, 5, 8)] is DayStatus.TAKEN
    assert by_day[date(2026, 5, 7)] is DayStatus.INACTIVE
    assert DayStatus.MISSED not in by_day.values()
    assert result.adherence_pct is None  # PRN → no percentage


async def test_voided_dose_excluded(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user, time_of_day=time(8, 0))
    await _link(session, sched.id, med.id)
    dose = await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 8, 5, tzinfo=UTC),
    )
    await void_dose(session, user=user, dose_id=dose.id)

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 8),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    assert result.days[0].status is DayStatus.MISSED


async def test_timezone_bucketing(session: AsyncSession) -> None:
    """A 03:00 UTC dose lands on 05-08 in UTC but 05-07 in Pacific."""
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    sched = await make_schedule(
        session, user=user, time_of_day=time(2, 0), days_of_week=127
    )
    await _link(session, sched.id, med.id)
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 3, 0, tzinfo=UTC),
    )

    utc = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 8),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    assert utc.days[0].status is DayStatus.TAKEN

    pacific = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 8),
        to_date=date(2026, 5, 8),
        timezone_override="America/Los_Angeles",
        now=NOW,
    )
    # In Pacific the dose belongs to 05-07, so 05-08 is missed.
    assert pacific.days[0].status is DayStatus.MISSED


async def test_inactive_before_start_date(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    med.start_date = date(2026, 5, 8)
    await session.flush()
    sched = await make_schedule(session, user=user, time_of_day=time(8, 0))
    await _link(session, sched.id, med.id)

    result = await compute_medication_adherence(
        session,
        user=user,
        medication_id=med.id,
        from_date=date(2026, 5, 7),
        to_date=date(2026, 5, 8),
        now=NOW,
    )
    by_day = {d.date: d.status for d in result.days}
    assert by_day[date(2026, 5, 7)] is DayStatus.INACTIVE
    assert by_day[date(2026, 5, 8)] is DayStatus.MISSED


async def test_inverted_range_raises(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    with pytest.raises(AdherenceRangeError):
        await compute_medication_adherence(
            session,
            user=user,
            medication_id=med.id,
            from_date=date(2026, 5, 10),
            to_date=date(2026, 5, 8),
        )


async def test_over_cap_range_raises(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    with pytest.raises(AdherenceRangeError):
        await compute_medication_adherence(
            session,
            user=user,
            medication_id=med.id,
            from_date=date(2024, 1, 1),
            to_date=date(2026, 1, 1),
        )


async def test_other_users_med_raises(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    other = await make_user(session, timezone_name="UTC")
    other_med = await make_medication(session, user=other)
    with pytest.raises(MedicationNotFoundError):
        await compute_medication_adherence(
            session,
            user=user,
            medication_id=other_med.id,
            from_date=date(2026, 5, 8),
            to_date=date(2026, 5, 8),
        )


# --- course progress --------------------------------------------------------


async def test_course_progress_counts_and_completes(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    med.total_doses = 3
    await session.flush()
    for hour in (8, 12, 18):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=datetime(2026, 5, 8, hour, 0, tzinfo=UTC),
        )

    progress = await compute_course_progress(session, user=user, medication=med)
    assert progress is not None
    assert (progress.total, progress.taken, progress.complete) == (3, 3, True)


async def test_course_progress_decrements_on_void(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)
    med.total_doses = 14
    await session.flush()
    first = await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 20, 0, tzinfo=UTC),
    )
    await void_dose(session, user=user, dose_id=first.id)

    progress = await compute_course_progress(session, user=user, medication=med)
    assert progress is not None
    assert (progress.taken, progress.complete) == (1, False)


async def test_course_progress_none_without_total(session: AsyncSession) -> None:
    user = await make_user(session, timezone_name="UTC")
    med = await make_medication(session, user=user)  # total_doses is None
    assert await compute_course_progress(session, user=user, medication=med) is None
