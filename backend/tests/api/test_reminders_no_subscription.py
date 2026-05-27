"""In-app fallback without push (Phase 7, T051, FR-008/US6).

A user who never registered a push subscription still sees due reminders
in-app — push is best-effort, not the only channel.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import PushSubscription, Reminder, User
from medminder.domain.users import create_user
from medminder.settings import Settings
from tests.db.factories import make_schedule

_SECRET = "test-only-stable-secret-for-itsdangerous-signing-12345"
_PW = "correct horse battery staple"


@pytest_asyncio.fixture
async def app_settings() -> Settings:
    return Settings(env="development", session_secret=_SECRET)


async def _login(client: AsyncClient, session: AsyncSession, *, email: str) -> User:
    await create_user(
        session, email=email, name="T", role="user", password=_PW
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PW}
    )
    assert resp.status_code == 204
    client.cookies.set("mm_session", resp.cookies.get("mm_session") or "")
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one()


async def test_reminders_listed_without_any_subscription(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login(client, session, email="no-sub@example.com")
    sched = await make_schedule(session, user=user)
    session.add(
        Reminder(
            user_id=user.id,
            type="dose",
            schedule_id=sched.id,
            scheduled_for=datetime.now(UTC),
            status="pending",
        )
    )
    await session.flush()

    # Sanity: the user has no push subscription at all.
    sub_count = (
        await session.execute(
            select(func.count())
            .select_from(PushSubscription)
            .where(PushSubscription.user_id == user.id)
        )
    ).scalar_one()
    assert sub_count == 0

    resp = await client.get("/api/v1/reminders")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
