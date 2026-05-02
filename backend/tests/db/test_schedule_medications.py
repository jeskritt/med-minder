"""Tests for the ``schedule_medications`` association table."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication

from .factories import make_medication, make_schedule, make_user


async def test_insert(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    med = await make_medication(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await session.flush()


async def test_duplicate_pair_rejected(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    med = await make_medication(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await session.flush()
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_schedule_delete_cascades(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    med = await make_medication(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await session.flush()
    await session.delete(sched)
    await session.flush()
    rows = (
        await session.execute(
            select(ScheduleMedication).where(
                ScheduleMedication.medication_id == med.id
            )
        )
    ).all()
    assert rows == []


async def test_medication_delete_cascades(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    med = await make_medication(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await session.flush()
    await session.delete(med)
    await session.flush()
    rows = (
        await session.execute(
            select(ScheduleMedication).where(
                ScheduleMedication.schedule_id == sched.id
            )
        )
    ).all()
    assert rows == []
