"""Pure scheduling-math tests (Phase 7, T009): fire times + grace window."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from medminder.domain.reminders import is_within_grace, next_dose_fire_times_utc

# 2026-05-24 is a Sunday; Mon-Fri mask = bits 0..4 set.
_MON_FRI = 0b0011111
_DAILY = 127


def test_next_fire_times_weekday_mask_in_utc() -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)  # Sunday noon UTC
    fires = next_dose_fire_times_utc(
        time_of_day=time(8, 0),
        days_of_week=_MON_FRI,
        tz="America/New_York",
        now=now,
        horizon=timedelta(days=3),
    )
    # 08:00 EDT == 12:00 UTC; Sunday excluded, only Mon 25 + Tue 26 in range.
    assert fires == [
        datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
    ]


def test_next_fire_times_includes_today_when_still_future() -> None:
    now = datetime(2026, 5, 24, 6, 0, tzinfo=UTC)  # 02:00 EDT, before 08:00
    fires = next_dose_fire_times_utc(
        time_of_day=time(8, 0),
        days_of_week=_DAILY,
        tz="America/New_York",
        now=now,
        horizon=timedelta(hours=24),
    )
    assert datetime(2026, 5, 24, 12, 0, tzinfo=UTC) in fires


def test_next_fire_times_excludes_already_passed_today() -> None:
    now = datetime(2026, 5, 24, 13, 0, tzinfo=UTC)  # 09:00 EDT, after 08:00
    fires = next_dose_fire_times_utc(
        time_of_day=time(8, 0),
        days_of_week=_DAILY,
        tz="America/New_York",
        now=now,
        horizon=timedelta(hours=24),
    )
    assert datetime(2026, 5, 24, 12, 0, tzinfo=UTC) not in fires


def test_is_within_grace_boundaries() -> None:
    sf = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    grace = timedelta(minutes=15)
    assert is_within_grace(scheduled_for=sf, now=sf, grace=grace)
    assert is_within_grace(scheduled_for=sf, now=sf + grace, grace=grace)
    assert not is_within_grace(
        scheduled_for=sf, now=sf + timedelta(minutes=16), grace=grace
    )
    # Not yet due:
    assert not is_within_grace(
        scheduled_for=sf, now=sf - timedelta(minutes=1), grace=grace
    )
