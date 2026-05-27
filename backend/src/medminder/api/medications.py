"""Medications router: CRUD over ``/api/v1/medications``.

All routes require an authenticated session and are scoped to the
calling user.  Inline schedule management uses the
complete-replacement strategy described in the Phase 3 ``research.md``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.api.schemas.interactions import (
    InteractionStateOut,
    to_interaction_state_out,
)
from medminder.api.schemas.medications import (
    MedicationBody,
    MedicationDetailOut,
    MedicationListOut,
    MedicationOut,
    ScheduleOut,
)
from medminder.api.schemas.timers import TimerStateOut, to_timer_state_out
from medminder.db.models import Medication, Schedule, User
from medminder.domain.doses import (
    load_active_interaction_state,
    load_non_voided_history_for_meds,
)
from medminder.domain.medications import (
    InvalidMedicationError,
    MedicationInput,
    create_medication,
    get_medication,
    list_medications,
    list_schedules_for_medication,
    soft_delete_medication,
    update_medication,
)
from medminder.domain.reminder_dispatch import (
    clear_refill_reminder,
    regenerate_schedule_reminders,
)
from medminder.domain.timers import compute_timer_state

router = APIRouter(prefix="/api/v1/medications", tags=["medications"])


def _to_input(body: MedicationBody) -> MedicationInput:
    return MedicationInput(
        name=body.name,
        quantity_per_dose=body.quantity_per_dose,
        unit=body.unit,
        times_per_day=body.times_per_day,
        schedules=body.schedules,
        start_date=body.start_date,
        end_date=body.end_date,
        total_doses=body.total_doses,
        refill_count=body.refill_count,
        refill_threshold=body.refill_threshold,
        timer_preference=body.timer_preference,
        min_interval_minutes=body.min_interval_minutes,
        window_duration_minutes=body.window_duration_minutes,
        pill_strength=body.pill_strength,
        pills_per_dose=body.pills_per_dose,
        max_doses_per_day=body.max_doses_per_day,
    )


def _to_out(
    med: Medication,
    schedules: list[Schedule],
    *,
    timer_state: TimerStateOut | None = None,
    interaction_state: InteractionStateOut | None = None,
) -> MedicationOut:
    return MedicationOut(
        id=med.id,
        name=med.name,
        quantity_per_dose=med.quantity_per_dose,
        unit=med.unit,
        times_per_day=med.times_per_day,
        start_date=med.start_date,
        end_date=med.end_date,
        total_doses=med.total_doses,
        refill_count=med.refill_count,
        refill_threshold=med.refill_threshold,
        schedules=[
            ScheduleOut(
                id=s.id,
                time_of_day=s.time_of_day,
                label=s.label,
                days_of_week=s.days_of_week,
            )
            for s in sorted(schedules, key=lambda s: s.time_of_day)
        ],
        timer_preference=med.timer_preference,
        min_interval_minutes=med.min_interval_minutes,
        window_duration_minutes=med.window_duration_minutes,
        pill_strength=med.pill_strength,
        pills_per_dose=med.pills_per_dose,
        max_doses_per_day=med.max_doses_per_day,
        timer_state=timer_state,
        interaction_state=interaction_state,
    )


@router.get("", response_model=MedicationListOut)
async def list_meds(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationListOut:
    """Return every active medication for the calling user."""
    meds = list(await list_medications(db, user_id=user.id))
    history = await load_non_voided_history_for_meds(
        db, user_id=user.id, medication_ids=[m.id for m in meds]
    )
    now = datetime.now(UTC)
    conflicts = await load_active_interaction_state(
        db, user_id=user.id, medication_ids=[m.id for m in meds], now=now
    )
    items: list[MedicationOut] = []
    for med in meds:
        scheds = list(
            await list_schedules_for_medication(db, medication_id=med.id)
        )
        state = compute_timer_state(med, history.get(med.id, []), now=now)
        items.append(
            _to_out(
                med,
                scheds,
                timer_state=to_timer_state_out(state),
                interaction_state=to_interaction_state_out(
                    conflicts.get(med.id)
                ),
            )
        )
    return MedicationListOut(items=items)


@router.get("/{medication_id}", response_model=MedicationDetailOut)
async def get_med(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationDetailOut:
    """Return a single medication owned by the caller.

    Responds 404 (NOT 403) when the medication does not exist, is
    soft-deleted, or belongs to another user. ``get_medication``
    folds all three into a single ``None`` result, so the three cases
    are observably indistinguishable — no existence leak (FR-014).
    """
    med = await get_medication(db, user_id=user.id, medication_id=medication_id)
    if med is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    schedules = list(
        await list_schedules_for_medication(db, medication_id=med.id)
    )
    history = await load_non_voided_history_for_meds(
        db, user_id=user.id, medication_ids=[med.id]
    )
    now = datetime.now(UTC)
    state = compute_timer_state(med, history.get(med.id, []), now=now)
    conflicts = await load_active_interaction_state(
        db, user_id=user.id, medication_ids=[med.id], now=now
    )
    base = _to_out(
        med,
        schedules,
        timer_state=to_timer_state_out(state),
        interaction_state=to_interaction_state_out(conflicts.get(med.id)),
    )
    return MedicationDetailOut(**base.model_dump())


@router.post(
    "",
    response_model=MedicationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_med(
    body: MedicationBody,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationOut:
    """Create a medication and its inline schedules."""
    try:
        med, schedules = await create_medication(
            db, user_id=user.id, payload=_to_input(body)
        )
    except InvalidMedicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    # FR-012: generate reminders for the schedules this med attached to.
    for sched in schedules:
        await regenerate_schedule_reminders(db, schedule_id=sched.id)
    return _to_out(med, list(schedules))


@router.put("/{medication_id}", response_model=MedicationOut)
async def update_med(
    medication_id: uuid.UUID,
    body: MedicationBody,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationOut:
    """Replace a medication's fields and schedules."""
    # Capture the schedules attached *before* the edit so detached ones also
    # get their reminders re-synced (FR-012).
    old_schedule_ids = {
        s.id
        for s in await list_schedules_for_medication(
            db, medication_id=medication_id
        )
    }
    try:
        result = await update_medication(
            db,
            user_id=user.id,
            medication_id=medication_id,
            payload=_to_input(body),
        )
    except InvalidMedicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found.",
        )
    med, schedules = result
    # FR-014a: if the med is no longer low on supply (a refill was recorded),
    # clear any open refill warning so a future crossing can warn again.
    still_low = (
        med.refill_count is not None
        and med.refill_threshold is not None
        and med.refill_count <= med.refill_threshold
    )
    if not still_low:
        await clear_refill_reminder(db, medication=med)
    # FR-012: re-sync reminders for both newly-attached and detached schedules.
    for sid in old_schedule_ids | {s.id for s in schedules}:
        await regenerate_schedule_reminders(db, schedule_id=sid)
    return _to_out(med, list(schedules))


@router.delete(
    "/{medication_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_med(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Soft-delete a medication owned by the caller."""
    affected_schedule_ids = [
        s.id
        for s in await list_schedules_for_medication(
            db, medication_id=medication_id
        )
    ]
    deleted = await soft_delete_medication(
        db, user_id=user.id, medication_id=medication_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found.",
        )
    # FR-012: the med is gone from these schedules — re-sync their reminders.
    for sid in affected_schedule_ids:
        await regenerate_schedule_reminders(db, schedule_id=sid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
