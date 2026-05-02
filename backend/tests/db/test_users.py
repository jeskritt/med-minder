"""Tests for the ``users`` table."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import User
from medminder.db.models.users import active

from .factories import make_user, utcnow


async def test_insert_minimal(session: AsyncSession) -> None:
    user = await make_user(session)
    assert user.id is not None
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.deleted_at is None


@pytest.mark.parametrize(
    "field",
    ["email", "password_hash", "name", "role", "timezone"],
)
async def test_required_field_rejects_null(
    session: AsyncSession, field: str
) -> None:
    user = User(
        email="x@example.com",
        password_hash="h",
        name="n",
        role="user",
        timezone="UTC",
    )
    setattr(user, field, None)
    session.add(user)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_email_unique_case_insensitive(session: AsyncSession) -> None:
    """D8: ``LOWER(email)`` is the uniqueness key."""
    await make_user(session, email="Foo@Example.com")
    with pytest.raises(IntegrityError):
        await make_user(session, email="FOO@example.COM")


async def test_role_enum_rejects_unknown(session: AsyncSession) -> None:
    user = User(
        email="x@example.com",
        password_hash="h",
        name="n",
        role="nope",
        timezone="UTC",
    )
    session.add(user)
    with pytest.raises((IntegrityError, DataError)):
        await session.flush()


async def test_active_helper_excludes_soft_deleted(
    session: AsyncSession,
) -> None:
    alive = await make_user(session)
    dead = await make_user(session)
    dead.deleted_at = utcnow()
    await session.flush()

    rows = (await session.execute(active())).scalars().all()
    ids = {u.id for u in rows}
    assert alive.id in ids
    assert dead.id not in ids

    all_rows = (await session.execute(select(User))).scalars().all()
    assert {u.id for u in all_rows} >= {alive.id, dead.id}
