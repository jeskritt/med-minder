"""Domain tests for the multi_sub_dose window overdose guard in ``create_dose``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.doses import create_dose
from medminder.domain.timers import WindowFullError
from tests.db.factories import (
    make_dose,
    make_dose_void,
    make_medication,
    make_user,
)


async def _msd_med(session: AsyncSession, user, slots: int = 3):
    med = await make_medication(
        session,
        user=user,
        timer_preference="multi_sub_dose",
        window_duration_minutes=360,
    )
    med.times_per_day = slots
    await session.flush()
    return med


async def test_first_dose_opens_window(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _msd_med(session, user)
    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=datetime.now(UTC)
    )
    assert dose.medication_id == med.id


async def test_window_not_full_is_allowed(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _msd_med(session, user, slots=3)
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=med, taken_at=now - timedelta(minutes=30)
    )
    await make_dose(
        session, user=user, medication=med, taken_at=now - timedelta(minutes=10)
    )
    # 2 of 3 used → a 3rd is allowed.
    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=now
    )
    assert dose.medication_id == med.id


async def test_full_window_raises(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await _msd_med(session, user, slots=3)
    now = datetime.now(UTC)
    start = now - timedelta(minutes=60)
    for offset in (0, 10, 20):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=start + timedelta(minutes=offset),
        )

    with pytest.raises(WindowFullError) as exc_info:
        await create_dose(
            session, user=user, medication_id=med.id, taken_at=now
        )

    err = exc_info.value
    assert err.medication_id == med.id
    assert err.slots_used == 3
    assert err.slots_total == 3
    # Oldest active dose (at `start`) frees a slot when its window expires.
    assert err.next_available_at == start + timedelta(minutes=360)


async def test_voided_dose_does_not_count_toward_fullness(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    med = await _msd_med(session, user, slots=3)
    now = datetime.now(UTC)
    start = now - timedelta(minutes=60)
    d1 = await make_dose(session, user=user, medication=med, taken_at=start)
    await make_dose(
        session, user=user, medication=med, taken_at=start + timedelta(minutes=10)
    )
    await make_dose(
        session, user=user, medication=med, taken_at=start + timedelta(minutes=20)
    )
    # Void one → only 2 effective doses in the window → a new one fits.
    await make_dose_void(session, dose=d1, voided_by=user)

    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=now
    )
    assert dose.medication_id == med.id


async def test_dose_after_windows_expire_is_allowed(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    med = await _msd_med(session, user, slots=3)
    now = datetime.now(UTC)
    # Three doses ~8h ago: each per-dose 6h window has expired, so none
    # are active now.
    old = now - timedelta(hours=8)
    for offset in (0, 5, 10):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=old + timedelta(minutes=offset),
        )
    # No active sub-doses → a dose now is allowed.
    dose = await create_dose(
        session, user=user, medication_id=med.id, taken_at=now
    )
    assert dose.medication_id == med.id
