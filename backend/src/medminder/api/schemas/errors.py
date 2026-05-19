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
    """HTTP 409 body when a multi_sub_dose med's active window is full."""

    model_config = ConfigDict(extra="forbid")

    code: Literal["window_full"]
    medication_id: uuid.UUID
    window_end: datetime
    slots_used: int = Field(ge=1)
    slots_total: int = Field(ge=1)


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
    "InteractionCooldownViolation",
    "MinIntervalViolation",
    "WindowFullViolation",
]
