"""Medications router: CRUD over ``/api/v1/medications``.

All routes require an authenticated session and are scoped to the
calling user.  Inline schedule management uses the
complete-replacement strategy described in the Phase 3 ``research.md``.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.db.models import Medication, Schedule, User
from medminder.domain.medications import (
    InvalidMedicationError,
    MedicationInput,
    create_medication,
    list_medications,
    list_schedules_for_medication,
    soft_delete_medication,
    update_medication,
)

router = APIRouter(prefix="/api/v1/medications", tags=["medications"])


class ScheduleOut(BaseModel):
    """Public view of a Schedule attached to a medication."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    time_of_day: time


class MedicationBody(BaseModel):
    """Inbound payload shared by ``POST`` and ``PUT``."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    quantity_per_dose: Decimal = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)
    times_per_day: int = Field(..., ge=0, le=24)
    start_date: date | None = None
    end_date: date | None = None
    total_doses: int | None = Field(default=None, gt=0)
    schedules: list[time] = Field(default_factory=list)
    refill_count: int | None = Field(default=None, ge=0)
    refill_threshold: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_dates(self) -> MedicationBody:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class MedicationOut(BaseModel):
    """Public view of a Medication plus its schedules."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    quantity_per_dose: Decimal
    unit: str
    times_per_day: int
    start_date: date | None
    end_date: date | None
    total_doses: int | None
    refill_count: int | None
    refill_threshold: int | None
    schedules: list[ScheduleOut]


class MedicationListOut(BaseModel):
    """Envelope for ``GET /api/v1/medications``."""

    model_config = ConfigDict(extra="forbid")

    items: list[MedicationOut]


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
    )


def _to_out(med: Medication, schedules: list[Schedule]) -> MedicationOut:
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
            ScheduleOut(id=s.id, time_of_day=s.time_of_day)
            for s in sorted(schedules, key=lambda s: s.time_of_day)
        ],
    )


@router.get("", response_model=MedicationListOut)
async def list_meds(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationListOut:
    """Return every active medication for the calling user."""
    meds = await list_medications(db, user_id=user.id)
    items: list[MedicationOut] = []
    for med in meds:
        scheds = list(
            await list_schedules_for_medication(db, medication_id=med.id)
        )
        items.append(_to_out(med, scheds))
    return MedicationListOut(items=items)


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _to_out(med, list(schedules))


@router.put("/{medication_id}", response_model=MedicationOut)
async def update_med(
    medication_id: uuid.UUID,
    body: MedicationBody,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationOut:
    """Replace a medication's fields and schedules."""
    try:
        result = await update_medication(
            db,
            user_id=user.id,
            medication_id=medication_id,
            payload=_to_input(body),
        )
    except InvalidMedicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found.",
        )
    med, schedules = result
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
    deleted = await soft_delete_medication(
        db, user_id=user.id, medication_id=medication_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
