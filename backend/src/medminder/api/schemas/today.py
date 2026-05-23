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
    """One Today row. Scheduled rows key on ``(schedule_id, medication_id)``.

    UX enhancements: rows can also be **unscheduled timer meds** shown
    while their timer is running. Those carry ``schedule_id = None`` and
    ``scheduled_time = None`` (no slot); the frontend groups them under
    an "As needed" header, never mutes them, and never gates their take
    with the out-of-schedule confirm.
    """

    model_config = ConfigDict(extra="forbid")

    schedule_id: uuid.UUID | None
    medication_id: uuid.UUID
    name: str
    scheduled_time: time | None
    quantity_per_dose: Decimal
    unit: str
    dose: TodayDose | None
    timer_state: TimerStateOut | None = None
    interaction_state: InteractionStateOut | None = None
    # UX enhancements: dow filter dropped server-side; the frontend
    # uses these to mute non-scheduled rows visually and gate take.
    # Unscheduled (PRN) rows set days_of_week=0, scheduled_today=False.
    days_of_week: int
    scheduled_today: bool
    schedule_label: str


class TodayResponse(BaseModel):
    """Body of ``GET /api/schedules/today``."""

    model_config = ConfigDict(extra="forbid")

    date: date
    timezone: str
    items: list[TodayItem]
