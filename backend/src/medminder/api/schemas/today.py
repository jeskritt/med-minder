"""Pydantic schemas for ``GET /api/schedules/today``."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from medminder.api.schemas.interactions import InteractionStateOut
from medminder.api.schemas.timers import TimerStateOut


class TodayDose(BaseModel):
    """The minimal slice of a dose surfaced under a Today item."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    taken_at: datetime


class TodayItem(BaseModel):
    """One scheduled slot. The UI keys rows on ``(schedule_id, medication_id)``."""

    model_config = ConfigDict(extra="forbid")

    schedule_id: uuid.UUID
    medication_id: uuid.UUID
    name: str
    scheduled_time: time
    quantity_per_dose: Decimal
    unit: str
    dose: TodayDose | None
    timer_state: TimerStateOut | None = None
    interaction_state: InteractionStateOut | None = None
    # UX enhancements: dow filter dropped server-side; the frontend
    # uses these to mute non-scheduled rows visually and gate take.
    days_of_week: int
    scheduled_today: bool
    schedule_label: str


class TodayResponse(BaseModel):
    """Body of ``GET /api/schedules/today``."""

    model_config = ConfigDict(extra="forbid")

    date: date
    timezone: str
    items: list[TodayItem]
