"""API integration tests for the multi_sub_dose window overdose guard.

Parity with the count_down guard (FR-005/FR-006): the rejection holds
against a direct API call that bypasses the disabled-when-full UI.
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


async def test_multi_sub_dose_within_slots_201(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="billy-msd-ok@example.com",
        name="Billy",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Tylenol 3",
        timer_preference="multi_sub_dose",
        window_duration_minutes=360,
    )
    med.times_per_day = 3
    await session.flush()

    await _login(client, "billy-msd-ok@example.com")
    for _ in range(3):
        resp = await client.post(
            "/api/doses", json={"medication_id": str(med.id)}
        )
        assert resp.status_code == 201, resp.text


async def test_multi_sub_dose_window_full_returns_409_with_violation_body(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="billy-msd-409@example.com",
        name="Billy",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Tylenol 3",
        timer_preference="multi_sub_dose",
        window_duration_minutes=360,
    )
    med.times_per_day = 3
    start = datetime.now(UTC) - timedelta(minutes=30)
    for offset in (0, 5, 10):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=start + timedelta(minutes=offset),
        )
    await session.flush()

    await _login(client, "billy-msd-409@example.com")
    # Direct API call bypassing the disabled-when-full UI → must 409.
    resp = await client.post(
        "/api/doses", json={"medication_id": str(med.id)}
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "code",
        "medication_id",
        "next_available_at",
        "slots_used",
        "slots_total",
    }
    assert body["code"] == "window_full"
    assert body["medication_id"] == str(med.id)
    assert body["slots_used"] == 3
    assert body["slots_total"] == 3
