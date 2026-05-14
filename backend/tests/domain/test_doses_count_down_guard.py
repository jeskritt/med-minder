"""Domain tests for the count_down min-interval guard in ``create_dose``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.doses import create_dose
from medminder.domain.timers import MinIntervalNotElapsedError
from tests.db.factories import (
    make_dose,
    make_dose_void,
    make_medication,
    make_user,
)


async def test_count_down_first_dose_is_allowed(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(
        session,
        user=user,
        timer_preference="count_down",
        min_interval_minutes=60,
    )

    dose = await create_dose(
        session,
        user=user,
        medication_id=med.id,
        taken_at=datetime.now(UTC),
    )
    assert dose.medication_id == med.id


async def test_count_down_inside_interval_raises(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(
        session,
        user=user,
        timer_preference="count_down",
        min_interval_minutes=60,
    )

    now = datetime.now(UTC)
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=now - timedelta(minutes=10),
    )

    with pytest.raises(MinIntervalNotElapsedError) as exc_info:
        await create_dose(
            session,
            user=user,
            medication_id=med.id,
            taken_at=now,
        )

    err = exc_info.value
    assert err.medication_id == med.id
    assert err.remaining_seconds >= 1
    # ~50 minutes remaining = 3000s; allow for test latency
    assert 2950 <= err.remaining_seconds <= 3000


async def test_count_down_voided_previous_does_not_block(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    med = await make_medication(
        session,
        user=user,
        timer_preference="count_down",
        min_interval_minutes=60,
    )

    now = datetime.now(UTC)
    voided_dose = await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=now - timedelta(minutes=10),
    )
    await make_dose_void(session, dose=voided_dose, voided_by=user)

    # No exception expected — the only previous dose is voided.
    dose = await create_dose(
        session,
        user=user,
        medication_id=med.id,
        taken_at=now,
    )
    assert dose.medication_id == med.id
