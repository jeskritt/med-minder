"""Pydantic schemas for the medications router."""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from medminder.api.schemas.timers import TimerStateOut


class ScheduleOut(BaseModel):
    """Public view of a Schedule attached to a medication."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    time_of_day: time


class MedicationBody(BaseModel):
    """Inbound payload shared by ``POST`` and ``PUT``."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    quantity_per_dose: Decimal = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)
    times_per_day: int = Field(..., ge=0, le=24)
    start_date: date | None = None
    end_date: date | None = None
    total_doses: int | None = Field(default=None, gt=0)
    schedules: list[time] = Field(default_factory=list)
    refill_count: int | None = Field(default=None, ge=0)
    refill_threshold: int | None = Field(default=None, ge=0)
    timer_preference: Literal[
        "none", "count_up", "count_down", "multi_sub_dose"
    ] = "none"
    min_interval_minutes: int | None = Field(default=None, gt=0)
    window_duration_minutes: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_dates(self) -> MedicationBody:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class MedicationOut(BaseModel):
    """Public view of a Medication plus its schedules."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    quantity_per_dose: Decimal
    unit: str
    times_per_day: int
    start_date: date | None
    end_date: date | None
    total_doses: int | None
    refill_count: int | None
    refill_threshold: int | None
    schedules: list[ScheduleOut]
    timer_preference: Literal["none", "count_up", "count_down", "multi_sub_dose"]
    min_interval_minutes: int | None = None
    window_duration_minutes: int | None = None
    timer_state: TimerStateOut | None = None


class MedicationListOut(BaseModel):
    """Envelope for ``GET /api/v1/medications``."""

    model_config = ConfigDict(extra="forbid")

    items: list[MedicationOut]


__all__ = [
    "MedicationBody",
    "MedicationListOut",
    "MedicationOut",
    "ScheduleOut",
]
