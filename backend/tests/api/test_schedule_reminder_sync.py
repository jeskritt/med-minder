"""Schedule-mutation → reminder resync tests (Phase 7, T040, FR-012/SC-005)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Reminder, User
from medminder.domain.users import create_user
from medminder.settings import Settings

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


async def _make_schedule(client: AsyncClient, *, time_of_day: str) -> str:
    resp = await client.post(
        "/api/v1/schedules", json={"time_of_day": time_of_day, "label": "Slot"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _make_med(client: AsyncClient, *, schedule_ids: list[str]) -> str:
    resp = await client.post(
        "/api/v1/medications",
        json={
            "name": "Aspirin",
            "quantity_per_dose": "100",
            "unit": "mg",
            "times_per_day": 1,
            "schedules": schedule_ids,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _pending_dose_hours(
    session: AsyncSession, schedule_id: str
) -> list[int]:
    rows = list(
        (
            await session.execute(
                select(Reminder).where(
                    Reminder.schedule_id == schedule_id,
                    Reminder.type == "dose",
                    Reminder.status == "pending",
                )
            )
        )
        .scalars()
        .all()
    )
    return sorted({r.scheduled_for.astimezone(UTC).hour for r in rows})


async def test_creating_med_generates_reminders(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sync-create@example.com")
    sched_id = await _make_schedule(client, time_of_day="08:00")
    # No med yet → no reminders.
    assert await _pending_dose_hours(session, sched_id) == []
    await _make_med(client, schedule_ids=[sched_id])
    # Now generated, all at 08:00 UTC.
    assert await _pending_dose_hours(session, sched_id) == [8]


async def test_editing_schedule_time_moves_reminders(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login(client, session, email="sync-edit@example.com")
    sched_id = await _make_schedule(client, time_of_day="08:00")
    await _make_med(client, schedule_ids=[sched_id])
    assert await _pending_dose_hours(session, sched_id) == [8]

    resp = await client.put(
        f"/api/v1/schedules/{sched_id}",
        json={"time_of_day": "09:00", "label": "Slot", "days_of_week": 127},
    )
    assert resp.status_code == 200, resp.text
    # Old 08:00 pending reminders gone; now all at 09:00.
    assert await _pending_dose_hours(session, sched_id) == [9]
    assert user.timezone == "UTC"


async def test_deleting_schedule_cancels_reminders(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sync-del@example.com")
    sched_id = await _make_schedule(client, time_of_day="08:00")
    await _make_med(client, schedule_ids=[sched_id])
    assert await _pending_dose_hours(session, sched_id) == [8]

    resp = await client.delete(f"/api/v1/schedules/{sched_id}")
    assert resp.status_code == 204
    assert await _pending_dose_hours(session, sched_id) == []


async def test_detaching_med_cancels_reminders(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sync-detach@example.com")
    sched_id = await _make_schedule(client, time_of_day="08:00")
    med_id = await _make_med(client, schedule_ids=[sched_id])
    assert await _pending_dose_hours(session, sched_id) == [8]

    # Detach the only med → schedule has no live med → reminders cancelled.
    resp = await client.put(
        f"/api/v1/medications/{med_id}",
        json={
            "name": "Aspirin",
            "quantity_per_dose": "100",
            "unit": "mg",
            "times_per_day": 1,
            "schedules": [],
        },
    )
    assert resp.status_code == 200, resp.text
    assert await _pending_dose_hours(session, sched_id) == []


async def test_past_sent_reminders_preserved_on_edit(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _login(client, session, email="sync-history@example.com")
    sched_id = await _make_schedule(client, time_of_day="08:00")
    await _make_med(client, schedule_ids=[sched_id])

    # A past, already-sent reminder for this schedule (history).
    past_sent = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched_id,
        scheduled_for=datetime.now(UTC) - timedelta(days=1),
        status="sent",
    )
    session.add(past_sent)
    await session.flush()

    resp = await client.put(
        f"/api/v1/schedules/{sched_id}",
        json={"time_of_day": "09:00", "label": "Slot", "days_of_week": 127},
    )
    assert resp.status_code == 200, resp.text
    await session.refresh(past_sent)
    assert past_sent.status == "sent"  # history untouched
