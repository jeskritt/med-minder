"""API integration tests for the multi_sub_dose per-day cap guard.

Sibling of ``test_doses_multi_sub_dose_guard.py``: enforces the
additional ``max_doses_per_day`` threshold on top of the per-window
slot cap. Per ADR-0008 this is a non-overridable overdose 409.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user
from tests.db.factories import make_dose, make_medication

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


async def test_daily_cap_under_limit_201(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Under cap: per-window has room (3/4) AND daily count under max."""
    user = await create_user(
        session,
        email="cap-under@example.com",
        name="Cap Under",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Naproxen",
        timer_preference="multi_sub_dose",
        window_duration_minutes=60,
    )
    med.times_per_day = 4
    med.max_doses_per_day = 4
    await session.flush()

    # Three existing doses clustered in the last 30 min — same UTC day as
    # "now", same 60-min window. The prospective dose will be the 4th
    # in the window (slots: 4, OK) and the 4th today (cap: 4, OK).
    now = datetime.now(UTC)
    for offset_min in (30, 20, 10):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=now - timedelta(minutes=offset_min),
        )
    await session.flush()

    await _login(client, "cap-under@example.com")
    resp = await client.post(
        "/api/doses", json={"medication_id": str(med.id)}
    )
    assert resp.status_code == 201, resp.text


async def test_daily_cap_at_limit_returns_409_with_violation_body(
    client: AsyncClient, session: AsyncSession
) -> None:
    """At cap: per-window still has room, but daily cap is reached."""
    user = await create_user(
        session,
        email="cap-full@example.com",
        name="Cap Full",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Naproxen",
        timer_preference="multi_sub_dose",
        window_duration_minutes=60,
    )
    med.times_per_day = 4
    med.max_doses_per_day = 3
    await session.flush()

    # Same clustering as the happy-path test, but with max_per_day=3.
    # Per-window: 3 of 4 slots used — has room. Daily cap: 3 of 3 — full.
    now = datetime.now(UTC)
    for offset_min in (30, 20, 10):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=now - timedelta(minutes=offset_min),
        )
    await session.flush()

    await _login(client, "cap-full@example.com")
    resp = await client.post(
        "/api/doses", json={"medication_id": str(med.id)}
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "code",
        "medication_id",
        "max_per_day",
        "count_today",
    }
    assert body["code"] == "daily_cap_reached"
    assert body["medication_id"] == str(med.id)
    assert body["max_per_day"] == 3
    assert body["count_today"] == 3
