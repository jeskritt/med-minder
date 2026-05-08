"""Timezone helpers for the Today view.

Phase 4 needs three things, computed in the user's IANA zone:

* The ``[start_utc, end_utc)`` half-open range covering the target day.
* The Mon=0…Sun=6 day-of-week bit (matching ``schedules.days_of_week``).
* The IANA zone name actually used (so the response can echo it).

Lifted into its own module so DST / midnight-wrap edge cases live in one
testable place rather than scattered through ``today_view``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezoneError(ValueError):
    """Raised when a caller-supplied IANA zone name is unknown."""


@dataclass(frozen=True)
class TodayBounds:
    target_date: date
    timezone_name: str
    start_utc: datetime
    end_utc: datetime
    day_of_week: int


def _resolve_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimezoneError(name) from exc


def resolve_today_bounds(
    *,
    user_tz: str,
    override_tz: str | None = None,
    target_date: date | None = None,
) -> TodayBounds:
    """Compute the UTC bounds and dow-bit for "today" in the user's zone.

    Parameters
    ----------
    user_tz:
        IANA zone from ``users.timezone``.
    override_tz:
        Optional client-supplied IANA zone (``?timezone=`` on the
        Today endpoint). Wins over ``user_tz`` when set.
    target_date:
        Optional explicit date, interpreted in the chosen zone. When
        ``None``, "today" is computed from ``datetime.now(zone).date()``.

    Returns
    -------
    TodayBounds
        ``start_utc``/``end_utc`` are timezone-aware UTC instants; the
        range is half-open. ``day_of_week`` is Mon=0 … Sun=6.

    Raises
    ------
    InvalidTimezoneError
        ``override_tz`` (or, as a fallback, ``user_tz``) is not a
        recognized IANA zone.
    """
    chosen_name = override_tz or user_tz
    zone = _resolve_zone(chosen_name)

    chosen_date = target_date or datetime.now(zone).date()

    start_local = datetime.combine(chosen_date, time(0, 0), tzinfo=zone)
    end_local = datetime.combine(
        chosen_date + timedelta(days=1), time(0, 0), tzinfo=zone
    )

    return TodayBounds(
        target_date=chosen_date,
        timezone_name=chosen_name,
        start_utc=start_local.astimezone(UTC),
        end_utc=end_local.astimezone(UTC),
        day_of_week=chosen_date.weekday(),
    )


__all__ = [
    "InvalidTimezoneError",
    "TodayBounds",
    "resolve_today_bounds",
]
