"""Snooze / dismiss API tests (Phase 7, T031)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Reminder, User
from medminder.domain.users import create_user
from medminder.settings import Settings
from tests.db.factories import make_schedule

_SECRET = "test-only-stable-secret-for-itsdangerous-signing-12345"
_PW = "correct horse battery staple"


@pytest_asyncio.fixture
async def app_settings() -> Settings:
    return Settings(env="development", session_secret=_SECRET)


async def _login_user(
    client: AsyncClient, session: AsyncSession, *, email: str
) -> User:
    await create_user(
        session, email=email, name="T", role="user", password=_PW
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PW}
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one()


async def _make_reminder(session: AsyncSession, *, user: User) -> Reminder:
    sched = await make_schedule(session, user=user)
    rem = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched.id,
        scheduled_for=datetime.now(UTC),
        status="pending",
    )
    session.add(rem)
    await session.flush()
    return rem


async def test_snooze_returns_next_reminder(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login_user(client, session, email="snooze@example.com")
    rem = await _make_reminder(session, user=user)
    resp = await client.post(f"/api/v1/reminders/{rem.id}/snooze")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["id"] != str(rem.id)
    assert body["overdue"] is False


async def test_dismiss_removes_from_list(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login_user(client, session, email="dismiss@example.com")
    rem = await _make_reminder(session, user=user)
    resp = await client.post(f"/api/v1/reminders/{rem.id}/dismiss")
    assert resp.status_code == 204
    listed = await client.get("/api/v1/reminders")
    assert all(item["id"] != str(rem.id) for item in listed.json()["items"])


async def test_snooze_unknown_id_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_user(client, session, email="snooze404@example.com")
    resp = await client.post(f"/api/v1/reminders/{uuid.uuid4()}/snooze")
    assert resp.status_code == 404


async def test_cross_user_snooze_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await _login_user(client, session, email="owner-act@example.com")
    rem = await _make_reminder(session, user=owner)
    await client.post("/auth/logout")
    client.cookies.clear()
    await _login_user(client, session, email="intruder-act@example.com")
    resp = await client.post(f"/api/v1/reminders/{rem.id}/snooze")
    assert resp.status_code == 404


async def test_unauthenticated_is_401(client: AsyncClient) -> None:
    resp = await client.post(f"/api/v1/reminders/{uuid.uuid4()}/dismiss")
    assert resp.status_code == 401
