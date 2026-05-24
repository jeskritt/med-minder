"""Pydantic schemas for the reminders router (Phase 7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReminderOut(BaseModel):
    """Public view of a reminder for the in-app list (FR-008)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    type: Literal["dose", "refill"]
    status: Literal["pending", "sent", "snoozed", "dismissed"]
    scheduled_for: datetime
    title: str
    schedule_id: uuid.UUID | None
    medication_id: uuid.UUID | None
    overdue: bool


class ReminderListOut(BaseModel):
    """Envelope for ``GET /api/v1/reminders``."""

    model_config = ConfigDict(extra="forbid")

    items: list[ReminderOut]


__all__ = ["ReminderListOut", "ReminderOut"]
