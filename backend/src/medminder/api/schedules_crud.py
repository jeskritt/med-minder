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
from medminder.db.models import Schedule, ScheduleMedication, User

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


class ScheduleCrudOut(BaseModel):
    """Public view of a user-level schedule."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    label: str
    time_of_day: time
    days_of_week: int


class ScheduleListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScheduleCrudOut]


class ScheduleCreateBody(BaseModel):
    """Inbound payload for ``POST /api/v1/schedules``."""

    model_config = ConfigDict(extra="forbid")

    time_of_day: time
    label: str = Field(default="", max_length=200)
    days_of_week: int = Field(default=127, ge=0, le=127)


def _to_out(sched: Schedule) -> ScheduleCrudOut:
    return ScheduleCrudOut(
        id=sched.id,
        label=sched.label,
        time_of_day=sched.time_of_day,
        days_of_week=sched.days_of_week,
    )


@router.get("", response_model=ScheduleListOut)
async def list_schedules(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ScheduleListOut:
    """Return every active schedule for the calling user."""
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
    return ScheduleListOut(items=[_to_out(s) for s in rows])


@router.post(
    "",
    response_model=ScheduleCrudOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    body: ScheduleCreateBody,
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
    return _to_out(sched)


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
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = [
    "ScheduleCreateBody",
    "ScheduleCrudOut",
    "ScheduleListOut",
    "router",
]
