"""Pure scheduling math for Phase 7 reminders.

Constitution Principle III: this module holds the time arithmetic that the
reminder engine needs and imports **no** SQLAlchemy / FastAPI / APScheduler —
so the DST / midnight-wrap / grace edge cases live in one exhaustively
unit-testable place (mirrors ``domain/timezone.py`` and ``domain/timers.py``).

The async DB orchestration that *uses* these functions lives in
``domain/reminder_dispatch.py``.

Conventions:
- ``days_of_week`` is the same Mon=0 … Sun=6 bitmask as ``schedules.days_of_week``
  (bit ``1 << weekday`` set ⇒ active that weekday), matching ``today_view``.
- All returned instants are timezone-aware UTC.
- Quiet-hours windows are ``[start, end)`` — exclusive at the end, so a
  reminder exactly at ``end`` fires — and may wrap midnight (``start > end``).
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

__all__ = [
    "crosses_refill_threshold",
    "defer_for_quiet_hours",
    "is_within_grace",
    "next_dose_fire_times_utc",
]


def next_dose_fire_times_utc(
    *,
    time_of_day: time,
    days_of_week: int,
    tz: str,
    now: datetime,
    horizon: timedelta,
) -> list[datetime]:
    """UTC fire instants for a schedule slot within ``[now, now + horizon)``.

    For each local date in the user's zone whose weekday bit is set in
    ``days_of_week``, combine the date with ``time_of_day`` (local), convert
    to UTC, and keep it if it lands in the half-open window. Returned
    ascending. ``now`` must be timezone-aware.
    """
    zone = ZoneInfo(tz)
    end = now + horizon
    start_date = now.astimezone(zone).date()
    end_date = end.astimezone(zone).date()

    out: list[datetime] = []
    current = start_date
    while current <= end_date:
        if days_of_week & (1 << current.weekday()):
            local_dt = datetime.combine(current, time_of_day, tzinfo=zone)
            fire_utc = local_dt.astimezone(UTC)
            if now <= fire_utc < end:
                out.append(fire_utc)
        current += timedelta(days=1)
    return sorted(out)


def is_within_grace(
    *, scheduled_for: datetime, now: datetime, grace: timedelta
) -> bool:
    """True iff the reminder is due and not older than the grace window.

    Due but older than ``grace`` → ``False`` (the caller leaves it ``pending``
    as overdue, never pushed — FR-006a).
    """
    return scheduled_for <= now <= scheduled_for + grace


def defer_for_quiet_hours(
    *,
    fire_utc: datetime,
    tz: str,
    quiet_start: time | None,
    quiet_end: time | None,
) -> datetime | None:
    """Return the deferred UTC instant if ``fire_utc`` falls in quiet hours.

    Quiet hours are the user-local window ``[quiet_start, quiet_end)``; when
    ``quiet_start > quiet_end`` the window wraps midnight (e.g. 22:00 → 07:00).
    Returns the UTC instant of the window **end** (the next ``quiet_end`` at or
    after the fire time) when inside the window, else ``None`` (deliver now).
    A fire exactly at ``quiet_end`` is *not* inside (boundary exclusive).
    Both bounds must be set for quiet hours to apply.
    """
    if quiet_start is None or quiet_end is None:
        return None

    zone = ZoneInfo(tz)
    local = fire_utc.astimezone(zone)
    t = local.time()

    if quiet_start <= quiet_end:
        # Same-day window, e.g. 13:00 → 14:00.
        inside = quiet_start <= t < quiet_end
        end_date = local.date()
    else:
        # Wraps midnight, e.g. 22:00 → 07:00.
        inside = t >= quiet_start or t < quiet_end
        # The window's end is "tomorrow" only when we're in the late-evening
        # part (t >= quiet_start); in the early-morning part it's today.
        end_date = local.date() + timedelta(days=1) if t >= quiet_start else local.date()

    if not inside:
        return None

    end_local = datetime.combine(end_date, quiet_end, tzinfo=zone)
    return end_local.astimezone(UTC)


def crosses_refill_threshold(
    *, before: int | None, after: int, threshold: int | None
) -> bool:
    """True iff a take just brought supply down to/below the warn level.

    Fires only on the *downward* crossing (``before > threshold >= after``)
    so repeated takes while already at/below threshold don't re-warn, and
    only when a ``threshold`` is set (refill warnings are opt-in). ``before``
    ``None`` means supply was untracked → no crossing.
    """
    if threshold is None or before is None:
        return False
    return before > threshold and after <= threshold
