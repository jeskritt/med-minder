"""Timer-state domain logic for Phase 5 modes.

Pure Python: no sqlalchemy, no fastapi imports at runtime. The
conversion to wire-format Pydantic models lives in
``medminder.api.schemas.timers``; the per-mode math is filled in
per-user-story (T019, T034, T048).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
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
        raise NotImplementedError("count_up branch — see T019 (US1).")
    if pref == "count_down":
        raise NotImplementedError("count_down branch — see T034 (US2).")
    if pref == "multi_sub_dose":
        raise NotImplementedError("multi_sub_dose branch — see T048 (US3).")
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
