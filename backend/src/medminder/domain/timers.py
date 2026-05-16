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


@dataclass(frozen=True)
class CountUpPayload:
    elapsed_seconds: int | None


@dataclass(frozen=True)
class CountDownPayload:
    min_interval_seconds: int
    next_allowed_at: datetime | None
    remaining_seconds: int


@dataclass(frozen=True)
class ActiveWindow:
    window_start: datetime
    window_end: datetime
    doses_in_window: list[datetime]
    slots_used: int
    slots_remaining: int


@dataclass(frozen=True)
class MultiSubDosePayload:
    window_duration_seconds: int
    slots_total: int
    active_window: ActiveWindow | None
    previous_window_unused_slots: int


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
        slots_total = med.times_per_day

        newest = doses[0] if doses else None
        last_dose_at = newest.taken_at if newest is not None else None

        if not doses:
            return TimerState(
                mode="multi_sub_dose",
                as_of=now,
                last_dose_at=None,
                multi_sub_dose=MultiSubDosePayload(
                    window_duration_seconds=window_duration_seconds,
                    slots_total=slots_total,
                    active_window=None,
                    previous_window_unused_slots=0,
                ),
            )

        # Walk oldest-first, grouping doses into non-overlapping windows.
        # A dose extends the current window if it falls before that
        # window's end; otherwise it opens a new window.
        windows: list[tuple[datetime, list[datetime]]] = []
        for dose in reversed(doses):
            taken = dose.taken_at
            if windows:
                start, members = windows[-1]
                if taken < start + window_duration:
                    members.append(taken)
                    continue
            windows.append((taken, [taken]))

        start, members = windows[-1]
        end = start + window_duration

        if start <= now < end:
            slots_used = len(members)
            return TimerState(
                mode="multi_sub_dose",
                as_of=now,
                last_dose_at=last_dose_at,
                multi_sub_dose=MultiSubDosePayload(
                    window_duration_seconds=window_duration_seconds,
                    slots_total=slots_total,
                    active_window=ActiveWindow(
                        window_start=start,
                        window_end=end,
                        doses_in_window=list(members),
                        slots_used=slots_used,
                        slots_remaining=max(0, slots_total - slots_used),
                    ),
                    previous_window_unused_slots=0,
                ),
            )

        # Latest window has expired (no new window started since, by
        # construction). Surface its unused-slot count for the banner.
        unused = max(0, slots_total - len(members))
        return TimerState(
            mode="multi_sub_dose",
            as_of=now,
            last_dose_at=last_dose_at,
            multi_sub_dose=MultiSubDosePayload(
                window_duration_seconds=window_duration_seconds,
                slots_total=slots_total,
                active_window=None,
                previous_window_unused_slots=unused,
            ),
        )
    raise ValueError(f"Unknown timer_preference: {pref!r}")


__all__ = [
    "ActiveWindow",
    "CountDownPayload",
    "CountUpPayload",
    "MinIntervalNotElapsedError",
    "MultiSubDosePayload",
    "TimerMode",
    "TimerState",
    "compute_timer_state",
]
