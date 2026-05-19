"""Medications domain — DB-aware CRUD plus pure validation helpers.

The pure helpers (``validate_medication_input``, ``InvalidMedicationError``)
are tested without a DB or HTTP server, per Constitution Principle III.
The async helpers wrap the SQLAlchemy operations the API layer needs:
soft-delete on the medication, complete-replacement on the schedules.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Medication, Schedule, ScheduleMedication
from medminder.db.models.medications import TimerPreference


class InvalidMedicationError(ValueError):
    """Raised when ``MedicationInput`` fails business-logic validation."""


@dataclass(frozen=True)
class MedicationInput:
    """Canonical inbound shape for create/update.  Pure data."""

    name: str
    quantity_per_dose: Decimal
    unit: str
    times_per_day: int
    schedules: Sequence[time]
    start_date: date | None = None
    end_date: date | None = None
    total_doses: int | None = None
    refill_count: int | None = None
    refill_threshold: int | None = None
    timer_preference: TimerPreference = "none"
    min_interval_minutes: int | None = None
    window_duration_minutes: int | None = None


def validate_medication_input(payload: MedicationInput) -> None:
    """Raise :class:`InvalidMedicationError` if ``payload`` is invalid.

    Mirrors the spec's user-visible rules: non-blank name/unit, positive
    dosage, sensible date ordering, ``total_doses`` must be NULL when
    untracked (manual ``0`` rejected), and refill fields ``>= 0``.
    """
    if not payload.name.strip():
        raise InvalidMedicationError("name must not be blank")
    if not payload.unit.strip():
        raise InvalidMedicationError("unit must not be blank")
    if payload.quantity_per_dose <= 0:
        raise InvalidMedicationError("quantity_per_dose must be > 0")
    if payload.times_per_day < 0:
        raise InvalidMedicationError("times_per_day must be >= 0")
    if (
        payload.start_date is not None
        and payload.end_date is not None
        and payload.end_date < payload.start_date
    ):
        raise InvalidMedicationError("end_date must be on or after start_date")
    if payload.total_doses is not None and payload.total_doses <= 0:
        # Spec: untracked must be NULL; manual ``0`` (or negative) is rejected.
        raise InvalidMedicationError(
            "total_doses must be NULL for untracked or > 0 (manual 0 not allowed)"
        )
    if payload.refill_count is not None and payload.refill_count < 0:
        raise InvalidMedicationError("refill_count must be >= 0")
    if payload.refill_threshold is not None and payload.refill_threshold < 0:
        raise InvalidMedicationError("refill_threshold must be >= 0")
    if payload.timer_preference == "count_down" and (
        payload.min_interval_minutes is None or payload.min_interval_minutes <= 0
    ):
        raise InvalidMedicationError(
            "count_down timer_preference requires min_interval_minutes > 0"
        )
    if payload.timer_preference == "multi_sub_dose" and (
        payload.window_duration_minutes is None
        or payload.window_duration_minutes <= 0
    ):
        raise InvalidMedicationError(
            "multi_sub_dose timer_preference requires window_duration_minutes > 0"
        )
    if (
        payload.timer_preference == "multi_sub_dose"
        and payload.times_per_day < 1
    ):
        # times_per_day is the per-window slot count (slots_total); a
        # multi_sub_dose med with 0 slots is meaningless and breaks the
        # timer-state wire model (MultiSubDosePayload.slots_total >= 1).
        raise InvalidMedicationError(
            "multi_sub_dose timer_preference requires times_per_day >= 1"
        )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _set_writable_fields(med: Medication, payload: MedicationInput) -> None:
    med.name = payload.name.strip()
    med.quantity_per_dose = payload.quantity_per_dose
    med.unit = payload.unit.strip()
    med.times_per_day = payload.times_per_day
    med.start_date = payload.start_date
    med.end_date = payload.end_date
    med.total_doses = payload.total_doses
    med.refill_count = payload.refill_count
    med.refill_threshold = payload.refill_threshold
    med.timer_preference = payload.timer_preference
    med.min_interval_minutes = payload.min_interval_minutes
    med.window_duration_minutes = payload.window_duration_minutes


async def list_medications(
    session: AsyncSession, *, user_id: uuid.UUID
) -> Sequence[Medication]:
    """Return non-soft-deleted medications for the user, oldest first."""
    stmt = (
        select(Medication)
        .where(Medication.user_id == user_id, Medication.deleted_at.is_(None))
        .order_by(Medication.created_at)
    )
    return (await session.execute(stmt)).scalars().all()


async def get_medication(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    medication_id: uuid.UUID,
) -> Medication | None:
    """Fetch a single non-deleted medication owned by ``user_id``."""
    stmt = select(Medication).where(
        Medication.id == medication_id,
        Medication.user_id == user_id,
        Medication.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_schedules_for_medication(
    session: AsyncSession,
    *,
    medication_id: uuid.UUID,
) -> Sequence[Schedule]:
    """Return live schedules linked to ``medication_id`` (active only)."""
    stmt = (
        select(Schedule)
        .join(
            ScheduleMedication,
            ScheduleMedication.schedule_id == Schedule.id,
        )
        .where(
            ScheduleMedication.medication_id == medication_id,
            Schedule.deleted_at.is_(None),
        )
        .order_by(Schedule.time_of_day)
    )
    return (await session.execute(stmt)).scalars().all()


async def _replace_schedules(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    medication: Medication,
    schedules: Sequence[time],
) -> list[Schedule]:
    """Soft-delete previous schedule links and create fresh ones.

    Per research.md item 2 (complete-replacement strategy): drop the
    M:M join rows for this medication, soft-delete the previously linked
    schedule rows (so listings stop returning them), then create new
    schedules + join rows for the supplied times.
    """
    prev_link_stmt = select(ScheduleMedication.schedule_id).where(
        ScheduleMedication.medication_id == medication.id
    )
    prev_schedule_ids = list(
        (await session.execute(prev_link_stmt)).scalars().all()
    )
    if prev_schedule_ids:
        await session.execute(
            delete(ScheduleMedication).where(
                ScheduleMedication.medication_id == medication.id
            )
        )
        now = _utcnow()
        prev_rows = (
            await session.execute(
                select(Schedule).where(Schedule.id.in_(prev_schedule_ids))
            )
        ).scalars().all()
        for sched in prev_rows:
            if sched.deleted_at is None:
                sched.deleted_at = now

    new_rows: list[Schedule] = []
    for tod in schedules:
        sched = Schedule(
            user_id=user_id,
            time_of_day=tod,
            label=medication.name,
        )
        session.add(sched)
        new_rows.append(sched)
    if new_rows:
        await session.flush()
        for sched in new_rows:
            session.add(
                ScheduleMedication(
                    schedule_id=sched.id, medication_id=medication.id
                )
            )
        await session.flush()
    return new_rows


async def create_medication(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: MedicationInput,
) -> tuple[Medication, list[Schedule]]:
    """Create a medication and its inline schedules in one transaction."""
    validate_medication_input(payload)
    med = Medication(
        user_id=user_id,
        name=payload.name.strip(),
        quantity_per_dose=payload.quantity_per_dose,
        unit=payload.unit.strip(),
        times_per_day=payload.times_per_day,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_doses=payload.total_doses,
        timer_preference=payload.timer_preference,
        min_interval_minutes=payload.min_interval_minutes,
        window_duration_minutes=payload.window_duration_minutes,
        refill_count=payload.refill_count,
        refill_threshold=payload.refill_threshold,
    )
    session.add(med)
    await session.flush()
    schedules = await _replace_schedules(
        session, user_id=user_id, medication=med, schedules=payload.schedules
    )
    return med, schedules


async def update_medication(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    medication_id: uuid.UUID,
    payload: MedicationInput,
) -> tuple[Medication, list[Schedule]] | None:
    """Replace medication fields and inline schedules; ``None`` if missing."""
    validate_medication_input(payload)
    med = await get_medication(
        session, user_id=user_id, medication_id=medication_id
    )
    if med is None:
        return None
    _set_writable_fields(med, payload)
    await session.flush()
    schedules = await _replace_schedules(
        session, user_id=user_id, medication=med, schedules=payload.schedules
    )
    return med, schedules


async def soft_delete_medication(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    medication_id: uuid.UUID,
) -> bool:
    """Mark a medication soft-deleted; returns ``False`` if not found."""
    med = await get_medication(
        session, user_id=user_id, medication_id=medication_id
    )
    if med is None:
        return False
    med.deleted_at = _utcnow()
    await session.flush()
    return True


__all__ = [
    "InvalidMedicationError",
    "MedicationInput",
    "create_medication",
    "get_medication",
    "list_medications",
    "list_schedules_for_medication",
    "soft_delete_medication",
    "update_medication",
    "validate_medication_input",
]
