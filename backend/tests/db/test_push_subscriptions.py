"""Tests for the ``push_subscriptions`` table."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import PushSubscription

from .factories import make_user


async def test_insert_subscription(session: AsyncSession) -> None:
    user = await make_user(session)
    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://push.example/abc",
        p256dh="p256",
        auth="auth",
    )
    session.add(sub)
    await session.flush()
    assert sub.id is not None


async def test_unique_user_endpoint(session: AsyncSession) -> None:
    """D10: UNIQUE on ``(user_id, endpoint)`` prevents duplicate subs."""
    user = await make_user(session)
    session.add(
        PushSubscription(
            user_id=user.id,
            endpoint="https://push.example/abc",
            p256dh="p1",
            auth="a1",
        )
    )
    await session.flush()
    session.add(
        PushSubscription(
            user_id=user.id,
            endpoint="https://push.example/abc",
            p256dh="p2",
            auth="a2",
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_same_endpoint_different_users_ok(session: AsyncSession) -> None:
    user_a = await make_user(session)
    user_b = await make_user(session)
    session.add_all(
        [
            PushSubscription(
                user_id=user_a.id,
                endpoint="https://push.example/x",
                p256dh="p",
                auth="a",
            ),
            PushSubscription(
                user_id=user_b.id,
                endpoint="https://push.example/x",
                p256dh="p",
                auth="a",
            ),
        ]
    )
    await session.flush()


async def test_user_delete_cascades(session: AsyncSession) -> None:
    user = await make_user(session)
    session.add(
        PushSubscription(
            user_id=user.id,
            endpoint="https://push.example/y",
            p256dh="p",
            auth="a",
        )
    )
    await session.flush()
    await session.delete(user)
    await session.flush()
    rows = (
        await session.execute(
            select(PushSubscription).where(PushSubscription.user_id == user.id)
        )
    ).all()
    assert rows == []
