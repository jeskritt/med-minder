"""Schedule-related endpoints. Currently only ``GET /api/schedules/today``."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.api.schemas.today import TodayDose, TodayItem, TodayResponse
from medminder.db.models import User
from medminder.domain.doses import today_view
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

    items = [
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
        )
        for item in view.items
    ]
    return TodayResponse(date=view.date, timezone=view.timezone, items=items)
