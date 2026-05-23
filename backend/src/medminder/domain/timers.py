"""Timer-state domain logic for Phase 5 modes.

Pure Python: no sqlalchemy, no fastapi imports at runtime. The
conversion to wire-format Pydantic models lives in
``medminder.api.schemas.timers``; the per-mode math is filled in
per-user-story (T019, T034, T048).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from medminder.db.models import Dose, Medication


TimerMode = Literal["count_up", "count_down", "multi_sub_dose"]

# UX enhancements: an unscheduled count_up med has no intrinsic expiry,
# so for the "show on /today while the timer is running" rule we treat
# its timer as active only within 24h of the last dose — matching the
# frontend's existing "over 24h ago" display cap (`lib/timers.ts`).
COUNT_UP_ACTIVE_HORIZON_SECONDS = 86_400


@dataclass(frozen=True)
class CountUpPayload:
    elapsed_seconds: int | None


@dataclass(frozen=True)
class CountDownPayload:
    min_interval_seconds: int
    next_allowed_at: datetime | None
    remaining_seconds: int


@dataclass(frozen=True)
class ActiveSubDose:
    """A non-voided dose still inside its own rolling window."""

    taken_at: datetime
    expires_at: datetime  # taken_at + window_duration


@dataclass(frozen=True)
class MultiSubDosePayload:
    """Rolling per-dose window state.

    Each dose opens its own ``window_duration`` window; at most
    ``max_concurrent`` of them may overlap ("max N at a time"). A dose
    is "active" while ``now`` is inside its window.
    """

    window_duration_seconds: int
    max_concurrent: int
    active_sub_doses: list[ActiveSubDose]  # oldest-first
    slots_used: int
    slots_remaining: int
    next_available_at: datetime | None  # earliest expiry when full, else None


@dataclass(frozen=True)
class TimerState:
    mode: TimerMode
    as_of: datetime
    last_dose_at: datetime | None
    count_up: CountUpPayload | None = None
    count_down: CountDownPayload | None = None
    multi_sub_dose: MultiSubDosePayload | None = None


class MinIntervalNotElapsedError(Exception):
    """Raised when a count_down med's minimum interval has not elapsed."""

    def __init__(
        self,
        *,
        medication_id: uuid.UUID,
        next_allowed_at: datetime,
        remaining_seconds: int,
    ) -> None:
        super().__init__(
            f"Min interval not elapsed for medication {medication_id}; "
            f"{remaining_seconds}s remaining."
        )
        self.medication_id = medication_id
        self.next_allowed_at = next_allowed_at
        self.remaining_seconds = remaining_seconds


class WindowFullError(Exception):
    """Raised when a multi_sub_dose med already has the max doses active.

    ``slots_total`` is the max-concurrent cap (N); ``slots_used`` is how
    many doses are currently active; ``next_available_at`` is when the
    oldest active dose's window expires and a slot frees.
    """

    def __init__(
        self,
        *,
        medication_id: uuid.UUID,
        next_available_at: datetime,
        slots_used: int,
        slots_total: int,
    ) -> None:
        super().__init__(
            f"multi_sub_dose at capacity for medication {medication_id}: "
            f"{slots_used}/{slots_total}."
        )
        self.medication_id = medication_id
        self.next_available_at = next_available_at
        self.slots_used = slots_used
        self.slots_total = slots_total


class DailyCapReachedError(Exception):
    """Raised when a multi_sub_dose med's per-day cap is reached.

    Sibling to :class:`WindowFullError`; the per-window cap is enforced
    separately. Per ADR-0008 this remains a non-overridable overdose
    guard (no `acknowledged` bypass).
    """

    def __init__(
        self,
        *,
        medication_id: uuid.UUID,
        max_per_day: int,
        count_today: int,
    ) -> None:
        super().__init__(
            f"multi_sub_dose daily cap reached for medication {medication_id}: "
            f"{count_today}/{max_per_day}."
        )
        self.medication_id = medication_id
        self.max_per_day = max_per_day
        self.count_today = count_today


def _active_at(
    taken_ats: list[datetime],
    at: datetime,
    window_duration: timedelta,
) -> list[datetime]:
    """Doses whose own rolling window covers ``at`` — i.e. taken in
    ``(at - window_duration, at]``. Returned sorted oldest-first.

    Single source of truth for the multi_sub_dose rolling model, shared
    by ``compute_timer_state`` and the ``create_dose`` overdose guard.
    """
    lower = at - window_duration
    return sorted(t for t in taken_ats if lower < t <= at)


def multi_sub_dose_window_full(
    med: Medication,
    non_voided_taken_ats: list[datetime],
    prospective_taken_at: datetime,
) -> WindowFullError | None:
    """Return a ``WindowFullError`` iff taking a dose at
    ``prospective_taken_at`` would exceed the max-concurrent cap.

    Rolling-window model: each dose is "active" for ``window_duration``;
    at most ``times_per_day`` (= max concurrent) may overlap. Blocked
    when ``window_duration`` already holds that many. Order-independent.
    """
    if med.window_duration_minutes is None or med.window_duration_minutes <= 0:
        return None
    window_duration = timedelta(minutes=med.window_duration_minutes)
    slots_total = med.times_per_day
    active = _active_at(
        non_voided_taken_ats, prospective_taken_at, window_duration
    )
    if len(active) >= slots_total:
        # The oldest active dose ages out first → frees the next slot.
        return WindowFullError(
            medication_id=med.id,
            next_available_at=active[0] + window_duration,
            slots_used=len(active),
            slots_total=slots_total,
        )
    return None


def compute_timer_state(
    med: Medication,
    doses: list[Dose],
    now: datetime,
) -> TimerState | None:
    """Compute the timer state for ``med`` given its dose history.

    ``doses`` MUST already exclude voided doses; callers filter at the
    SQL layer. Returns ``None`` when ``med.timer_preference == "none"``
    (the API surfaces this as ``timer_state: null``).
    """
    pref = med.timer_preference
    if pref == "none":
        return None
    if pref == "count_up":
        last = doses[0] if doses else None
        last_dose_at = last.taken_at if last is not None else None
        elapsed = (
            int((now - last_dose_at).total_seconds())
            if last_dose_at is not None
            else None
        )
        return TimerState(
            mode="count_up",
            as_of=now,
            last_dose_at=last_dose_at,
            count_up=CountUpPayload(elapsed_seconds=elapsed),
        )
    if pref == "count_down":
        if med.min_interval_minutes is None or med.min_interval_minutes <= 0:
            raise ValueError(
                "count_down timer_preference requires min_interval_minutes > 0"
            )
        min_interval_seconds = med.min_interval_minutes * 60
        last = doses[0] if doses else None
        last_dose_at = last.taken_at if last is not None else None
        if last_dose_at is None:
            return TimerState(
                mode="count_down",
                as_of=now,
                last_dose_at=None,
                count_down=CountDownPayload(
                    min_interval_seconds=min_interval_seconds,
                    next_allowed_at=None,
                    remaining_seconds=0,
                ),
            )
        next_allowed_at = last_dose_at + timedelta(
            minutes=med.min_interval_minutes
        )
        remaining = max(0, int((next_allowed_at - now).total_seconds()))
        return TimerState(
            mode="count_down",
            as_of=now,
            last_dose_at=last_dose_at,
            count_down=CountDownPayload(
                min_interval_seconds=min_interval_seconds,
                next_allowed_at=next_allowed_at,
                remaining_seconds=remaining,
            ),
        )
    if pref == "multi_sub_dose":
        if med.times_per_day < 1:
            # Misconfigured/legacy row (slots_total would be 0, which the
            # wire model rejects). Degrade to no timer state rather than
            # 500 the whole list/today; creation/update is blocked by
            # validate_medication_input. The medication still lists so
            # the user can fix or delete it.
            return None
        if (
            med.window_duration_minutes is None
            or med.window_duration_minutes <= 0
        ):
            raise ValueError(
                "multi_sub_dose timer_preference requires "
                "window_duration_minutes > 0"
            )
        window_duration = timedelta(minutes=med.window_duration_minutes)
        window_duration_seconds = med.window_duration_minutes * 60
        max_concurrent = med.times_per_day

        newest = doses[0] if doses else None
        last_dose_at = newest.taken_at if newest is not None else None

        # Rolling model: a dose is "active" while now is inside its own
        # window. At most `max_concurrent` may overlap; the oldest active
        # dose frees the next slot when its window expires.
        active = _active_at([d.taken_at for d in doses], now, window_duration)
        active_sub_doses = [
            ActiveSubDose(taken_at=t, expires_at=t + window_duration)
            for t in active
        ]
        slots_used = len(active_sub_doses)
        slots_remaining = max(0, max_concurrent - slots_used)
        next_available_at = (
            active_sub_doses[0].expires_at
            if slots_used >= max_concurrent and active_sub_doses
            else None
        )
        return TimerState(
            mode="multi_sub_dose",
            as_of=now,
            last_dose_at=last_dose_at,
            multi_sub_dose=MultiSubDosePayload(
                window_duration_seconds=window_duration_seconds,
                max_concurrent=max_concurrent,
                active_sub_doses=active_sub_doses,
                slots_used=slots_used,
                slots_remaining=slots_remaining,
                next_available_at=next_available_at,
            ),
        )
    raise ValueError(f"Unknown timer_preference: {pref!r}")


def is_timer_active(state: TimerState | None) -> bool:
    """Whether ``state`` represents a *running* (not-yet-expired) timer.

    Single source of truth for the UX-enhancement rule "show an
    unscheduled timer med on /today only while its timer is running":

    - ``count_down``: counting down toward the next allowed dose.
    - ``multi_sub_dose``: at least one dose is still inside its own
      rolling window (``slots_used > 0``); drops off once every
      per-dose window has expired.
    - ``count_up``: a dose exists and it was within the 24h horizon
      (count_up has no natural expiry; see
      :data:`COUNT_UP_ACTIVE_HORIZON_SECONDS`).
    """
    if state is None:
        return False
    if state.mode == "count_down":
        return (
            state.count_down is not None
            and state.count_down.remaining_seconds > 0
        )
    if state.mode == "multi_sub_dose":
        return (
            state.multi_sub_dose is not None
            and state.multi_sub_dose.slots_used > 0
        )
    if state.mode == "count_up":
        return (
            state.count_up is not None
            and state.count_up.elapsed_seconds is not None
            and state.count_up.elapsed_seconds <= COUNT_UP_ACTIVE_HORIZON_SECONDS
        )
    return False


__all__ = [
    "COUNT_UP_ACTIVE_HORIZON_SECONDS",
    "ActiveSubDose",
    "CountDownPayload",
    "CountUpPayload",
    "DailyCapReachedError",
    "MinIntervalNotElapsedError",
    "MultiSubDosePayload",
    "TimerMode",
    "TimerState",
    "WindowFullError",
    "compute_timer_state",
    "is_timer_active",
    "multi_sub_dose_window_full",
]
