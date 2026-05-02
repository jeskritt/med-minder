"""Tests for ``medication_interactions``."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import MedicationInteraction

from .factories import make_medication, make_user


async def test_insert_pair(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    inter = MedicationInteraction(
        medication_id=a.id, conflicting_medication_id=b.id, cooldown_minutes=120
    )
    session.add(inter)
    await session.flush()
    assert inter.id is not None


async def test_distinct_medications(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    bad = MedicationInteraction(
        medication_id=a.id, conflicting_medication_id=a.id, cooldown_minutes=10
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_cooldown_must_be_positive(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    bad = MedicationInteraction(
        medication_id=a.id, conflicting_medication_id=b.id, cooldown_minutes=0
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_unordered_pair_unique(session: AsyncSession) -> None:
    """D5: ``(A, B)`` and ``(B, A)`` are treated as the same pair."""
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    session.add(
        MedicationInteraction(
            medication_id=a.id,
            conflicting_medication_id=b.id,
            cooldown_minutes=120,
        )
    )
    await session.flush()
    session.add(
        MedicationInteraction(
            medication_id=b.id,
            conflicting_medication_id=a.id,
            cooldown_minutes=60,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_medication_restrict_on_delete(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    session.add(
        MedicationInteraction(
            medication_id=a.id,
            conflicting_medication_id=b.id,
            cooldown_minutes=120,
        )
    )
    await session.flush()
    await session.delete(a)
    with pytest.raises(IntegrityError):
        await session.flush()
