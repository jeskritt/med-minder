"""Tests for the ``sessions`` table."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import SessionModel

from .factories import make_user, utcnow


async def test_insert_session(session: AsyncSession) -> None:
    user = await make_user(session)
    s = SessionModel(
        user_id=user.id,
        token_hash="a" * 64,
        expires_at=utcnow() + timedelta(hours=1),
    )
    session.add(s)
    await session.flush()
    assert s.id is not None


async def test_token_hash_unique(session: AsyncSession) -> None:
    user = await make_user(session)
    session.add(
        SessionModel(
            user_id=user.id,
            token_hash="dup",
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    await session.flush()
    session.add(
        SessionModel(
            user_id=user.id,
            token_hash="dup",
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_delete_cascades_sessions(session: AsyncSession) -> None:
    user = await make_user(session)
    session.add(
        SessionModel(
            user_id=user.id,
            token_hash="cascade",
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    await session.flush()

    await session.delete(user)
    await session.flush()

    rows = (
        (
            await session.execute(
                select(SessionModel).where(SessionModel.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_expired_session_remains_queryable(session: AsyncSession) -> None:
    user = await make_user(session)
    expired = SessionModel(
        user_id=user.id,
        token_hash="expired",
        expires_at=utcnow() - timedelta(hours=1),
    )
    session.add(expired)
    await session.flush()

    fetched = (
        await session.execute(
            select(SessionModel).where(SessionModel.token_hash == "expired")
        )
    ).scalar_one()
    assert fetched.expires_at < utcnow()
