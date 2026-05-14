"""Phase 5 integration tests for ``timer_state`` on today response."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication
from medminder.domain.users import create_user
from tests.db.factories import (
    make_dose,
    make_medication,
    make_schedule,
)

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)


async def test_count_up_in_today_response(
    client: AsyncClient, session: AsyncSession
) -> None:
    """count_up med surfaces elapsed_seconds; foreign + soft-deleted are hidden."""
    today = datetime.now(UTC).date()

    user = await create_user(
        session,
        email="molly@example.com",
        name="Molly",
        role="user",
        password=_PASSWORD,
        timezone_name="UTC",
    )
    foreign = await create_user(
        session,
        email="foreign@example.com",
        name="F",
        role="user",
        password=_PASSWORD,
    )

    med = await make_medication(
        session,
        user=user,
        name="Sumatriptan",
        timer_preference="count_up",
    )
    sched = await make_schedule(
        session, user=user, label="Morning", time_of_day=time(8, 0)
    )
    session.add(ScheduleMedication(schedule_id=sched.id, medication_id=med.id))

    taken_at = datetime.now(UTC) - timedelta(seconds=180)
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=taken_at,
    )

    # Foreign user's identical med — must NOT appear in primary's response.
    foreign_med = await make_medication(
        session,
        user=foreign,
        name="Sumatriptan",
        timer_preference="count_up",
    )
    foreign_sched = await make_schedule(session, user=foreign)
    session.add(
        ScheduleMedication(
            schedule_id=foreign_sched.id, medication_id=foreign_med.id
        )
    )
    await session.flush()

    await _login(client, "molly@example.com")
    resp = await client.get(
        "/api/schedules/today",
        params={"timezone": "UTC", "date": today.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["medication_id"] == str(med.id)

    timer = item["timer_state"]
    assert timer is not None
    assert timer["mode"] == "count_up"
    assert timer["last_dose_at"] is not None
    elapsed = timer["count_up"]["elapsed_seconds"]
    assert 175 <= elapsed <= 200, elapsed

    # Cross-user isolation gate (FR-014).
    assert all(
        i["medication_id"] != str(foreign_med.id) for i in body["items"]
    )


async def test_count_up_soft_deleted_excluded(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Soft-deleted count_up med must not appear in the today response."""
    today = datetime.now(UTC).date()

    user = await create_user(
        session,
        email="soft@example.com",
        name="Soft",
        role="user",
        password=_PASSWORD,
        timezone_name="UTC",
    )
    med = await make_medication(
        session,
        user=user,
        name="Sumatriptan",
        timer_preference="count_up",
    )
    sched = await make_schedule(session, user=user)
    session.add(ScheduleMedication(schedule_id=sched.id, medication_id=med.id))
    med.deleted_at = datetime.now(UTC)
    await session.flush()

    await _login(client, "soft@example.com")
    resp = await client.get(
        "/api/schedules/today",
        params={"timezone": "UTC", "date": today.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
