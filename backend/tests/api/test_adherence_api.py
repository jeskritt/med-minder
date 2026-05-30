"""Contract tests for ``GET /api/v1/adherence/medications/{id}``."""

from __future__ import annotations

from datetime import UTC, datetime, time

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication, User
from medminder.domain.users import create_user
from tests.api.conftest import FIXTURE_PASSWORD, login_as
from tests.db.factories import make_dose, make_medication, make_schedule

_BASE = "/api/v1/adherence/medications"


async def _user(session: AsyncSession, email: str) -> User:
    return await create_user(
        session,
        email=email,
        name="U",
        role="user",
        password=FIXTURE_PASSWORD,
        timezone_name="UTC",
    )


async def test_401_unauthenticated(client: AsyncClient, session: AsyncSession) -> None:
    user = await _user(session, "an1@example.com")
    med = await make_medication(session, user=user)
    await session.flush()
    resp = await client.get(
        f"{_BASE}/{med.id}", params={"from": "2026-05-01", "to": "2026-05-31"}
    )
    assert resp.status_code == 401


async def test_404_other_users_medication(
    client: AsyncClient, session: AsyncSession
) -> None:
    me = await _user(session, "me1@example.com")  # noqa: F841
    other = await _user(session, "other1@example.com")
    other_med = await make_medication(session, user=other)
    await session.flush()

    await login_as(client, "me1@example.com")
    resp = await client.get(
        f"{_BASE}/{other_med.id}",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert resp.status_code == 404


async def test_422_inverted_range(client: AsyncClient, session: AsyncSession) -> None:
    user = await _user(session, "inv@example.com")
    med = await make_medication(session, user=user)
    await session.flush()
    await login_as(client, "inv@example.com")
    resp = await client.get(
        f"{_BASE}/{med.id}", params={"from": "2026-05-31", "to": "2026-05-01"}
    )
    assert resp.status_code == 422


async def test_422_over_cap_range(client: AsyncClient, session: AsyncSession) -> None:
    user = await _user(session, "cap@example.com")
    med = await make_medication(session, user=user)
    await session.flush()
    await login_as(client, "cap@example.com")
    resp = await client.get(
        f"{_BASE}/{med.id}", params={"from": "2024-01-01", "to": "2026-01-01"}
    )
    assert resp.status_code == 422


async def test_400_unknown_timezone(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "tz@example.com")
    med = await make_medication(session, user=user)
    await session.flush()
    await login_as(client, "tz@example.com")
    resp = await client.get(
        f"{_BASE}/{med.id}",
        params={"from": "2026-05-01", "to": "2026-05-02", "timezone": "Nowhere/Nope"},
    )
    assert resp.status_code == 400


async def test_scheduled_med_returns_days_pct_and_aliases(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "sch@example.com")
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user, time_of_day=time(8, 0))
    session.add(ScheduleMedication(schedule_id=sched.id, medication_id=med.id))
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 8, 5, tzinfo=UTC),
    )
    await session.flush()

    await login_as(client, "sch@example.com")
    resp = await client.get(
        f"{_BASE}/{med.id}", params={"from": "2026-05-08", "to": "2026-05-08"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Aliased wire names round-trip.
    assert body["from"] == "2026-05-08"
    assert body["to"] == "2026-05-08"
    assert len(body["days"]) == 1
    assert body["days"][0]["status"] == "taken"
    assert body["adherence_pct"] == 100.0
    assert body["course"] is None  # no total_doses set


async def test_prn_med_has_null_pct(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "prn@example.com")
    med = await make_medication(session, user=user)  # no schedule
    await session.flush()
    await login_as(client, "prn@example.com")
    resp = await client.get(
        f"{_BASE}/{med.id}", params={"from": "2026-05-01", "to": "2026-05-03"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["adherence_pct"] is None


async def test_course_block_present_when_total_set(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "course@example.com")
    med = await make_medication(session, user=user)
    med.total_doses = 5
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    await session.flush()

    await login_as(client, "course@example.com")
    resp = await client.get(
        f"{_BASE}/{med.id}", params={"from": "2026-05-08", "to": "2026-05-08"}
    )
    assert resp.status_code == 200, resp.text
    course = resp.json()["course"]
    assert course == {"total": 5, "taken": 1, "complete": False}
