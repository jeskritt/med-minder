"""Tests for the ``medications`` table."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Medication
from medminder.db.models.medications import active

from .factories import make_medication, make_user, utcnow


async def test_insert_minimal(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    assert med.id is not None


async def test_quantity_per_dose_precision(session: AsyncSession) -> None:
    """D7: Numeric(10, 3) preserves 0.5 exactly."""
    user = await make_user(session)
    med = Medication(
        user_id=user.id,
        name="m",
        times_per_day=1,
        quantity_per_dose=Decimal("0.500"),
        unit="mg",
        timer_preference="none",
    )
    session.add(med)
    await session.flush()
    await session.refresh(med)
    assert med.quantity_per_dose == Decimal("0.500")


async def test_quantity_per_dose_must_be_positive(session: AsyncSession) -> None:
    user = await make_user(session)
    bad = Medication(
        user_id=user.id,
        name="m",
        times_per_day=1,
        quantity_per_dose=Decimal("0"),
        unit="mg",
        timer_preference="none",
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_count_down_requires_min_interval(session: AsyncSession) -> None:
    user = await make_user(session)
    bad = Medication(
        user_id=user.id,
        name="m",
        times_per_day=1,
        quantity_per_dose=Decimal("1"),
        unit="mg",
        timer_preference="count_down",
        min_interval_minutes=None,
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_multi_sub_dose_requires_window(session: AsyncSession) -> None:
    user = await make_user(session)
    bad = Medication(
        user_id=user.id,
        name="m",
        times_per_day=1,
        quantity_per_dose=Decimal("1"),
        unit="mg",
        timer_preference="multi_sub_dose",
        window_duration_minutes=None,
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_restrict_on_delete(session: AsyncSession) -> None:
    user = await make_user(session)
    await make_medication(session, user=user)
    await session.delete(user)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_active_helper_excludes_soft_deleted(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    alive = await make_medication(session, user=user)
    dead = await make_medication(session, user=user)
    dead.deleted_at = utcnow()
    await session.flush()
    rows = (await session.execute(active())).scalars().all()
    ids = {m.id for m in rows}
    assert alive.id in ids
    assert dead.id not in ids


async def test_times_per_day_independent_of_schedule_count(
    session: AsyncSession,
) -> None:
    """D1: ``times_per_day`` is a stored intent, not derived."""
    user = await make_user(session)
    med = Medication(
        user_id=user.id,
        name="m",
        times_per_day=3,
        quantity_per_dose=Decimal("1"),
        unit="mg",
        timer_preference="none",
    )
    session.add(med)
    await session.flush()
    await session.refresh(med)
    assert med.times_per_day == 3
    fetched = (
        await session.execute(
            select(Medication).where(Medication.id == med.id)
        )
    ).scalar_one()
    assert fetched.times_per_day == 3
