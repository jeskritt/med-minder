"""In-app reminders list API tests (Phase 7, T013)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Reminder, ScheduleMedication, User
from medminder.domain.users import create_user
from medminder.settings import Settings
from tests.db.factories import make_medication, make_schedule

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


async def test_list_returns_dose_reminder_with_title(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login_user(client, session, email="rem@example.com")
    sched = await make_schedule(session, user=user, label="Morning")
    med = await make_medication(session, user=user, name="Aspirin")
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
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

    resp = await client.get("/api/v1/reminders")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "dose"
    assert items[0]["status"] == "pending"
    assert "Aspirin" in items[0]["title"]
    assert items[0]["overdue"] is False


async def test_list_excludes_dismissed(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login_user(client, session, email="rem-dismiss@example.com")
    sched = await make_schedule(session, user=user)
    session.add(
        Reminder(
            user_id=user.id,
            type="dose",
            schedule_id=sched.id,
            scheduled_for=datetime.now(UTC),
            status="dismissed",
        )
    )
    await session.flush()
    resp = await client.get("/api/v1/reminders")
    assert resp.json()["items"] == []


async def test_overdue_flag_set_when_past_grace(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login_user(client, session, email="rem-overdue@example.com")
    sched = await make_schedule(session, user=user)
    session.add(
        Reminder(
            user_id=user.id,
            type="dose",
            schedule_id=sched.id,
            scheduled_for=datetime.now(UTC) - timedelta(hours=2),
            status="pending",
        )
    )
    await session.flush()
    items = (await client.get("/api/v1/reminders")).json()["items"]
    assert items[0]["overdue"] is True


async def test_unauthenticated_is_401(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/reminders")).status_code == 401


async def test_cross_user_isolation(
    client: AsyncClient, session: AsyncSession
) -> None:
    alice = await _login_user(client, session, email="alice-rem@example.com")
    sched = await make_schedule(session, user=alice)
    session.add(
        Reminder(
            user_id=alice.id,
            type="dose",
            schedule_id=sched.id,
            scheduled_for=datetime.now(UTC),
            status="pending",
        )
    )
    await session.flush()

    await client.post("/auth/logout")
    client.cookies.clear()
    await _login_user(client, session, email="bob-rem@example.com")
    assert (await client.get("/api/v1/reminders")).json()["items"] == []
