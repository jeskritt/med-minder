"""Live refill supply + warning tests (Phase 7, T044, FR-013/014/014a)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Medication, Reminder, User
from medminder.domain.doses import create_dose, void_dose
from medminder.domain.reminder_dispatch import (
    clear_refill_reminder,
    ensure_refill_reminder,
)
from tests.db.factories import make_medication, make_user


async def _med_with_supply(
    session: AsyncSession,
    *,
    user: User,
    refill_count: int | None,
    refill_threshold: int | None = None,
) -> Medication:
    med = await make_medication(session, user=user)
    med.refill_count = refill_count
    med.refill_threshold = refill_threshold
    await session.flush()
    return med


async def _open_refill_count(session: AsyncSession, med_id: object) -> int:
    rows = list(
        (
            await session.execute(
                select(Reminder).where(
                    Reminder.medication_id == med_id,
                    Reminder.type == "refill",
                    Reminder.status != "dismissed",
                )
            )
        )
        .scalars()
        .all()
    )
    return len(rows)


async def test_take_decrements_count(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(session, user=user, refill_count=5)
    await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    await session.refresh(med)
    assert med.refill_count == 4


async def test_decrement_floors_at_zero(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(session, user=user, refill_count=0)
    await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    await session.refresh(med)
    assert med.refill_count == 0


async def test_untracked_count_unaffected(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(session, user=user, refill_count=None)
    await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    await session.refresh(med)
    assert med.refill_count is None


async def test_warns_on_threshold_crossing(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(
        session, user=user, refill_count=4, refill_threshold=3
    )
    await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    await session.refresh(med)
    assert med.refill_count == 3
    assert await _open_refill_count(session, med.id) == 1


async def test_no_duplicate_warning_while_low(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(
        session, user=user, refill_count=4, refill_threshold=3
    )
    for _ in range(3):  # 4→3 (warns), 3→2, 2→1
        await create_dose(
            session,
            user=user,
            medication_id=med.id,
            taken_at=datetime.now(UTC),
        )
    await session.refresh(med)
    assert med.refill_count == 1
    assert await _open_refill_count(session, med.id) == 1  # still just one


async def test_no_warning_without_threshold(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(
        session, user=user, refill_count=1, refill_threshold=None
    )
    await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    assert await _open_refill_count(session, med.id) == 0


async def test_void_restores_count(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(session, user=user, refill_count=5)
    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    await session.refresh(med)
    assert med.refill_count == 4
    await void_dose(session, user=user, dose_id=dose.id)
    await session.refresh(med)
    assert med.refill_count == 5


async def test_void_noop_when_untracked(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _med_with_supply(session, user=user, refill_count=None)
    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    await void_dose(session, user=user, dose_id=dose.id)
    await session.refresh(med)
    assert med.refill_count is None


async def test_ensure_is_deduped_and_clear_rearms(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    med = await _med_with_supply(
        session, user=user, refill_count=2, refill_threshold=3
    )
    await ensure_refill_reminder(session, user=user, medication=med)
    await ensure_refill_reminder(session, user=user, medication=med)
    assert await _open_refill_count(session, med.id) == 1  # deduped

    cleared = await clear_refill_reminder(session, medication=med)
    assert cleared == 1
    assert await _open_refill_count(session, med.id) == 0

    await ensure_refill_reminder(session, user=user, medication=med)
    assert await _open_refill_count(session, med.id) == 1  # re-armed
