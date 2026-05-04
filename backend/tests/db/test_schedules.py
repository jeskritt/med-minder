"""Tests for the ``schedules`` table."""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Schedule
from medminder.db.models.schedules import active

from .factories import make_schedule, make_user, utcnow


async def test_insert_minimal(session: AsyncSession) -> None:
    user = await make_user(session)
    sched = await make_schedule(session, user=user)
    assert sched.id is not None
    assert sched.days_of_week == 127


@pytest.mark.parametrize("days", [0, 1, 64, 127])
async def test_days_of_week_in_range(session: AsyncSession, days: int) -> None:
    user = await make_user(session)
    sched = Schedule(
        user_id=user.id,
        time_of_day=time(8, 0),
        days_of_week=days,
        label="L",
    )
    session.add(sched)
    await session.flush()


@pytest.mark.parametrize("days", [-1, 128, 200])
async def test_days_of_week_out_of_range(session: AsyncSession, days: int) -> None:
    user = await make_user(session)
    sched = Schedule(
        user_id=user.id,
        time_of_day=time(8, 0),
        days_of_week=days,
        label="L",
    )
    session.add(sched)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_restrict_on_delete(session: AsyncSession) -> None:
    user = await make_user(session)
    await make_schedule(session, user=user)
    await session.delete(user)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_active_excludes_soft_deleted(session: AsyncSession) -> None:
    user = await make_user(session)
    alive = await make_schedule(session, user=user)
    dead = await make_schedule(session, user=user)
    dead.deleted_at = utcnow()
    await session.flush()
    rows = (await session.execute(active())).scalars().all()
    ids = {s.id for s in rows}
    assert alive.id in ids
    assert dead.id not in ids
