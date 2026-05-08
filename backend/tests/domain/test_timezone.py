"""Tests for ``resolve_today_bounds`` (Phase 4)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from medminder.domain.timezone import (
    InvalidTimezoneError,
    resolve_today_bounds,
)


def test_basic_utc_window() -> None:
    bounds = resolve_today_bounds(
        user_tz="UTC", target_date=date(2026, 5, 8)
    )
    assert bounds.timezone_name == "UTC"
    assert bounds.start_utc == datetime(2026, 5, 8, 0, 0, tzinfo=UTC)
    assert bounds.end_utc == datetime(2026, 5, 9, 0, 0, tzinfo=UTC)
    assert bounds.day_of_week == 4  # Friday
    assert bounds.target_date == date(2026, 5, 8)


def test_override_wins_over_user_tz() -> None:
    bounds = resolve_today_bounds(
        user_tz="UTC",
        override_tz="America/Los_Angeles",
        target_date=date(2026, 5, 8),
    )
    assert bounds.timezone_name == "America/Los_Angeles"
    # 2026-05-08 00:00 PT is 2026-05-08 07:00 UTC (PDT, UTC-7).
    assert bounds.start_utc == datetime(2026, 5, 8, 7, 0, tzinfo=UTC)
    assert bounds.end_utc == datetime(2026, 5, 9, 7, 0, tzinfo=UTC)


def test_window_is_24_hours_in_normal_zone() -> None:
    """Outside DST transitions the window is exactly one day."""
    bounds = resolve_today_bounds(
        user_tz="America/Los_Angeles", target_date=date(2026, 5, 8)
    )
    assert bounds.end_utc - bounds.start_utc == timedelta(hours=24)


def test_dst_spring_forward_window_is_23h() -> None:
    """On 2026-03-08 the US/Pacific zone springs forward, losing an hour."""
    bounds = resolve_today_bounds(
        user_tz="America/Los_Angeles", target_date=date(2026, 3, 8)
    )
    assert bounds.end_utc - bounds.start_utc == timedelta(hours=23)


def test_dst_fall_back_window_is_25h() -> None:
    """On 2026-11-01 the US/Pacific zone falls back, gaining an hour."""
    bounds = resolve_today_bounds(
        user_tz="America/Los_Angeles", target_date=date(2026, 11, 1)
    )
    assert bounds.end_utc - bounds.start_utc == timedelta(hours=25)


def test_midnight_wrap_dow() -> None:
    """The dow-bit reflects the local date, not UTC."""
    # 2026-05-08 22:00 PT = 2026-05-09 05:00 UTC. We pin date=8 and
    # expect Friday (4), not Saturday.
    bounds = resolve_today_bounds(
        user_tz="America/Los_Angeles", target_date=date(2026, 5, 8)
    )
    assert bounds.day_of_week == 4


def test_invalid_zone_raises() -> None:
    with pytest.raises(InvalidTimezoneError):
        resolve_today_bounds(
            user_tz="UTC", override_tz="Nowhere/Nope", target_date=date(2026, 5, 8)
        )


def test_default_target_date_uses_zone_now() -> None:
    """Sanity check: default target_date is the current date in the chosen zone."""
    bounds = resolve_today_bounds(user_tz="UTC")
    assert bounds.target_date == datetime.now(ZoneInfo("UTC")).date()
