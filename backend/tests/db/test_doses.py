"""Tests for the ``doses`` table (incl. cross-user-id trigger)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Dose

from .factories import make_medication, make_user, utcnow


async def test_insert_minimal(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = Dose(
        user_id=user.id,
        medication_id=med.id,
        taken_at=utcnow(),
        quantity=Decimal("1.000"),
    )
    session.add(dose)
    await session.flush()
    assert dose.id is not None


async def test_quantity_must_be_positive(session: AsyncSession) -> None:
    user = await make_user(session)
    med = await make_medication(session, user=user)
    bad = Dose(
        user_id=user.id,
        medication_id=med.id,
        taken_at=utcnow(),
        quantity=Decimal("0"),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_id_must_match_medication_user_id(
    session: AsyncSession,
) -> None:
    """D4: trigger fires on mismatched ``user_id``."""
    owner = await make_user(session)
    other = await make_user(session)
    med = await make_medication(session, user=owner)
    bad = Dose(
        user_id=other.id,
        medication_id=med.id,
        taken_at=utcnow(),
        quantity=Decimal("1"),
    )
    session.add(bad)
    # The trigger raises a generic Postgres exception which SQLAlchemy
    # surfaces as some DBAPIError subclass (InternalError, IntegrityError,
    # ...); DBAPIError is the common ancestor.
    with pytest.raises(DBAPIError):
        await session.flush()


async def test_medication_restrict_on_delete(session: AsyncSession) -> None:
    """D6: a dose blocks hard-delete of its medication."""
    user = await make_user(session)
    med = await make_medication(session, user=user)
    dose = Dose(
        user_id=user.id,
        medication_id=med.id,
        taken_at=utcnow(),
        quantity=Decimal("1"),
    )
    session.add(dose)
    await session.flush()
    await session.delete(med)
    with pytest.raises(IntegrityError):
        await session.flush()
