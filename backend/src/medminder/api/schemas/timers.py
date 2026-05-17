"""Wire-format schemas for timer state (Phase 5).

Pydantic v2 models matching ``specs/005-timer-modes/contracts/timers.openapi.yaml``.
The domain ``TimerState`` lives in ``medminder.domain.timers``; the
adapter ``to_timer_state_out`` is the only crossing of that boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from medminder.domain import timers as domain_timers


class CountUpPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elapsed_seconds: int | None = Field(default=None, ge=0)


class CountDownPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_interval_seconds: int = Field(ge=1)
    next_allowed_at: datetime | None
    remaining_seconds: int = Field(ge=0)


class ActiveWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime
    doses_in_window: list[datetime]
    slots_used: int = Field(ge=0)
    slots_remaining: int = Field(ge=0)


class MultiSubDosePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_duration_seconds: int = Field(ge=1)
    slots_total: int = Field(ge=1)
    active_window: ActiveWindow | None
    previous_window_unused_slots: int = Field(ge=0)


class TimerStateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["count_up", "count_down", "multi_sub_dose"]
    as_of: datetime
    last_dose_at: datetime | None
    count_up: CountUpPayload | None = None
    count_down: CountDownPayload | None = None
    multi_sub_dose: MultiSubDosePayload | None = None


def to_timer_state_out(
    state: domain_timers.TimerState | None,
) -> TimerStateOut | None:
    """Convert a domain ``TimerState`` to its wire form.

    Returns ``None`` when ``state is None`` so callers can pass through
    a ``timer_preference == 'none'`` medication verbatim.
    """
    if state is None:
        return None
    return TimerStateOut(
        mode=state.mode,
        as_of=state.as_of,
        last_dose_at=state.last_dose_at,
        count_up=(
            CountUpPayload(elapsed_seconds=state.count_up.elapsed_seconds)
            if state.count_up is not None
            else None
        ),
        count_down=(
            CountDownPayload(
                min_interval_seconds=state.count_down.min_interval_seconds,
                next_allowed_at=state.count_down.next_allowed_at,
                remaining_seconds=state.count_down.remaining_seconds,
            )
            if state.count_down is not None
            else None
        ),
        multi_sub_dose=(
            MultiSubDosePayload(
                window_duration_seconds=state.multi_sub_dose.window_duration_seconds,
                slots_total=state.multi_sub_dose.slots_total,
                active_window=(
                    ActiveWindow(
                        window_start=state.multi_sub_dose.active_window.window_start,
                        window_end=state.multi_sub_dose.active_window.window_end,
                        doses_in_window=list(
                            state.multi_sub_dose.active_window.doses_in_window
                        ),
                        slots_used=state.multi_sub_dose.active_window.slots_used,
                        slots_remaining=(
                            state.multi_sub_dose.active_window.slots_remaining
                        ),
                    )
                    if state.multi_sub_dose.active_window is not None
                    else None
                ),
                previous_window_unused_slots=(
                    state.multi_sub_dose.previous_window_unused_slots
                ),
            )
            if state.multi_sub_dose is not None
            else None
        ),
    )


__all__ = [
    "ActiveWindow",
    "CountDownPayload",
    "CountUpPayload",
    "MultiSubDosePayload",
    "TimerStateOut",
    "to_timer_state_out",
]
