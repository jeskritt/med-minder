"""Wire-format error bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MinIntervalViolation(BaseModel):
    """HTTP 409 body when a count_down med's interval has not elapsed."""

    model_config = ConfigDict(extra="forbid")

    code: Literal["min_interval_not_elapsed"]
    medication_id: uuid.UUID
    next_allowed_at: datetime
    remaining_seconds: int = Field(ge=1)


class WindowFullViolation(BaseModel):
    """HTTP 409 body when a multi_sub_dose med has the max doses active.

    Rolling model: ``slots_total`` is the max-concurrent cap and
    ``next_available_at`` is when the oldest active dose's window expires
    (a slot frees then).
    """

    model_config = ConfigDict(extra="forbid")

    code: Literal["window_full"]
    medication_id: uuid.UUID
    next_available_at: datetime
    slots_used: int = Field(ge=1)
    slots_total: int = Field(ge=1)


class DailyCapViolation(BaseModel):
    """HTTP 409 body when a multi_sub_dose med's per-day cap is reached.

    Sibling of `WindowFullViolation`: per-window slots are enforced
    separately; this fires when the additional `max_doses_per_day`
    threshold has been reached for today's UTC bounds.
    """

    model_config = ConfigDict(extra="forbid")

    code: Literal["daily_cap_reached"]
    medication_id: uuid.UUID
    max_per_day: int = Field(ge=1)
    count_today: int = Field(ge=1)


class ConflictOut(BaseModel):
    """One active drug-interaction conflict (Phase 6)."""

    model_config = ConfigDict(extra="forbid")

    conflicting_medication_id: uuid.UUID
    conflicting_medication_name: str
    cooldown_elapses_at: datetime
    remaining_seconds: int = Field(ge=0)


class InteractionCooldownViolation(BaseModel):
    """HTTP 409 body for an unacknowledged active interaction cooldown.

    ``code`` is distinct from the Phase 5 overdose codes; this conflict
    is *always overridable* by retrying with
    ``interaction_acknowledged: true`` (ADR-0008).
    """

    model_config = ConfigDict(extra="forbid")

    code: Literal["interaction_cooldown_active"]
    medication_id: uuid.UUID
    conflicts: list[ConflictOut] = Field(min_length=1)
    cooldown_elapses_at: datetime
    remaining_seconds: int = Field(ge=0)


__all__ = [
    "ConflictOut",
    "DailyCapViolation",
    "InteractionCooldownViolation",
    "MinIntervalViolation",
    "WindowFullViolation",
]
