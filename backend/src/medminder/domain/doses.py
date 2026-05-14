"""Domain logic for the dose lifecycle: create, void, today-view.

Three exports:

- :func:`create_dose` — append-only insert into ``doses`` with ownership
  and schedule-linkage validation.
- :func:`void_dose` — insert a compensating row into ``dose_voids``.
- :func:`today_view` — read the user's scheduled slots for a given day
  along with the most recent effective dose per slot.

All write operations derive ``user_id`` / ``voided_by_user_id`` from the
session user, never from the request body (plan §Constitution Check I).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import and_, not_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from medminder.db.models import (
    Dose,
    DoseVoid,
    Medication,
    Schedule,
    ScheduleMedication,
    User,
)
from medminder.domain.timezone import resolve_today_bounds


class DoseError(Exception):
    """Base for dose-domain errors."""


class DoseForbiddenError(DoseError):
    """The session user does not own the medication or dose (HTTP 403)."""


class DoseValidationError(DoseError):
    """Validation failure: bad linkage, soft-deleted target, etc. (HTTP 422)."""


class DoseNotFoundError(DoseError):
    """Target dose does not exist (HTTP 404)."""


class DoseAlreadyVoidedError(DoseError):
    """A void already exists for this dose (HTTP 409)."""


async def create_dose(
    session: AsyncSession,
    *,
    user: User,
    medication_id: uuid.UUID,
    taken_at: datetime,
    schedule_id: uuid.UUID | None = None,
    quantity: Decimal | None = None,
) -> Dose:
    """Insert a new ``doses`` row attributed to the session user."""
    med = (
        await session.execute(select(Medication).where(Medication.id == medication_id))
    ).scalar_one_or_none()
    if med is None or med.user_id != user.id:
        raise DoseForbiddenError("Medication not found or not owned by user.")
    if med.deleted_at is not None:
        raise DoseValidationError("Medication is deleted.")

    if schedule_id is not None:
        sched = (
            await session.execute(select(Schedule).where(Schedule.id == schedule_id))
        ).scalar_one_or_none()
        if sched is None or sched.user_id != user.id or sched.deleted_at is not None:
            raise DoseValidationError("Schedule is not available.")
        link = (
            await session.execute(
                select(ScheduleMedication).where(
                    ScheduleMedication.schedule_id == schedule_id,
                    ScheduleMedication.medication_id == medication_id,
                )
            )
        ).scalar_one_or_none()
        if link is None:
            raise DoseValidationError(
                "Schedule is not linked to the given medication.",
            )

    effective_quantity = quantity if quantity is not None else med.quantity_per_dose

    dose = Dose(
        user_id=user.id,
        medication_id=medication_id,
        schedule_id=schedule_id,
        taken_at=taken_at,
        quantity=effective_quantity,
    )
    session.add(dose)
    await session.flush()
    await session.refresh(dose)
    return dose


async def void_dose(
    session: AsyncSession,
    *,
    user: User,
    dose_id: uuid.UUID,
) -> DoseVoid:
    """Insert a ``dose_voids`` row marking the dose as ineffective."""
    dose = (
        await session.execute(select(Dose).where(Dose.id == dose_id))
    ).scalar_one_or_none()
    if dose is None:
        raise DoseNotFoundError("Dose does not exist.")
    if dose.user_id != user.id:
        raise DoseForbiddenError("Dose belongs to a different user.")

    void = DoseVoid(
        dose_id=dose.id,
        voided_by_user_id=user.id,
        voided_at=datetime.now(UTC),
    )
    session.add(void)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise DoseAlreadyVoidedError("Dose has already been voided.") from exc
    await session.refresh(void)
    return void


@dataclass(frozen=True)
class TodayItem:
    """One per-slot row in the Today view."""

    schedule_id: uuid.UUID
    medication_id: uuid.UUID
    name: str
    scheduled_time: time
    quantity_per_dose: Decimal
    unit: str
    dose: Dose | None


@dataclass(frozen=True)
class TodayView:
    date: date
    timezone: str
    items: list[TodayItem]


async def today_view(
    session: AsyncSession,
    *,
    user: User,
    timezone_override: str | None = None,
    target_date: date | None = None,
) -> TodayView:
    """Read the user's scheduled slots for ``target_date`` in their TZ."""
    bounds = resolve_today_bounds(
        user_tz=user.timezone,
        override_tz=timezone_override,
        target_date=target_date,
    )

    EffectiveDose = aliased(Dose)  # noqa: N806  # SQLAlchemy alias used as class
    voided_exists = (
        select(DoseVoid.id).where(DoseVoid.dose_id == EffectiveDose.id).exists()
    )
    dow_mask = 1 << bounds.day_of_week

    stmt = (
        select(Schedule, Medication, EffectiveDose)
        .join(
            ScheduleMedication,
            ScheduleMedication.schedule_id == Schedule.id,
        )
        .join(
            Medication,
            Medication.id == ScheduleMedication.medication_id,
        )
        .outerjoin(
            EffectiveDose,
            and_(
                EffectiveDose.schedule_id == Schedule.id,
                EffectiveDose.medication_id == Medication.id,
                EffectiveDose.user_id == user.id,
                EffectiveDose.taken_at >= bounds.start_utc,
                EffectiveDose.taken_at < bounds.end_utc,
                not_(voided_exists),
            ),
        )
        .where(
            Schedule.user_id == user.id,
            Schedule.deleted_at.is_(None),
            Medication.user_id == user.id,
            Medication.deleted_at.is_(None),
            Schedule.days_of_week.op("&")(dow_mask) != 0,
        )
        .order_by(Schedule.time_of_day, Medication.name)
    )

    rows = (await session.execute(stmt)).all()

    items = [
        TodayItem(
            schedule_id=schedule.id,
            medication_id=medication.id,
            name=medication.name,
            scheduled_time=schedule.time_of_day,
            quantity_per_dose=medication.quantity_per_dose,
            unit=medication.unit,
            dose=dose,
        )
        for schedule, medication, dose in rows
    ]

    return TodayView(
        date=bounds.target_date,
        timezone=bounds.timezone_name,
        items=items,
    )


async def load_non_voided_history_for_meds(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    medication_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[Dose]]:
    """Return non-voided doses per medication, newest-first.

    Used by the Phase 5 timer-state computation; filters on ``user_id``
    (cross-user isolation) and excludes voided doses via the same
    NOT EXISTS pattern ``today_view`` uses.
    """
    if not medication_ids:
        return {}

    voided_exists = (
        select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
    )
    stmt = (
        select(Dose)
        .where(
            Dose.user_id == user_id,
            Dose.medication_id.in_(medication_ids),
            not_(voided_exists),
        )
        .order_by(Dose.taken_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    out: dict[uuid.UUID, list[Dose]] = {mid: [] for mid in medication_ids}
    for dose in rows:
        out[dose.medication_id].append(dose)
    return out


__all__ = [
    "DoseAlreadyVoidedError",
    "DoseError",
    "DoseForbiddenError",
    "DoseNotFoundError",
    "DoseValidationError",
    "TodayItem",
    "TodayView",
    "create_dose",
    "load_non_voided_history_for_meds",
    "today_view",
    "void_dose",
]
