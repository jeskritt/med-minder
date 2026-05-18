"""Phase 6 integration tests for ``interaction_state`` on summary
endpoints (FR-011/FR-018/FR-019, SC-005)."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import MedicationInteraction, ScheduleMedication
from medminder.domain.users import create_user
from tests.db.factories import (
    make_dose,
    make_dose_void,
    make_medication,
    make_schedule,
)

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> None:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204
    client.cookies.set("mm_session", resp.cookies["mm_session"])


async def _pair(session: AsyncSession, email: str):
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


def _item(body: dict, med_id: str) -> dict:
    return next(i for i in body["items"] if i["id"] == med_id)


async def test_state_on_list_and_detail(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _pair(session, "s1@example.com")
    await make_dose(
        session,
        user=user,
        medication=a,
        taken_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    await session.flush()
    await _login(client, "s1@example.com")

    lst = (await client.get("/api/v1/medications")).json()
    b_item = _item(lst, str(b.id))
    assert b_item["interaction_state"] is not None
    assert (
        b_item["interaction_state"]["conflicts"][0][
            "conflicting_medication_name"
        ]
        == "Sumatriptan"
    )
    # A has no armed partner (B not dosed) → no state.
    assert _item(lst, str(a.id))["interaction_state"] is None

    detail = (await client.get(f"/api/v1/medications/{b.id}")).json()
    assert detail["interaction_state"] is not None
    assert detail["interaction_state"]["remaining_seconds"] >= 0


async def test_state_on_today(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _pair(session, "s2@example.com")
    today = datetime.now(UTC).date()
    sched = await make_schedule(
        session, user=user, label="AM", time_of_day=time(8, 0)
    )
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=b.id)
    )
    await make_dose(
        session,
        user=user,
        medication=a,
        taken_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    await session.flush()
    await _login(client, "s2@example.com")

    body = (
        await client.get(
            "/api/schedules/today",
            params={"timezone": "UTC", "date": today.isoformat()},
        )
    ).json()
    b_item = next(i for i in body["items"] if i["medication_id"] == str(b.id))
    assert b_item["interaction_state"] is not None


async def test_clears_when_arming_dose_voided(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _pair(session, "s3@example.com")
    armed = await make_dose(
        session,
        user=user,
        medication=a,
        taken_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    await make_dose_void(session, dose=armed, voided_by=user)
    await session.flush()
    await _login(client, "s3@example.com")

    lst = (await client.get("/api/v1/medications")).json()
    assert _item(lst, str(b.id))["interaction_state"] is None


async def test_clears_when_cooldown_elapsed(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _pair(session, "s4@example.com")
    await make_dose(
        session,
        user=user,
        medication=a,
        taken_at=datetime.now(UTC) - timedelta(minutes=200),
    )
    await session.flush()
    await _login(client, "s4@example.com")

    lst = (await client.get("/api/v1/medications")).json()
    assert _item(lst, str(b.id))["interaction_state"] is None


async def test_soft_deleted_partner_no_state(
    client: AsyncClient, session: AsyncSession
) -> None:
    user, a, b = await _pair(session, "s5@example.com")
    await make_dose(
        session,
        user=user,
        medication=a,
        taken_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    a.deleted_at = datetime.now(UTC)
    await session.flush()
    await _login(client, "s5@example.com")

    lst = (await client.get("/api/v1/medications")).json()
    # A is hidden (soft-deleted); B is present but unflagged (FR-018).
    assert all(i["id"] != str(a.id) for i in lst["items"])
    assert _item(lst, str(b.id))["interaction_state"] is None


async def test_cross_user_isolation(
    client: AsyncClient, session: AsyncSession
) -> None:
    """FR-019: one user's rules/doses never surface for another user."""
    u1, a, _b = await _pair(session, "owner@example.com")
    await make_dose(
        session,
        user=u1,
        medication=a,
        taken_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await create_user(
        session,
        email="other@example.com",
        name="Other",
        role="user",
        password=_PASSWORD,
    )
    await session.flush()
    await _login(client, "other@example.com")

    lst = (await client.get("/api/v1/medications")).json()
    # The second user owns nothing and sees no leaked rule/dose/state.
    assert lst["items"] == []
