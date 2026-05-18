"""Domain tests for the Phase 6 interaction guard in ``create_dose``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import (
    Dose,
    DoseInteractionOverride,
    MedicationInteraction,
)
from medminder.domain.doses import create_dose
from medminder.domain.interactions import MedicationInteractionConflictError
from medminder.domain.timers import MinIntervalNotElapsedError
from tests.db.factories import (
    make_dose,
    make_dose_void,
    make_medication,
    make_user,
)


async def _rule(
    session: AsyncSession, a_id, b_id, cooldown_minutes: int = 120
) -> None:
    session.add(
        MedicationInteraction(
            medication_id=a_id,
            conflicting_medication_id=b_id,
            cooldown_minutes=cooldown_minutes,
        )
    )
    await session.flush()


async def _count_doses(session: AsyncSession, medication_id) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Dose)
            .where(Dose.medication_id == medication_id)
        )
    ).scalar_one()


async def test_no_rule_records_normally(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user, name="Lonely")
    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    assert dose.medication_id == med.id


async def test_unacknowledged_conflict_raises_and_writes_no_dose(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    await _rule(session, a.id, b.id, 120)
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=10)
    )

    with pytest.raises(MedicationInteractionConflictError) as exc:
        await create_dose(
            session, user=user, medication_id=b.id, taken_at=now
        )
    assert exc.value.medication_id == b.id
    assert exc.value.conflict.conflicts[0].conflicting_medication_id == a.id
    assert await _count_doses(session, b.id) == 0


async def test_acknowledged_records_dose_and_override(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    await _rule(session, a.id, b.id, 120)
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=10)
    )

    dose = await create_dose(
        session,
        user=user,
        medication_id=b.id,
        taken_at=now,
        interaction_acknowledged=True,
    )
    assert dose.medication_id == b.id
    overrides = (
        (
            await session.execute(
                select(DoseInteractionOverride).where(
                    DoseInteractionOverride.dose_id == dose.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(overrides) == 1
    assert overrides[0].conflicting_medication_id == a.id


async def test_voided_arming_dose_does_not_conflict(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    await _rule(session, a.id, b.id, 120)
    now = datetime.now(UTC)
    armed = await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=10)
    )
    await make_dose_void(session, dose=armed, voided_by=user)

    dose = await create_dose(
        session, user=user, medication_id=b.id, taken_at=now
    )
    assert dose.medication_id == b.id


async def test_expired_cooldown_records_normally(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    await _rule(session, a.id, b.id, 120)
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=200)
    )
    dose = await create_dose(
        session, user=user, medication_id=b.id, taken_at=now
    )
    assert dose.medication_id == b.id


async def test_soft_deleted_partner_does_not_conflict(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    await _rule(session, a.id, b.id, 120)
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=5)
    )
    a.deleted_at = now
    await session.flush()

    dose = await create_dose(
        session, user=user, medication_id=b.id, taken_at=now
    )
    assert dose.medication_id == b.id


async def test_phase5_overdose_guard_still_wins_with_ack(
    session: AsyncSession,
) -> None:
    """FR-010: an interaction ack never defeats a non-overridable
    count_down overdose 409."""
    user = await make_user(session)
    a = await make_medication(
        session,
        user=user,
        name="A",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    b = await make_medication(session, user=user, name="B")
    await _rule(session, a.id, b.id, 120)
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=10)
    )

    # Re-dosing A within its min-interval, even with the interaction
    # acknowledgment set, must still raise the overdose error.
    with pytest.raises(MinIntervalNotElapsedError):
        await create_dose(
            session,
            user=user,
            medication_id=a.id,
            taken_at=now,
            interaction_acknowledged=True,
        )
