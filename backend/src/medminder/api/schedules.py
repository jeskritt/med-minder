"""Schedule-related endpoints. Currently only ``GET /api/schedules/today``."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.api.schemas.interactions import to_interaction_state_out
from medminder.api.schemas.timers import to_timer_state_out
from medminder.api.schemas.today import TodayDose, TodayItem, TodayResponse
from medminder.db.models import Medication, User
from medminder.domain.doses import (
    load_active_interaction_state,
    load_non_voided_history_for_meds,
    today_view,
)
from medminder.domain.timers import compute_timer_state
from medminder.domain.timezone import InvalidTimezoneError

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("/today", response_model=TodayResponse)
async def get_today(
    timezone: str | None = Query(default=None),
    target_date: date | None = Query(default=None, alias="date"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> TodayResponse:
    """List the user's scheduled slots for "today" plus any effective dose."""
    try:
        view = await today_view(
            db,
            user=user,
            timezone_override=timezone,
            target_date=target_date,
        )
    except InvalidTimezoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown IANA timezone: {exc}",
        ) from exc

    med_ids = list({item.medication_id for item in view.items})
    meds_by_id: dict[uuid.UUID, Medication] = {}
    if med_ids:
        rows = (
            await db.execute(
                select(Medication).where(
                    Medication.id.in_(med_ids),
                    Medication.user_id == user.id,
                    Medication.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        meds_by_id = {m.id: m for m in rows}
    history = await load_non_voided_history_for_meds(
        db, user_id=user.id, medication_ids=med_ids
    )
    now = datetime.now(UTC)
    conflicts = await load_active_interaction_state(
        db, user_id=user.id, medication_ids=med_ids, now=now
    )

    items: list[TodayItem] = []
    for item in view.items:
        med = meds_by_id.get(item.medication_id)
        state = (
            compute_timer_state(med, history.get(item.medication_id, []), now=now)
            if med is not None
            else None
        )
        items.append(
            TodayItem(
                schedule_id=item.schedule_id,
                medication_id=item.medication_id,
                name=item.name,
                scheduled_time=item.scheduled_time,
                quantity_per_dose=item.quantity_per_dose,
                unit=item.unit,
                dose=(
                    TodayDose(id=item.dose.id, taken_at=item.dose.taken_at)
                    if item.dose is not None
                    else None
                ),
                timer_state=to_timer_state_out(state),
                interaction_state=to_interaction_state_out(
                    conflicts.get(item.medication_id)
                ),
            )
        )
    return TodayResponse(date=view.date, timezone=view.timezone, items=items)
