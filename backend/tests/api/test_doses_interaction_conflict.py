"""API integration tests for the Phase 6 interaction conflict (FR-005/SC-001).

These POST ``/api/doses`` directly via ``httpx.AsyncClient`` — no
frontend, no ``useTakeDose`` — proving the warn/override is
server-authoritative and not silently bypassable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import (
    Dose,
    DoseInteractionOverride,
    MedicationInteraction,
)
from medminder.domain.users import create_user
from tests.db.factories import make_dose, make_medication

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> None:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)


async def _setup(session: AsyncSession, email: str):
    user = await create_user(
        session, email=email, name="Molly", role="user", password=_PASSWORD
    )
    a = await make_medication(session, user=user, name="Sumatriptan")
    b = await make_medication(session, user=user, name="Ibuprofen")
    session.add(
        MedicationInteraction(
            medication_id=a.id,
            conflicting_medication_id=b.id,
            cooldown_minutes=120,
        )
    )
    await session.flush()
    return user, a, b


async def test_unacknowledged_conflict_409_no_dose_written(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _setup(session, "molly-409@example.com")
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=10)
    )
    await session.flush()

    await _login(client, "molly-409@example.com")
    resp = await client.post(
        "/api/doses",
        json={"medication_id": str(b.id), "taken_at": now.isoformat()},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "code",
        "medication_id",
        "conflicts",
        "cooldown_elapses_at",
        "remaining_seconds",
    }
    assert body["code"] == "interaction_cooldown_active"
    assert body["medication_id"] == str(b.id)
    assert body["conflicts"][0]["conflicting_medication_id"] == str(a.id)
    assert body["conflicts"][0]["conflicting_medication_name"] == "Sumatriptan"
    assert body["remaining_seconds"] >= 0

    n = (
        await session.execute(
            select(func.count())
            .select_from(Dose)
            .where(Dose.medication_id == b.id)
        )
    ).scalar_one()
    assert n == 0


async def test_acknowledged_retry_records_dose_and_override(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _setup(session, "molly-ack@example.com")
    now = datetime.now(UTC)
    await make_dose(
        session, user=user, medication=a, taken_at=now - timedelta(minutes=10)
    )
    await session.flush()

    await _login(client, "molly-ack@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(b.id),
            "taken_at": now.isoformat(),
            "interaction_acknowledged": True,
        },
    )
    assert resp.status_code == 201, resp.text

    overrides = (
        (
            await session.execute(
                select(DoseInteractionOverride).where(
                    DoseInteractionOverride.conflicting_medication_id == a.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(overrides) == 1


async def test_first_dose_of_pair_201(
    client: AsyncClient, session: AsyncSession
) -> None:
    _user, a, _b = await _setup(session, "molly-first@example.com")
    await session.flush()
    await _login(client, "molly-first@example.com")
    resp = await client.post(
        "/api/doses",
        json={
            "medication_id": str(a.id),
            "taken_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
