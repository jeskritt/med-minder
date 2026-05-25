"""Async DB orchestration for Phase 7 reminders (FR-004/005/006/007).

The pure scheduling math lives in ``domain/reminders.py``; this module does
the DB I/O: materialising dose reminders for upcoming schedule slots and
dispatching due ones. Delivery goes through an injected ``send`` callable so
the dispatcher is testable with a fake sender and no network (Principle III).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
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
from medminder.domain.reminders import (
    defer_for_quiet_hours,
    is_within_grace,
    next_dose_fire_times_utc,
)
from medminder.domain.timezone import resolve_today_bounds

GENERATION_HORIZON: timedelta = timedelta(hours=48)
"""How far ahead dose reminders are materialised (plan research D3)."""

SNOOZE_DURATION: timedelta = timedelta(hours=1)
"""Fixed one-hour snooze (FR-009 / UC-5.2)."""


class ReminderNotFoundError(Exception):
    """The reminder doesn't exist or isn't owned by the user (→ HTTP 404)."""

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
        created += await _ensure_slot_reminders(
            session, schedule=sched, tz=tz, now=now, horizon=horizon
        )
    await session.flush()
    return created


async def _ensure_slot_reminders(
    session: AsyncSession,
    *,
    schedule: Schedule,
    tz: str,
    now: datetime,
    horizon: timedelta,
) -> int:
    """Idempotently insert pending dose reminders for one schedule's slots.

    Inserts a row per fire instant in ``[now, now + horizon)`` that has no
    existing non-``dismissed`` reminder at ``(schedule_id, scheduled_for)``.
    Does not flush — the caller owns the transaction boundary.
    """
    created = 0
    for fire in next_dose_fire_times_utc(
        time_of_day=schedule.time_of_day,
        days_of_week=schedule.days_of_week,
        tz=tz,
        now=now,
        horizon=horizon,
    ):
        already = (
            await session.execute(
                select(Reminder.id).where(
                    Reminder.type == "dose",
                    Reminder.schedule_id == schedule.id,
                    Reminder.scheduled_for == fire,
                    Reminder.status != "dismissed",
                )
            )
        ).first()
        if already is None:
            session.add(
                Reminder(
                    user_id=schedule.user_id,
                    type="dose",
                    schedule_id=schedule.id,
                    scheduled_for=fire,
                    status="pending",
                )
            )
            created += 1
    return created


async def regenerate_schedule_reminders(
    session: AsyncSession,
    *,
    schedule_id: uuid.UUID,
    now: datetime | None = None,
) -> int:
    """Re-sync a schedule's future dose reminders to its current state (FR-012).

    Deletes the schedule's **future** ``pending`` dose reminders (preserving
    ``sent``/``dismissed``/past history), then regenerates from the schedule's
    current time/days — but only if the schedule is live (not soft-deleted,
    owner live) and still has ≥1 non-deleted attached medication. A
    deleted/detached/med-less schedule therefore just gets its future pending
    reminders cancelled. Returns the count regenerated.
    """
    when = now if now is not None else datetime.now(UTC)
    await session.execute(
        delete(Reminder).where(
            Reminder.type == "dose",
            Reminder.schedule_id == schedule_id,
            Reminder.status == "pending",
            Reminder.scheduled_for > when,
        )
    )
    has_live_med = (
        select(ScheduleMedication.schedule_id)
        .join(Medication, Medication.id == ScheduleMedication.medication_id)
        .where(
            ScheduleMedication.schedule_id == Schedule.id,
            Medication.deleted_at.is_(None),
        )
        .exists()
    )
    row = (
        await session.execute(
            select(Schedule, User.timezone)
            .join(User, User.id == Schedule.user_id)
            .where(
                Schedule.id == schedule_id,
                Schedule.deleted_at.is_(None),
                User.deleted_at.is_(None),
                has_live_med,
            )
        )
    ).first()
    if row is None:
        await session.flush()
        return 0
    schedule, tz = row
    created = await _ensure_slot_reminders(
        session, schedule=schedule, tz=tz, now=when, horizon=GENERATION_HORIZON
    )
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

    user_ids = {r.user_id for r in due}
    users: dict[uuid.UUID, User] = {}
    if user_ids:
        for u in (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars():
            users[u.id] = u

    dispatched = 0
    for rem in due:
        if not is_within_grace(
            scheduled_for=rem.scheduled_for, now=now, grace=grace
        ):
            continue  # overdue — stays pending, not pushed (FR-006a)
        user = users.get(rem.user_id)
        if user is not None:
            # Quiet hours (FR-011): defer by rescheduling to the window end;
            # the row stays pending and a later tick delivers it.
            deferred = defer_for_quiet_hours(
                fire_utc=rem.scheduled_for,
                tz=user.timezone,
                quiet_start=user.quiet_hours_start,
                quiet_end=user.quiet_hours_end,
            )
            if deferred is not None:
                rem.scheduled_for = deferred
                continue
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


async def _load_owned_reminder(
    session: AsyncSession, *, user: User, reminder_id: uuid.UUID
) -> Reminder:
    rem = (
        await session.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
    ).scalar_one_or_none()
    if rem is None or rem.user_id != user.id:
        raise ReminderNotFoundError(str(reminder_id))
    return rem


async def snooze_reminder(
    session: AsyncSession,
    *,
    user: User,
    reminder_id: uuid.UUID,
    now: datetime,
) -> Reminder:
    """Snooze one of the user's reminders by one hour (FR-009/010).

    Dose: mark the original ``snoozed`` and create a fresh ``pending`` reminder
    at ``now + 1h``. Refill: move the *existing* warning forward instead of
    creating a second open row — the ``uq_reminders_open_refill`` invariant
    allows only one open refill warning per medication. Returns the reminder
    that will next fire. Re-snoozing is allowed (no cap).
    """
    rem = await _load_owned_reminder(session, user=user, reminder_id=reminder_id)

    if rem.type == "refill":
        rem.status = "pending"
        rem.scheduled_for = now + SNOOZE_DURATION
        await session.flush()
        await session.refresh(rem)
        return rem

    rem.status = "snoozed"
    successor = Reminder(
        user_id=rem.user_id,
        type=rem.type,
        schedule_id=rem.schedule_id,
        medication_id=rem.medication_id,
        scheduled_for=now + SNOOZE_DURATION,
        status="pending",
    )
    session.add(successor)
    await session.flush()
    await session.refresh(successor)
    return successor


async def dismiss_reminder(
    session: AsyncSession, *, user: User, reminder_id: uuid.UUID
) -> None:
    """Mark one of the user's reminders ``dismissed`` (FR-022). Idempotent."""
    rem = await _load_owned_reminder(session, user=user, reminder_id=reminder_id)
    rem.status = "dismissed"
    await session.flush()


async def resolve_dose_reminders(
    session: AsyncSession,
    *,
    user: User,
    schedule_id: uuid.UUID | None,
    taken_at: datetime,
) -> int:
    """Resolve today's open dose reminder(s) for the taken slot (FR-021).

    Marks ``dismissed`` every ``pending``/``snoozed`` dose reminder for
    ``schedule_id`` whose ``scheduled_for`` lands in the user-local day of
    ``taken_at`` — so a taken medication stops nagging and drops out of the
    in-app list. A no-op for an unscheduled (PRN) dose. Returns the count.
    """
    if schedule_id is None:
        return 0
    local_date = taken_at.astimezone(ZoneInfo(user.timezone)).date()
    bounds = resolve_today_bounds(user_tz=user.timezone, target_date=local_date)
    result = await session.execute(
        update(Reminder)
        .where(
            Reminder.user_id == user.id,
            Reminder.schedule_id == schedule_id,
            Reminder.type == "dose",
            Reminder.status.in_(["pending", "snoozed"]),
            Reminder.scheduled_for >= bounds.start_utc,
            Reminder.scheduled_for < bounds.end_utc,
        )
        .values(status="dismissed")
    )
    return result.rowcount or 0


async def ensure_refill_reminder(
    session: AsyncSession,
    *,
    user: User,
    medication: Medication,
    now: datetime | None = None,
) -> Reminder | None:
    """Create a refill warning for ``medication`` unless one is already open.

    Enforces the "one open refill warning per medication" invariant
    (uq_reminders_open_refill / FR-014): if an unresolved (``status <>
    'dismissed'``) refill reminder already exists for the med, this is a
    no-op. The caller decides *when* to warn (a downward threshold crossing).
    """
    existing = (
        await session.execute(
            select(Reminder.id).where(
                Reminder.type == "refill",
                Reminder.medication_id == medication.id,
                Reminder.status != "dismissed",
            )
        )
    ).first()
    if existing is not None:
        return None
    rem = Reminder(
        user_id=user.id,
        type="refill",
        medication_id=medication.id,
        scheduled_for=now if now is not None else datetime.now(UTC),
        status="pending",
    )
    session.add(rem)
    await session.flush()
    return rem


async def clear_refill_reminder(
    session: AsyncSession, *, medication: Medication
) -> int:
    """Resolve any open refill warning for ``medication`` (FR-014a re-arm).

    Marks ``dismissed`` every non-dismissed refill reminder for the med, so a
    future threshold crossing can warn again. Idempotent. Returns the count.
    """
    result = await session.execute(
        update(Reminder)
        .where(
            Reminder.type == "refill",
            Reminder.medication_id == medication.id,
            Reminder.status != "dismissed",
        )
        .values(status="dismissed")
    )
    return result.rowcount or 0


__all__ = [
    "GENERATION_HORIZON",
    "SNOOZE_DURATION",
    "PushSender",
    "ReminderNotFoundError",
    "clear_refill_reminder",
    "dismiss_reminder",
    "dispatch_due_reminders",
    "ensure_refill_reminder",
    "generate_due_dose_reminders",
    "load_reminder_titles",
    "regenerate_schedule_reminders",
    "resolve_dose_reminders",
    "snooze_reminder",
]
