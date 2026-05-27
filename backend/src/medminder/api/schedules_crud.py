"""Schedules CRUD — shared user-level resources (UX enhancements).

Schedules used to be created inline with a medication (one Schedule
row per med + HH:MM). The UX-enhancements pass made them shared: one
Schedule can back many medications via ``ScheduleMedication``. This
router owns the Schedule lifecycle so the medication form can simply
attach existing ids.

Lives alongside the legacy ``api.schedules`` (which exposes
``GET /api/schedules/today``) — kept distinct so the today response
remains untouched.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.db.models import Medication, Schedule, ScheduleMedication, User
from medminder.domain.reminder_dispatch import regenerate_schedule_reminders

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


class ScheduleMedRef(BaseModel):
    """A medication currently attached to a schedule (for delete warnings)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str


class ScheduleCrudOut(BaseModel):
    """Public view of a user-level schedule."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    label: str
    time_of_day: time
    days_of_week: int
    medications: list[ScheduleMedRef] = Field(default_factory=list)


class ScheduleListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScheduleCrudOut]


class ScheduleWriteBody(BaseModel):
    """Inbound payload for ``POST`` / ``PUT`` ``/api/v1/schedules``."""

    model_config = ConfigDict(extra="forbid")

    time_of_day: time
    label: str = Field(default="", max_length=200)
    days_of_week: int = Field(default=127, ge=0, le=127)


# Back-compat alias: the create body is identical to the write body.
ScheduleCreateBody = ScheduleWriteBody


def _to_out(
    sched: Schedule, medications: list[ScheduleMedRef] | None = None
) -> ScheduleCrudOut:
    return ScheduleCrudOut(
        id=sched.id,
        label=sched.label,
        time_of_day=sched.time_of_day,
        days_of_week=sched.days_of_week,
        medications=medications or [],
    )


@router.get("", response_model=ScheduleListOut)
async def list_schedules(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ScheduleListOut:
    """Return every active schedule for the calling user, with attached meds."""
    rows = (
        await db.execute(
            select(Schedule)
            .where(
                Schedule.user_id == user.id,
                Schedule.deleted_at.is_(None),
            )
            .order_by(Schedule.time_of_day, Schedule.label)
        )
    ).scalars().all()

    # Attach the (own, non-deleted) medications linked to each schedule so
    # the delete-confirm modal can name what will be unscheduled.
    by_schedule: dict[uuid.UUID, list[ScheduleMedRef]] = {}
    if rows:
        link_rows = (
            await db.execute(
                select(
                    ScheduleMedication.schedule_id,
                    Medication.id,
                    Medication.name,
                )
                .join(
                    Medication,
                    Medication.id == ScheduleMedication.medication_id,
                )
                .where(
                    ScheduleMedication.schedule_id.in_([s.id for s in rows]),
                    Medication.user_id == user.id,
                    Medication.deleted_at.is_(None),
                )
                .order_by(Medication.name)
            )
        ).all()
        for schedule_id, med_id, med_name in link_rows:
            by_schedule.setdefault(schedule_id, []).append(
                ScheduleMedRef(id=med_id, name=med_name)
            )

    return ScheduleListOut(
        items=[_to_out(s, by_schedule.get(s.id, [])) for s in rows]
    )


@router.post(
    "",
    response_model=ScheduleCrudOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    body: ScheduleWriteBody,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ScheduleCrudOut:
    """Create a user-level schedule (no medication link yet)."""
    sched = Schedule(
        user_id=user.id,
        time_of_day=body.time_of_day,
        label=body.label,
        days_of_week=body.days_of_week,
    )
    db.add(sched)
    await db.flush()
    await db.refresh(sched)
    # FR-012: keep reminders in step (a fresh schedule has no meds yet → no-op).
    await regenerate_schedule_reminders(db, schedule_id=sched.id)
    return _to_out(sched)


@router.put("/{schedule_id}", response_model=ScheduleCrudOut)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleWriteBody,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ScheduleCrudOut:
    """Update a user-level schedule's time, label, and day-of-week mask.

    Edits propagate to every medication attached to the schedule (that is
    the point of shared schedules). Attached links are untouched.
    """
    sched = (
        await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    ).scalar_one_or_none()
    if (
        sched is None
        or sched.user_id != user.id
        or sched.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    sched.time_of_day = body.time_of_day
    sched.label = body.label
    sched.days_of_week = body.days_of_week
    await db.flush()
    await db.refresh(sched)
    # FR-012: regenerate this schedule's future dose reminders at the new
    # time/days (stale ones for the old time are cancelled).
    await regenerate_schedule_reminders(db, schedule_id=sched.id)

    med_refs = [
        ScheduleMedRef(id=med_id, name=med_name)
        for med_id, med_name in (
            await db.execute(
                select(Medication.id, Medication.name)
                .join(
                    ScheduleMedication,
                    ScheduleMedication.medication_id == Medication.id,
                )
                .where(
                    ScheduleMedication.schedule_id == sched.id,
                    Medication.user_id == user.id,
                    Medication.deleted_at.is_(None),
                )
                .order_by(Medication.name)
            )
        ).all()
    ]
    return _to_out(sched, med_refs)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Detach any linked medications then soft-delete the schedule.

    Detach-then-soft-delete matches the plan's "cascade-detach via
    ScheduleMedication" decision: the user can drop a slot without
    cascading into medication soft-deletes.
    """
    sched = (
        await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    ).scalar_one_or_none()
    if (
        sched is None
        or sched.user_id != user.id
        or sched.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    await db.execute(
        delete(ScheduleMedication).where(
            ScheduleMedication.schedule_id == schedule_id
        )
    )
    sched.deleted_at = datetime.now(UTC)
    await db.flush()
    # FR-012: the schedule is now soft-deleted, so this cancels its future
    # pending dose reminders.
    await regenerate_schedule_reminders(db, schedule_id=schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = [
    "ScheduleCreateBody",
    "ScheduleCrudOut",
    "ScheduleListOut",
    "ScheduleMedRef",
    "ScheduleWriteBody",
    "router",
]
