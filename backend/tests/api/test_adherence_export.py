"""Contract tests for ``GET /api/v1/adherence/export.csv``."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import User
from medminder.domain.doses import void_dose
from medminder.domain.users import create_user
from tests.api.conftest import FIXTURE_PASSWORD, login_as
from tests.db.factories import make_dose, make_medication, make_schedule

_URL = "/api/v1/adherence/export.csv"


async def _user(session: AsyncSession, email: str) -> User:
    return await create_user(
        session,
        email=email,
        name="U",
        role="user",
        password=FIXTURE_PASSWORD,
        timezone_name="UTC",
    )


def _parse(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


async def test_401_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get(_URL)
    assert resp.status_code == 401


async def test_headers_columns_and_rows(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "exp1@example.com")
    med = await make_medication(session, user=user, name="Lisinopril")
    sched = await make_schedule(session, user=user, label="Morning")
    from medminder.db.models import ScheduleMedication

    session.add(ScheduleMedication(schedule_id=sched.id, medication_id=med.id))
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    await session.flush()

    await login_as(client, "exp1@example.com")
    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "medminder-doses.csv" in resp.headers["content-disposition"]

    rows = _parse(resp.text)
    assert len(rows) == 1
    row = rows[0]
    assert list(row.keys()) == [
        "medication_name",
        "taken_at",
        "quantity",
        "unit",
        "schedule_label",
        "soft_deleted",
    ]
    assert row["medication_name"] == "Lisinopril"
    assert row["unit"] == "mg"
    assert row["schedule_label"] == "Morning"
    assert row["soft_deleted"] == "false"


async def test_soft_deleted_med_marked_removed(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "exp2@example.com")
    med = await make_medication(session, user=user, name="OldMed")
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    med.deleted_at = datetime.now(UTC)
    await session.flush()

    await login_as(client, "exp2@example.com")
    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    rows = _parse(resp.text)
    assert rows[0]["medication_name"] == "OldMed (removed)"
    assert rows[0]["soft_deleted"] == "true"


async def test_voided_dose_excluded(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "exp3@example.com")
    med = await make_medication(session, user=user)
    kept = await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    voided = await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 20, 0, tzinfo=UTC),
    )
    await void_dose(session, user=user, dose_id=voided.id)
    await session.flush()

    await login_as(client, "exp3@example.com")
    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    rows = _parse(resp.text)
    assert len(rows) == 1
    assert rows[0]["taken_at"].startswith("2026-05-08T08:00")
    _ = kept


async def test_unknown_timezone_400(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _user(session, "exp-tz@example.com")
    await session.flush()
    await login_as(client, "exp-tz@example.com")
    resp = await client.get(_URL, params={"timezone": "Nowhere/Nope"})
    assert resp.status_code == 400


async def test_only_own_doses_exported(
    client: AsyncClient, session: AsyncSession
) -> None:
    me = await _user(session, "exp-me@example.com")
    other = await _user(session, "exp-other@example.com")
    my_med = await make_medication(session, user=me, name="Mine")
    other_med = await make_medication(session, user=other, name="Theirs")
    await make_dose(
        session,
        user=me,
        medication=my_med,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    await make_dose(
        session,
        user=other,
        medication=other_med,
        taken_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )
    await session.flush()

    await login_as(client, "exp-me@example.com")
    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    names = {r["medication_name"] for r in _parse(resp.text)}
    assert names == {"Mine"}


async def _seed_three_days(session: AsyncSession, user: User) -> None:
    med = await make_medication(session, user=user, name="Daily")
    for day in (8, 15, 22):
        await make_dose(
            session,
            user=user,
            medication=med,
            taken_at=datetime(2026, 5, day, 12, 0, tzinfo=UTC),
        )
    await session.flush()


async def test_from_to_filters_to_window(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "win@example.com")
    await _seed_three_days(session, user)
    await login_as(client, "win@example.com")
    resp = await client.get(_URL, params={"from": "2026-05-10", "to": "2026-05-20"})
    assert resp.status_code == 200, resp.text
    rows = _parse(resp.text)
    assert len(rows) == 1
    assert rows[0]["taken_at"].startswith("2026-05-15")


async def test_from_only_is_inclusive(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "fromonly@example.com")
    await _seed_three_days(session, user)
    await login_as(client, "fromonly@example.com")
    resp = await client.get(_URL, params={"from": "2026-05-15"})
    assert resp.status_code == 200, resp.text
    days = [r["taken_at"][:10] for r in _parse(resp.text)]
    assert days == ["2026-05-15", "2026-05-22"]


async def test_to_only_is_inclusive(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "toonly@example.com")
    await _seed_three_days(session, user)
    await login_as(client, "toonly@example.com")
    resp = await client.get(_URL, params={"to": "2026-05-15"})
    assert resp.status_code == 200, resp.text
    days = [r["taken_at"][:10] for r in _parse(resp.text)]
    assert days == ["2026-05-08", "2026-05-15"]


async def test_inverted_range_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _user(session, "inv-exp@example.com")
    await session.flush()
    await login_as(client, "inv-exp@example.com")
    resp = await client.get(_URL, params={"from": "2026-05-20", "to": "2026-05-01"})
    assert resp.status_code == 422


async def test_range_respects_user_timezone(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A 03:00Z dose is 2026-05-08 in UTC but 2026-05-07 in Los Angeles."""
    user = await create_user(
        session,
        email="tzwin@example.com",
        name="U",
        role="user",
        password=FIXTURE_PASSWORD,
        timezone_name="America/Los_Angeles",
    )
    med = await make_medication(session, user=user, name="TZ")
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime(2026, 5, 8, 3, 0, tzinfo=UTC),
    )
    await session.flush()
    await login_as(client, "tzwin@example.com")

    # In the user's zone the dose belongs to 05-07, so a 05-08 window misses it.
    resp = await client.get(_URL, params={"from": "2026-05-08", "to": "2026-05-08"})
    assert resp.status_code == 200, resp.text
    assert len(_parse(resp.text)) == 0

    # A 05-07 window includes it.
    resp = await client.get(_URL, params={"from": "2026-05-07", "to": "2026-05-07"})
    assert resp.status_code == 200, resp.text
    assert len(_parse(resp.text)) == 1


async def test_csv_formula_injection_neutralized(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Spreadsheet formula prefixes (=, +, -, @) are prefixed with a quote."""
    user = await _user(session, "csv-inj@example.com")
    med = await make_medication(session, user=user, name="=CMD|' /C calc'!A0")
    med.unit = "+mg"
    sched = await make_schedule(session, user=user, label="@Evening")
    from medminder.db.models import ScheduleMedication

    session.add(ScheduleMedication(schedule_id=sched.id, medication_id=med.id))
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )
    await session.flush()

    await login_as(client, "csv-inj@example.com")
    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    row = _parse(resp.text)[0]
    assert row["medication_name"] == "'=CMD|' /C calc'!A0"
    assert row["unit"] == "'+mg"
    assert row["schedule_label"] == "'@Evening"
