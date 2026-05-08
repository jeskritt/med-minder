"""Domain tests for ``create_dose`` / ``void_dose`` (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Dose, ScheduleMedication
from medminder.domain.doses import (
    DoseAlreadyVoidedError,
    DoseForbiddenError,
    DoseNotFoundError,
    DoseValidationError,
    create_dose,
    void_dose,
)
from tests.db.factories import (
    make_dose,
    make_medication,
    make_schedule,
    make_user,
)


async def _link(
    session: AsyncSession,
    schedule_id: object,
    medication_id: object,
) -> None:
    session.add(
        ScheduleMedication(schedule_id=schedule_id, medication_id=medication_id)
    )
    await session.flush()


# ---------------------------------------------------------------------------
# create_dose
# ---------------------------------------------------------------------------


async def test_create_dose_happy(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    await _link(session, sched.id, med.id)

    dose = await create_dose(
        session,
        user=user,
        medication_id=med.id,
        schedule_id=sched.id,
        taken_at=datetime.now(UTC),
    )
    assert dose.id is not None
    assert dose.user_id == user.id
    assert dose.medication_id == med.id
    assert dose.schedule_id == sched.id
    # Default quantity comes from medications.quantity_per_dose.
    assert dose.quantity == med.quantity_per_dose


async def test_create_dose_explicit_quantity(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = await create_dose(
        session,
        user=user,
        medication_id=med.id,
        taken_at=datetime.now(UTC),
        quantity=Decimal("0.500"),
    )
    assert dose.quantity == Decimal("0.500")


async def test_create_dose_cross_user_forbidden(session: AsyncSession) -> None:
    owner = await make_user(session)
    intruder = await make_user(session)
    med = await make_medication(session, user=owner)
    with pytest.raises(DoseForbiddenError):
        await create_dose(
            session,
            user=intruder,
            medication_id=med.id,
            taken_at=datetime.now(UTC),
        )


async def test_create_dose_unlinked_schedule_invalid(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    # No schedule_medications row linking the two.
    with pytest.raises(DoseValidationError):
        await create_dose(
            session,
            user=user,
            medication_id=med.id,
            schedule_id=sched.id,
            taken_at=datetime.now(UTC),
        )


async def test_create_dose_soft_deleted_medication_invalid(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    med.deleted_at = datetime.now(UTC)
    await session.flush()
    with pytest.raises(DoseValidationError):
        await create_dose(
            session,
            user=user,
            medication_id=med.id,
            taken_at=datetime.now(UTC),
        )


async def test_create_dose_soft_deleted_schedule_invalid(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    await _link(session, sched.id, med.id)
    sched.deleted_at = datetime.now(UTC)
    await session.flush()
    with pytest.raises(DoseValidationError):
        await create_dose(
            session,
            user=user,
            medication_id=med.id,
            schedule_id=sched.id,
            taken_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# void_dose
# ---------------------------------------------------------------------------


async def test_void_dose_happy(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)
    void = await void_dose(session, user=user, dose_id=dose.id)
    assert void.dose_id == dose.id
    assert void.voided_by_user_id == user.id


async def test_void_dose_double_conflict(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)
    await void_dose(session, user=user, dose_id=dose.id)
    with pytest.raises(DoseAlreadyVoidedError):
        await void_dose(session, user=user, dose_id=dose.id)


async def test_void_dose_cross_user_forbidden(session: AsyncSession) -> None:
    owner = await make_user(session)
    intruder = await make_user(session)
    med = await make_medication(session, user=owner)
    dose = await make_dose(session, user=owner, medication=med)
    with pytest.raises(DoseForbiddenError):
        await void_dose(session, user=intruder, dose_id=dose.id)


async def test_void_dose_missing_404(session: AsyncSession) -> None:
    import uuid as _uuid

    user = await make_user(session)
    with pytest.raises(DoseNotFoundError):
        await void_dose(session, user=user, dose_id=_uuid.uuid4())


# Silence unused import — Dose / time are needed when extending tests.
_ = (Dose, time)
