"""Tests for the ``dose_voids`` table (Phase 4)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .factories import (
    make_dose,
    make_dose_void,
    make_medication,
    make_user,
    utcnow,
)


async def test_round_trip_insert(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)
    void = await make_dose_void(session, dose=dose)
    assert void.id is not None
    assert void.dose_id == dose.id
    assert void.voided_by_user_id == user.id


async def test_dose_id_unique(session: AsyncSession) -> None:
    """A second void on the same dose violates the UNIQUE constraint."""
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)
    await make_dose_void(session, dose=dose)
    with pytest.raises(IntegrityError):
        await make_dose_void(session, dose=dose, voided_at=utcnow())


async def test_dose_restrict_on_delete(session: AsyncSession) -> None:
    """RESTRICT FK to ``doses.id`` prevents hard delete of a voided dose."""
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)
    await make_dose_void(session, dose=dose)
    await session.delete(dose)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_voider_restrict_on_delete(session: AsyncSession) -> None:
    """RESTRICT FK to ``users.id`` prevents hard delete of the voider."""
    voider = await make_user(session)
    owner = await make_user(session)
    med = await make_medication(session, user=owner)
    dose = await make_dose(session, user=owner, medication=med)
    await make_dose_void(session, dose=dose, voided_by=voider)
    await session.delete(voider)
    with pytest.raises(IntegrityError):
        await session.flush()
