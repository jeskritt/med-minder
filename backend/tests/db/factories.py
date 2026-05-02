"""Tiny test factories.

These exist to keep individual test bodies focused on the constraint
under test rather than on plausible field values.  Each factory returns
a *persisted* row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import (
    Medication,
    Schedule,
    User,
)


async def make_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    name: str = "Test User",
    role: str = "user",
    timezone_name: str = "UTC",
) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$test$test",
        name=name,
        role=role,
        timezone=timezone_name,
    )
    session.add(user)
    await session.flush()
    return user


async def make_medication(
    session: AsyncSession,
    *,
    user: User,
    name: str = "Test Med",
    timer_preference: str = "none",
    min_interval_minutes: int | None = None,
    window_duration_minutes: int | None = None,
) -> Medication:
    med = Medication(
        user_id=user.id,
        name=name,
        times_per_day=1,
        quantity_per_dose=Decimal("1.000"),
        unit="mg",
        timer_preference=timer_preference,
        min_interval_minutes=min_interval_minutes,
        window_duration_minutes=window_duration_minutes,
    )
    session.add(med)
    await session.flush()
    return med


async def make_schedule(
    session: AsyncSession,
    *,
    user: User,
    label: str = "Morning",
    time_of_day: time = time(8, 0),
    days_of_week: int = 127,
) -> Schedule:
    sched = Schedule(
        user_id=user.id,
        time_of_day=time_of_day,
        days_of_week=days_of_week,
        label=label,
    )
    session.add(sched)
    await session.flush()
    return sched


def utcnow() -> datetime:
    return datetime.now(UTC)
