"""Reminders router (Phase 7) — the in-app reminder list (FR-008).

A user without push still sees what is due here. Scoped to the logged-in
user; dismissed reminders are excluded.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session, get_settings
from medminder.api.schemas.reminders import ReminderListOut, ReminderOut
from medminder.db.models import Reminder, User
from medminder.domain.reminder_dispatch import load_reminder_titles
from medminder.domain.reminders import is_within_grace
from medminder.settings import Settings

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


@router.get("", response_model=ReminderListOut)
async def list_reminders(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ReminderListOut:
    """List the caller's open (non-dismissed) reminders, oldest first."""
    rows = list(
        (
            await db.execute(
                select(Reminder)
                .where(
                    Reminder.user_id == user.id,
                    Reminder.status != "dismissed",
                )
                .order_by(Reminder.scheduled_for)
            )
        )
        .scalars()
        .all()
    )
    titles = await load_reminder_titles(db, rows)
    now = datetime.now(UTC)
    grace = timedelta(minutes=settings.reminder_grace_minutes)
    items = [
        ReminderOut(
            id=r.id,
            type=r.type,
            status=r.status,
            scheduled_for=r.scheduled_for,
            title=titles.get(r.id, "MedMinder reminder"),
            schedule_id=r.schedule_id,
            medication_id=r.medication_id,
            overdue=(
                r.status == "pending"
                and r.scheduled_for <= now
                and not is_within_grace(
                    scheduled_for=r.scheduled_for, now=now, grace=grace
                )
            ),
        )
        for r in rows
    ]
    return ReminderListOut(items=items)


__all__ = ["router"]
