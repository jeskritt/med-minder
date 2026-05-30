"""Pydantic schemas for the ``/api/v1/adherence`` read endpoint.

The windowed read carries ``from``/``to`` as wire names; because ``from`` is a
Python keyword the field is declared as ``from_`` with ``alias="from"`` (and
``populate_by_name=True``) so the OpenAPI schema — and the generated TS client —
still use ``from``/``to`` (data-model.md / ADR-0016).
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from medminder.domain.adherence import (
    CourseProgress,
    DayStatus,
    MedicationAdherence,
)


class DayAdherenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    expected: int
    taken: int
    status: DayStatus


class CourseProgressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    taken: int
    complete: bool


class MedicationAdherenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    medication_id: uuid.UUID
    timezone: str
    from_: date = Field(alias="from")
    to: date
    days: list[DayAdherenceOut]
    adherence_pct: float | None
    course: CourseProgressOut | None


def _course_out(course: CourseProgress | None) -> CourseProgressOut | None:
    if course is None:
        return None
    return CourseProgressOut(
        total=course.total, taken=course.taken, complete=course.complete
    )


def to_medication_adherence_out(
    result: MedicationAdherence,
) -> MedicationAdherenceOut:
    """Map the domain result onto the wire schema."""
    return MedicationAdherenceOut(
        medication_id=result.medication_id,
        timezone=result.timezone,
        from_=result.from_date,
        to=result.to_date,
        days=[
            DayAdherenceOut(
                date=d.date, expected=d.expected, taken=d.taken, status=d.status
            )
            for d in result.days
        ],
        adherence_pct=result.adherence_pct,
        course=_course_out(result.course),
    )
