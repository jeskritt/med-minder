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
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from medminder.db.models import (
    Dose,
    DoseInteractionOverride,
    DoseVoid,
    Medication,
    MedicationInteraction,
    Schedule,
    ScheduleMedication,
    User,
)
from medminder.domain.interactions import (
    InteractionConflict,
    MedicationInteractionConflictError,
    detect_interaction_conflict,
)
from medminder.domain.timers import (
    MinIntervalNotElapsedError,
    multi_sub_dose_window_full,
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
    interaction_acknowledged: bool = False,
) -> Dose:
    """Insert a new ``doses`` row attributed to the session user.

    ``interaction_acknowledged`` (Phase 6 / ADR-0008): when an active
    drug-interaction cooldown is detected and this is ``False``, no
    ``doses`` row is written and ``MedicationInteractionConflictError`` is
    raised (→ HTTP 409, always overridable). When ``True``, the dose is
    recorded *and* one append-only ``dose_interaction_overrides`` row
    per active conflict is written in the same transaction. It never
    weakens the non-overridable Phase 5 overdose guards, which run
    first.
    """
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

    if (
        med.timer_preference == "count_down"
        and med.min_interval_minutes is not None
    ):
        voided_exists = (
            select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
        )
        last = (
            await session.execute(
                select(Dose)
                .where(
                    Dose.user_id == user.id,
                    Dose.medication_id == medication_id,
                    not_(voided_exists),
                )
                .order_by(Dose.taken_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last is not None:
            next_allowed_at = last.taken_at + timedelta(
                minutes=med.min_interval_minutes
            )
            if next_allowed_at > taken_at:
                remaining = max(
                    1, int((next_allowed_at - taken_at).total_seconds())
                )
                raise MinIntervalNotElapsedError(
                    medication_id=medication_id,
                    next_allowed_at=next_allowed_at,
                    remaining_seconds=remaining,
                )

    if med.timer_preference == "multi_sub_dose":
        voided_exists = (
            select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
        )
        taken_ats = list(
            (
                await session.execute(
                    select(Dose.taken_at)
                    .where(
                        Dose.user_id == user.id,
                        Dose.medication_id == medication_id,
                        not_(voided_exists),
                    )
                    .order_by(Dose.taken_at.asc())
                )
            ).scalars()
        )
        violation = multi_sub_dose_window_full(med, taken_ats, taken_at)
        if violation is not None:
            raise violation

    # --- Drug-interaction cooldown (Phase 6 / ADR-0008) ----------------
    # Runs AFTER the non-overridable Phase 5 overdose guards above so an
    # acknowledgment can never defeat an overdose 409 (FR-010).
    interaction_conflict = None
    rules = list(
        (
            await session.execute(
                select(MedicationInteraction).where(
                    or_(
                        MedicationInteraction.medication_id == medication_id,
                        MedicationInteraction.conflicting_medication_id
                        == medication_id,
                    )
                )
            )
        ).scalars()
    )
    if rules:
        partner_ids = {
            (
                r.conflicting_medication_id
                if r.medication_id == medication_id
                else r.medication_id
            )
            for r in rules
        }
        # Only the user's own, non-deleted partner medications surface
        # (cross-user isolation, FR-019; soft-deleted exclusion, FR-018).
        name_rows = (
            await session.execute(
                select(Medication.id, Medication.name).where(
                    Medication.id.in_(partner_ids),
                    Medication.user_id == user.id,
                    Medication.deleted_at.is_(None),
                )
            )
        ).all()
        medication_names: dict[uuid.UUID, str] = {}
        for mid, name in name_rows:
            medication_names[mid] = name
        partner_last_non_voided: dict[uuid.UUID, datetime] = {}
        if medication_names:
            voided_exists = (
                select(DoseVoid.id)
                .where(DoseVoid.dose_id == Dose.id)
                .exists()
            )
            last_rows = (
                await session.execute(
                    select(Dose.medication_id, func.max(Dose.taken_at))
                    .where(
                        Dose.user_id == user.id,
                        Dose.medication_id.in_(medication_names.keys()),
                        not_(voided_exists),
                    )
                    .group_by(Dose.medication_id)
                )
            ).all()
            for mid, ts in last_rows:
                partner_last_non_voided[mid] = ts
        interaction_conflict = detect_interaction_conflict(
            medication_id=medication_id,
            rules=rules,
            partner_last_non_voided=partner_last_non_voided,
            medication_names=medication_names,
            prospective_taken_at=taken_at,
            now=taken_at,
        )
        if (
            interaction_conflict is not None
            and not interaction_acknowledged
        ):
            raise MedicationInteractionConflictError(
                medication_id=medication_id,
                conflict=interaction_conflict,
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

    # Acknowledged dose over an active conflict: persist the audit in
    # the same transaction (one row per active conflict).
    if interaction_conflict is not None:
        for c in interaction_conflict.conflicts:
            session.add(
                DoseInteractionOverride(
                    dose_id=dose.id,
                    conflicting_medication_id=c.conflicting_medication_id,
                )
            )
        await session.flush()
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

    # The EffectiveDose outerjoin is unaggregated: a slot with N
    # non-voided doses in today's window yields N rows. Collapse to
    # exactly one item per (schedule, medication) slot carrying the
    # *most recent* effective dose (or None) — the documented contract
    # ("the most recent effective dose per slot") and what the UI keys
    # on (`${schedule_id}-${medication_id}`). Rows arrive ordered by
    # (time_of_day, name); dict preserves that first-seen order.
    by_slot: dict[tuple[uuid.UUID, uuid.UUID], TodayItem] = {}
    for schedule, medication, dose in rows:
        key = (schedule.id, medication.id)
        existing = by_slot.get(key)
        if existing is None:
            by_slot[key] = TodayItem(
                schedule_id=schedule.id,
                medication_id=medication.id,
                name=medication.name,
                scheduled_time=schedule.time_of_day,
                quantity_per_dose=medication.quantity_per_dose,
                unit=medication.unit,
                dose=dose,
            )
        elif dose is not None and (
            existing.dose is None or dose.taken_at > existing.dose.taken_at
        ):
            by_slot[key] = TodayItem(
                schedule_id=schedule.id,
                medication_id=medication.id,
                name=medication.name,
                scheduled_time=schedule.time_of_day,
                quantity_per_dose=medication.quantity_per_dose,
                unit=medication.unit,
                dose=dose,
            )

    return TodayView(
        date=bounds.target_date,
        timezone=bounds.timezone_name,
        items=list(by_slot.values()),
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


async def load_active_interaction_state(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    medication_ids: list[uuid.UUID],
    now: datetime,
) -> dict[uuid.UUID, InteractionConflict]:
    """Currently-active interaction conflict per target medication.

    Read-side counterpart to the ``create_dose`` guard (prospective
    time is ``now``). Scoped to the user's own non-deleted medications
    (cross-user isolation FR-019; soft-deleted exclusion FR-018);
    voided doses never arm (FR-008). Returns only medications with at
    least one active conflict.
    """
    if not medication_ids:
        return {}

    rules = list(
        (
            await session.execute(
                select(MedicationInteraction).where(
                    or_(
                        MedicationInteraction.medication_id.in_(
                            medication_ids
                        ),
                        MedicationInteraction.conflicting_medication_id.in_(
                            medication_ids
                        ),
                    )
                )
            )
        ).scalars()
    )
    if not rules:
        return {}

    involved: set[uuid.UUID] = set(medication_ids)
    for r in rules:
        involved.add(r.medication_id)
        involved.add(r.conflicting_medication_id)

    name_rows = (
        await session.execute(
            select(Medication.id, Medication.name).where(
                Medication.id.in_(involved),
                Medication.user_id == user_id,
                Medication.deleted_at.is_(None),
            )
        )
    ).all()
    medication_names: dict[uuid.UUID, str] = {}
    for mid, name in name_rows:
        medication_names[mid] = name
    if not medication_names:
        return {}

    voided_exists = (
        select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
    )
    last_rows = (
        await session.execute(
            select(Dose.medication_id, func.max(Dose.taken_at))
            .where(
                Dose.user_id == user_id,
                Dose.medication_id.in_(medication_names.keys()),
                not_(voided_exists),
            )
            .group_by(Dose.medication_id)
        )
    ).all()
    partner_last_non_voided: dict[uuid.UUID, datetime] = {}
    for mid, ts in last_rows:
        partner_last_non_voided[mid] = ts

    out: dict[uuid.UUID, InteractionConflict] = {}
    for med_id in medication_ids:
        if med_id not in medication_names:
            continue
        conflict = detect_interaction_conflict(
            medication_id=med_id,
            rules=rules,
            partner_last_non_voided=partner_last_non_voided,
            medication_names=medication_names,
            prospective_taken_at=now,
            now=now,
        )
        if conflict is not None:
            out[med_id] = conflict
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
    "load_active_interaction_state",
    "load_non_voided_history_for_meds",
    "today_view",
    "void_dose",
]
