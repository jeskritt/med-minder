"""API integration tests for the count_down min-interval guard (FR-005/FR-006)."""

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


async def test_count_down_first_dose_201(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="harry-first@example.com",
        name="Harry",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Ibuprofen",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    await session.flush()

    await _login(client, "harry-first@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(med.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text


async def test_count_down_too_soon_returns_409_with_violation_body(
    client: AsyncClient, session: AsyncSession
) -> None:
    """FR-005: 409 with structured MinIntervalViolation body."""
    user = await create_user(
        session,
        email="harry-409@example.com",
        name="Harry",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Ibuprofen",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    await session.flush()

    await _login(client, "harry-409@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(med.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "code",
        "medication_id",
        "next_allowed_at",
        "remaining_seconds",
    }
    assert body["code"] == "min_interval_not_elapsed"
    assert body["medication_id"] == str(med.id)
    assert body["remaining_seconds"] >= 1
    # ~50 minutes remaining
    assert 2950 <= body["remaining_seconds"] <= 3000


async def test_count_down_direct_api_call_still_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    """FR-006: 409 holds against direct API calls (no FE involvement).

    The test client does not go through ``useTakeDose`` — it's an
    ``httpx.AsyncClient`` POST. Same 409 must come back.
    """
    user = await create_user(
        session,
        email="harry-direct@example.com",
        name="Harry",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Ibuprofen",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await session.flush()

    await _login(client, "harry-direct@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(med.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "min_interval_not_elapsed"
