"""Schema tests for ``dose_interaction_overrides`` (Phase 6)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import DoseInteractionOverride

from .factories import make_dose, make_medication, make_user


async def test_insert_override(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    dose = await make_dose(session, user=user, medication=b)
    row = DoseInteractionOverride(
        dose_id=dose.id, conflicting_medication_id=a.id
    )
    session.add(row)
    await session.flush()
    assert row.id is not None


async def test_unique_pair(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    dose = await make_dose(session, user=user, medication=b)
    session.add(
        DoseInteractionOverride(dose_id=dose.id, conflicting_medication_id=a.id)
    )
    await session.flush()
    session.add(
        DoseInteractionOverride(dose_id=dose.id, conflicting_medication_id=a.id)
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_dose_restrict_on_delete(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    dose = await make_dose(session, user=user, medication=b)
    session.add(
        DoseInteractionOverride(dose_id=dose.id, conflicting_medication_id=a.id)
    )
    await session.flush()
    await session.delete(dose)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_medication_restrict_on_delete(session: AsyncSession) -> None:
    user = await make_user(session)
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    dose = await make_dose(session, user=user, medication=b)
    session.add(
        DoseInteractionOverride(dose_id=dose.id, conflicting_medication_id=a.id)
    )
    await session.flush()
    await session.delete(a)
    with pytest.raises(IntegrityError):
        await session.flush()
