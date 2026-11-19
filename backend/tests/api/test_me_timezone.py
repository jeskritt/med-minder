"""Integration tests for ``PUT /me/timezone`` (self-service timezone)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import Reminder
from medminder.domain.users import create_user, get_user_by_email

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204, resp.text
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    return cookie


async def _signed_in(client: AsyncClient, session: AsyncSession, email: str) -> None:
    await create_user(
        session, email=email, name="TZ", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, email))


async def test_set_timezone_persists_and_echoes(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "tz-set@example.com")

    resp = await client.put("/me/timezone", json={"timezone": "America/Edmonton"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["timezone"] == "America/Edmonton"

    # Reflected on GET /me and stored on the row.
    me = (await client.get("/me")).json()
    assert me["timezone"] == "America/Edmonton"
    user = await get_user_by_email(session, email="tz-set@example.com")
    assert user is not None
    assert user.timezone == "America/Edmonton"


async def test_unknown_zone_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "tz-bad@example.com")
    resp = await client.put("/me/timezone", json={"timezone": "Mars/Phobos"})
    assert resp.status_code == 422
    # The row keeps its original (default UTC) zone.
    user = await get_user_by_email(session, email="tz-bad@example.com")
    assert user is not None
    assert user.timezone == "UTC"


async def test_empty_zone_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "tz-empty@example.com")
    resp = await client.put("/me/timezone", json={"timezone": ""})
    assert resp.status_code == 422


async def test_unauthenticated(client: AsyncClient) -> None:
    resp = await client.put("/me/timezone", json={"timezone": "America/Edmonton"})
    assert resp.status_code == 401


async def test_changing_timezone_regenerates_pending_dose_reminders(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Updating timezone moves future pending reminders and preserves past history."""
    await _signed_in(client, session, "tz-resync@example.com")
    user = await get_user_by_email(session, email="tz-resync@example.com")
    assert user is not None

    sched_resp = await client.post(
        "/api/v1/schedules",
        json={"time_of_day": "08:00", "label": "Morning", "days_of_week": 127},
    )
    assert sched_resp.status_code == 201, sched_resp.text
    sched_id = sched_resp.json()["id"]

    med_resp = await client.post(
        "/api/v1/medications",
        json={
            "name": "Vitamin D",
            "quantity_per_dose": "1",
            "unit": "capsule",
            "times_per_day": 1,
            "schedules": [sched_id],
        },
    )
    assert med_resp.status_code == 201, med_resp.text

    # Past sent reminder (history) must survive the timezone change untouched.
    past_sent = Reminder(
        user_id=user.id,
        type="dose",
        schedule_id=sched_id,
        scheduled_for=datetime.now(UTC) - timedelta(days=1),
        status="sent",
    )
    session.add(past_sent)
    await session.flush()

    async def _pending_hours() -> list[int]:
        rows = list(
            (
                await session.execute(
                    select(Reminder).where(
                        Reminder.schedule_id == sched_id,
                        Reminder.type == "dose",
                        Reminder.status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        return sorted({r.scheduled_for.astimezone(UTC).hour for r in rows})

    # Initially UTC → 08:00 local is 08:00 UTC.
    assert await _pending_hours() == [8]

    # Switch to America/Regina (permanent UTC-6) → 08:00 local is 14:00 UTC.
    # Old 08:00 UTC pending rows must be cancelled (no stale duplicates).
    resp = await client.put("/me/timezone", json={"timezone": "America/Regina"})
    assert resp.status_code == 200, resp.text
    assert await _pending_hours() == [14]

    await session.refresh(past_sent)
    assert past_sent.status == "sent"
