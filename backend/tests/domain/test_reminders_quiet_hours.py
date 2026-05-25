"""Pure quiet-hours deferral tests (Phase 7, T036)."""

from __future__ import annotations

from datetime import UTC, datetime, time

from medminder.domain.reminders import defer_for_quiet_hours

_Q_START = time(22, 0)
_Q_END = time(7, 0)


def test_wrap_early_morning_defers_to_window_end_same_day() -> None:
    fire = datetime(2026, 5, 24, 2, 0, tzinfo=UTC)  # 02:00, inside 22:00-07:00
    deferred = defer_for_quiet_hours(
        fire_utc=fire, tz="UTC", quiet_start=_Q_START, quiet_end=_Q_END
    )
    assert deferred == datetime(2026, 5, 24, 7, 0, tzinfo=UTC)


def test_wrap_late_evening_defers_to_next_day_end() -> None:
    fire = datetime(2026, 5, 24, 23, 0, tzinfo=UTC)  # late evening, inside
    deferred = defer_for_quiet_hours(
        fire_utc=fire, tz="UTC", quiet_start=_Q_START, quiet_end=_Q_END
    )
    assert deferred == datetime(2026, 5, 25, 7, 0, tzinfo=UTC)


def test_end_boundary_is_exclusive() -> None:
    fire = datetime(2026, 5, 24, 7, 0, tzinfo=UTC)  # exactly window end
    assert (
        defer_for_quiet_hours(
            fire_utc=fire, tz="UTC", quiet_start=_Q_START, quiet_end=_Q_END
        )
        is None
    )


def test_outside_window_not_deferred() -> None:
    fire = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    assert (
        defer_for_quiet_hours(
            fire_utc=fire, tz="UTC", quiet_start=_Q_START, quiet_end=_Q_END
        )
        is None
    )


def test_same_day_window_defers_to_end() -> None:
    fire = datetime(2026, 5, 24, 13, 30, tzinfo=UTC)
    deferred = defer_for_quiet_hours(
        fire_utc=fire, tz="UTC", quiet_start=time(13, 0), quiet_end=time(14, 0)
    )
    assert deferred == datetime(2026, 5, 24, 14, 0, tzinfo=UTC)


def test_no_quiet_hours_set_returns_none() -> None:
    fire = datetime(2026, 5, 24, 2, 0, tzinfo=UTC)
    assert (
        defer_for_quiet_hours(
            fire_utc=fire, tz="UTC", quiet_start=None, quiet_end=None
        )
        is None
    )
