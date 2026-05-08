"""Contract tests for ``POST /api/doses``."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication
from medminder.domain.users import create_user
from tests.db.factories import make_medication, make_schedule

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


async def test_create_dose_201(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="user1@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await session.flush()

    await _login(client, "user1@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(med.id),
            "schedule_id": str(sched.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["medication_id"] == str(med.id)
    assert body["schedule_id"] == str(sched.id)
    assert "id" in body
    assert "taken_at" in body
    assert "created_at" in body


async def test_create_dose_403_cross_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await create_user(
        session, email="owner@example.com", name="O", role="user", password=_PASSWORD
    )
    intruder = await create_user(
        session, email="intruder@example.com", name="I", role="user", password=_PASSWORD
    )
    _ = intruder
    med = await make_medication(session, user=owner)

    await _login(client, "intruder@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(med.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 403


async def test_create_dose_422_unlinked_schedule(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="u422@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)  # no link

    await _login(client, "u422@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(med.id),
            "schedule_id": str(sched.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 422


async def test_create_dose_401_unauthenticated(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(uuid.uuid4()),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 401
