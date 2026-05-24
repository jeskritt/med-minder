"""Async DB orchestration for Phase 7 reminders (FR-004/005/006/007).

The pure scheduling math lives in ``domain/reminders.py``; this module does
the DB I/O: materialising dose reminders for upcoming schedule slots and
dispatching due ones. Delivery goes through an injected ``send`` callable so
the dispatcher is testable with a fake sender and no network (Principle III).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import (
    Medication,
    PushSubscription,
    Reminder,
    Schedule,
    ScheduleMedication,
    User,
)
from medminder.domain.push import PushResult
from medminder.domain.reminders import is_within_grace, next_dose_fire_times_utc

GENERATION_HORIZON: timedelta = timedelta(hours=48)
"""How far ahead dose reminders are materialised (plan research D3)."""

PushSender = Callable[[PushSubscription, dict[str, Any]], Awaitable[PushResult]]


async def generate_due_dose_reminders(
    session: AsyncSession,
    *,
    now: datetime,
    horizon: timedelta = GENERATION_HORIZON,
) -> int:
    """Idempotently create ``pending`` dose reminders for upcoming slots.

    For every non-deleted schedule (owner live) with at least one non-deleted
    attached medication, materialise a reminder per fire instant in
    ``[now, now + horizon)`` that does not already have a non-``dismissed``
    row at ``(schedule_id, scheduled_for)``. Returns the count created.
    """
    has_live_med = (
        select(ScheduleMedication.schedule_id)
        .join(Medication, Medication.id == ScheduleMedication.medication_id)
        .where(
            ScheduleMedication.schedule_id == Schedule.id,
            Medication.deleted_at.is_(None),
        )
        .exists()
    )
    rows = (
        await session.execute(
            select(Schedule, User.timezone)
            .join(User, User.id == Schedule.user_id)
            .where(
                Schedule.deleted_at.is_(None),
                User.deleted_at.is_(None),
                has_live_med,
            )
        )
    ).all()

    created = 0
    for sched, tz in rows:
        for fire in next_dose_fire_times_utc(
            time_of_day=sched.time_of_day,
            days_of_week=sched.days_of_week,
            tz=tz,
            now=now,
            horizon=horizon,
        ):
            already = (
                await session.execute(
                    select(Reminder.id).where(
                        Reminder.type == "dose",
                        Reminder.schedule_id == sched.id,
                        Reminder.scheduled_for == fire,
                        Reminder.status != "dismissed",
                    )
                )
            ).first()
            if already is None:
                session.add(
                    Reminder(
                        user_id=sched.user_id,
                        type="dose",
                        schedule_id=sched.id,
                        scheduled_for=fire,
                        status="pending",
                    )
                )
                created += 1
    await session.flush()
    return created


async def dispatch_due_reminders(
    session: AsyncSession,
    *,
    now: datetime,
    grace: timedelta,
    send: PushSender,
) -> int:
    """Deliver due ``pending`` reminders within the grace window (FR-007).

    A due reminder older than ``grace`` is left ``pending`` (overdue, visible
    in-app, never pushed — FR-006a). Delivery is best-effort: a subscription
    reported gone (404/410) is deleted (FR-016). Returns the number marked
    ``sent``.
    """
    due = list(
        (
            await session.execute(
                select(Reminder)
                .where(
                    Reminder.status == "pending",
                    Reminder.scheduled_for <= now,
                )
                .order_by(Reminder.scheduled_for)
            )
        )
        .scalars()
        .all()
    )

    titles = await load_reminder_titles(session, due)
    dispatched = 0
    for rem in due:
        if not is_within_grace(
            scheduled_for=rem.scheduled_for, now=now, grace=grace
        ):
            continue  # overdue — stays pending, not pushed (FR-006a)
        subs = list(
            (
                await session.execute(
                    select(PushSubscription).where(
                        PushSubscription.user_id == rem.user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        payload: dict[str, Any] = {
            "reminder_id": str(rem.id),
            "type": rem.type,
            "title": titles.get(rem.id, "MedMinder reminder"),
        }
        for sub in subs:
            result = await send(sub, payload)
            if result.gone:
                await session.delete(sub)
        rem.status = "sent"
        dispatched += 1
    await session.flush()
    return dispatched


async def load_reminder_titles(
    session: AsyncSession, reminders: Sequence[Reminder]
) -> dict[uuid.UUID, str]:
    """Human-readable title per reminder (used by dispatch + the list API).

    Dose: schedule label/time + the names of the medications attached to that
    schedule. Refill: the medication name + remaining count.
    """
    if not reminders:
        return {}

    schedule_ids = {
        r.schedule_id
        for r in reminders
        if r.type == "dose" and r.schedule_id is not None
    }
    medication_ids = {
        r.medication_id
        for r in reminders
        if r.type == "refill" and r.medication_id is not None
    }

    schedules: dict[uuid.UUID, Schedule] = {}
    schedule_meds: dict[uuid.UUID, list[str]] = {}
    if schedule_ids:
        for sched_row in (
            await session.execute(
                select(Schedule).where(Schedule.id.in_(schedule_ids))
            )
        ).scalars():
            schedules[sched_row.id] = sched_row
        for sid, name in (
            await session.execute(
                select(ScheduleMedication.schedule_id, Medication.name)
                .join(
                    Medication,
                    Medication.id == ScheduleMedication.medication_id,
                )
                .where(
                    ScheduleMedication.schedule_id.in_(schedule_ids),
                    Medication.deleted_at.is_(None),
                )
                .order_by(Medication.name)
            )
        ).all():
            schedule_meds.setdefault(sid, []).append(name)

    medications: dict[uuid.UUID, Medication] = {}
    if medication_ids:
        for med_row in (
            await session.execute(
                select(Medication).where(Medication.id.in_(medication_ids))
            )
        ).scalars():
            medications[med_row.id] = med_row

    titles: dict[uuid.UUID, str] = {}
    for r in reminders:
        if r.type == "dose" and r.schedule_id is not None:
            sched = schedules.get(r.schedule_id)
            meds = ", ".join(schedule_meds.get(r.schedule_id, [])) or "your medication"
            when = sched.time_of_day.strftime("%H:%M") if sched else ""
            label = sched.label if sched else ""
            if label:
                titles[r.id] = f"{label} ({when}): {meds}".replace(" ()", "")
            else:
                titles[r.id] = f"Time to take {meds}" + (f" ({when})" if when else "")
        elif r.type == "refill" and r.medication_id is not None:
            med = medications.get(r.medication_id)
            name = med.name if med else "your medication"
            count = med.refill_count if med else None
            titles[r.id] = f"Refill {name}" + (
                f" — {count} left" if count is not None else ""
            )
        else:
            titles[r.id] = "MedMinder reminder"
    return titles


__all__ = [
    "GENERATION_HORIZON",
    "PushSender",
    "dispatch_due_reminders",
    "generate_due_dose_reminders",
    "load_reminder_titles",
]
