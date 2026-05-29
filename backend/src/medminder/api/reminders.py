"""Reminders router (Phase 7) — the in-app reminder list (FR-008).

A user without push still sees what is due here. Scoped to the logged-in
user; dismissed reminders are excluded.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session, get_settings
from medminder.api.schemas.reminders import ReminderListOut, ReminderOut
from medminder.db.models import Reminder, User
from medminder.domain.doses import ReminderNotTakeableError, take_reminder
from medminder.domain.reminder_dispatch import (
    ReminderNotFoundError,
    dismiss_reminder,
    load_reminder_titles,
    snooze_reminder,
)
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


@router.post("/{reminder_id}/snooze", response_model=ReminderOut)
async def snooze(
    reminder_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ReminderOut:
    """Snooze a reminder one hour; returns the reminder that will next fire."""
    try:
        rem = await snooze_reminder(
            db, user=user, reminder_id=reminder_id, now=datetime.now(UTC)
        )
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        ) from exc
    titles = await load_reminder_titles(db, [rem])
    return ReminderOut(
        id=rem.id,
        type=rem.type,
        status=rem.status,
        scheduled_for=rem.scheduled_for,
        title=titles.get(rem.id, "MedMinder reminder"),
        schedule_id=rem.schedule_id,
        medication_id=rem.medication_id,
        overdue=False,
    )


@router.post("/{reminder_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss(
    reminder_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Dismiss (resolve) a reminder. Idempotent; 404 if not the caller's."""
    try:
        await dismiss_reminder(db, user=user, reminder_id=reminder_id)
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{reminder_id}/take", status_code=status.HTTP_204_NO_CONTENT)
async def take(
    reminder_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Mark a dose reminder's slot as taken: record a dose per attached med.

    Powers the notification "Mark taken" action (Phase 8). Atomic — any
    overdose/interaction guard raised by ``create_dose`` propagates to the
    app-wide handlers as a 409 with nothing committed (FR-015). 404 if the
    reminder isn't the caller's; 422 for a non-dose reminder. Idempotent (204)
    when the slot has no meds or is already resolved.
    """
    try:
        await take_reminder(
            db, user=user, reminder_id=reminder_id, now=datetime.now(UTC)
        )
    except ReminderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        ) from exc
    except ReminderNotTakeableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
