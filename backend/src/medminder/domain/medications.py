"""Medications domain — DB-aware CRUD plus pure validation helpers.

The pure helpers (``validate_medication_input``, ``InvalidMedicationError``)
are tested without a DB or HTTP server, per Constitution Principle III.
The async helpers wrap the SQLAlchemy operations the API layer needs:
soft-delete on the medication; the schedule join rows
(`ScheduleMedication`) are reconciled by id (UX enhancements made
schedules a shared user-level resource).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Medication, Schedule, ScheduleMedication
from medminder.db.models.medications import TimerPreference


class InvalidMedicationError(ValueError):
    """Raised when ``MedicationInput`` fails business-logic validation."""


@dataclass(frozen=True)
class MedicationInput:
    """Canonical inbound shape for create/update.  Pure data.

    `schedules` is a list of **existing** `Schedule.id`s the medication
    should be linked to (UX enhancements: schedules became shared
    user-level resources). Validation rejects unknown / cross-user /
    soft-deleted ids; `_replace_schedules` reconciles `ScheduleMedication`
    join rows.
    """

    name: str
    quantity_per_dose: Decimal
    unit: str
    times_per_day: int
    schedules: Sequence[uuid.UUID] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    total_doses: int | None = None
    refill_count: int | None = None
    refill_threshold: int | None = None
    timer_preference: TimerPreference = "none"
    min_interval_minutes: int | None = None
    window_duration_minutes: int | None = None
    # UX enhancements (Phase 6.5):
    pill_strength: Decimal | None = None
    pills_per_dose: int | None = None
    max_doses_per_day: int | None = None


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
        # times_per_day is the max-concurrent cap ("max at a time"); a
        # multi_sub_dose med with 0 is meaningless and breaks the
        # timer-state wire model (MultiSubDosePayload.max_concurrent >= 1).
        raise InvalidMedicationError(
            "multi_sub_dose timer_preference requires times_per_day >= 1"
        )
    # Pill-based dosage: both-or-neither, both positive when set.
    if (payload.pill_strength is None) != (payload.pills_per_dose is None):
        raise InvalidMedicationError(
            "pill_strength and pills_per_dose must be set together"
        )
    if payload.pill_strength is not None and payload.pill_strength <= 0:
        raise InvalidMedicationError("pill_strength must be > 0")
    if payload.pills_per_dose is not None and payload.pills_per_dose < 1:
        raise InvalidMedicationError("pills_per_dose must be >= 1")
    # multi_sub_dose daily cap: only meaningful on that mode; must be
    # >= the max-at-a-time cap (times_per_day).
    if payload.max_doses_per_day is not None:
        if payload.timer_preference != "multi_sub_dose":
            raise InvalidMedicationError(
                "max_doses_per_day is only valid for multi_sub_dose"
            )
        if payload.max_doses_per_day < 1:
            raise InvalidMedicationError(
                "max_doses_per_day must be >= 1"
            )
        if payload.max_doses_per_day < payload.times_per_day:
            raise InvalidMedicationError(
                "max_doses_per_day must be >= times_per_day "
                "(the per-window slot cap)"
            )


def _effective_quantity_per_dose(payload: MedicationInput) -> Decimal:
    """Derive `quantity_per_dose` for the model write.

    Pill-based meds (both `pill_strength` and `pills_per_dose` set):
    quantity is `pill_strength * pills_per_dose` and overrides any
    user-supplied `quantity_per_dose`. Non-pill meds use the supplied
    value unchanged.
    """
    if (
        payload.pill_strength is not None
        and payload.pills_per_dose is not None
    ):
        return payload.pill_strength * Decimal(payload.pills_per_dose)
    return payload.quantity_per_dose


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _set_writable_fields(med: Medication, payload: MedicationInput) -> None:
    med.name = payload.name.strip()
    med.quantity_per_dose = _effective_quantity_per_dose(payload)
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
    med.pill_strength = payload.pill_strength
    med.pills_per_dose = payload.pills_per_dose
    med.max_doses_per_day = payload.max_doses_per_day


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
    schedules: Sequence[uuid.UUID],
) -> list[Schedule]:
    """Reconcile `ScheduleMedication` join rows for this medication.

    UX enhancements: schedules are shared user-level resources owned
    by a separate CRUD surface (`/api/v1/schedules`). The med form
    sends a list of existing `Schedule.id`s; this function only
    inserts/deletes M:M join rows — it does NOT create or
    soft-delete Schedule rows. Validates each id belongs to the
    user and is non-soft-deleted; raises `InvalidMedicationError`
    on any unknown / cross-user / soft-deleted id.
    """
    target_ids: list[uuid.UUID] = list(dict.fromkeys(schedules))  # dedupe, keep order
    if target_ids:
        owned = set(
            (
                await session.execute(
                    select(Schedule.id).where(
                        Schedule.id.in_(target_ids),
                        Schedule.user_id == user_id,
                        Schedule.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = [sid for sid in target_ids if sid not in owned]
        if missing:
            raise InvalidMedicationError(
                f"schedule not found or not owned: {missing[0]}"
            )

    current_ids = set(
        (
            await session.execute(
                select(ScheduleMedication.schedule_id).where(
                    ScheduleMedication.medication_id == medication.id
                )
            )
        )
        .scalars()
        .all()
    )
    target_set = set(target_ids)

    to_remove = current_ids - target_set
    if to_remove:
        await session.execute(
            delete(ScheduleMedication).where(
                ScheduleMedication.medication_id == medication.id,
                ScheduleMedication.schedule_id.in_(to_remove),
            )
        )

    to_add = target_set - current_ids
    for sid in to_add:
        session.add(
            ScheduleMedication(
                schedule_id=sid, medication_id=medication.id
            )
        )
    if to_remove or to_add:
        await session.flush()

    if not target_ids:
        return []
    rows = (
        await session.execute(
            select(Schedule)
            .where(Schedule.id.in_(target_ids))
            .order_by(Schedule.time_of_day)
        )
    ).scalars().all()
    return list(rows)


async def create_medication(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: MedicationInput,
) -> tuple[Medication, list[Schedule]]:
    """Create a medication and link existing schedules in one transaction."""
    validate_medication_input(payload)
    med = Medication(
        user_id=user_id,
        name=payload.name.strip(),
        quantity_per_dose=_effective_quantity_per_dose(payload),
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
        pill_strength=payload.pill_strength,
        pills_per_dose=payload.pills_per_dose,
        max_doses_per_day=payload.max_doses_per_day,
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
    """Replace medication fields and schedule links; ``None`` if missing."""
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
