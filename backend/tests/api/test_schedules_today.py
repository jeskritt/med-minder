"""Contract tests for ``GET /api/schedules/today``."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import ScheduleMedication
from medminder.domain.users import create_user
from tests.db.factories import make_dose, make_medication, make_schedule

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


async def test_today_returns_two_slots_ordered(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="tw@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
        timezone_name="America/Los_Angeles",
    )
    other = await create_user(
        session,
        email="other@example.com",
        name="O",
        role="user",
        password=_PASSWORD,
    )

    med = await make_medication(session, user=user, name="Lisinopril")
    morning = await make_schedule(
        session, user=user, label="Morning", time_of_day=time(8, 0)
    )
    evening = await make_schedule(
        session, user=user, label="Evening", time_of_day=time(20, 0)
    )
    session.add_all(
        [
            ScheduleMedication(schedule_id=morning.id, medication_id=med.id),
            ScheduleMedication(schedule_id=evening.id, medication_id=med.id),
        ]
    )

    # Foreign user's schedule/medication — must not leak.
    leaked_med = await make_medication(session, user=other, name="Other Med")
    leaked_sched = await make_schedule(session, user=other)
    session.add(
        ScheduleMedication(schedule_id=leaked_sched.id, medication_id=leaked_med.id)
    )
    await session.flush()

    await _login(client, "tw@example.com")
    resp = await client.get(
        "/api/schedules/today",
        params={"timezone": "America/Los_Angeles", "date": "2026-05-08"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["date"] == "2026-05-08"
    assert body["timezone"] == "America/Los_Angeles"
    assert len(body["items"]) == 2
    assert body["items"][0]["scheduled_time"] == "08:00:00"
    assert body["items"][1]["scheduled_time"] == "20:00:00"
    assert all(item["medication_id"] == str(med.id) for item in body["items"])
    assert all(item["dose"] is None for item in body["items"])


async def test_today_400_invalid_zone(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session,
        email="tz400@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    await _login(client, "tz400@example.com")
    resp = await client.get(
        "/api/schedules/today",
        params={"timezone": "Nowhere/Nope", "date": "2026-05-08"},
    )
    assert resp.status_code == 400


async def test_today_with_dose(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="tdo@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=user)
    sched = await make_schedule(session, user=user)
    session.add(ScheduleMedication(schedule_id=sched.id, medication_id=med.id))
    await session.flush()
    dose = await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )

    await _login(client, "tdo@example.com")
    resp = await client.get(
        "/api/schedules/today",
        params={"timezone": "UTC", "date": "2026-05-08"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["dose"] is not None
    assert body["items"][0]["dose"]["id"] == str(dose.id)


async def test_today_401_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/api/schedules/today")
    assert resp.status_code == 401


# --- UX-enhancements: dow filter dropped, fields surfaced -------------------


async def test_today_surfaces_days_of_week_and_scheduled_today(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Slots off-day-of-week still surface, with `scheduled_today=False`."""
    user = await create_user(
        session,
        email="dow@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=user, name="Lisinopril")
    # 2026-05-08 is a Friday → bit 4 (Mon=0).
    # weekday-only schedule (Mon-Fri = 31) → includes Fri.
    weekdays = await make_schedule(
        session,
        user=user,
        label="Weekday Morning",
        time_of_day=time(8, 0),
        days_of_week=0b0011111,
    )
    # weekend-only schedule (Sat+Sun = 96) → excludes Fri.
    weekend = await make_schedule(
        session,
        user=user,
        label="Weekend Brunch",
        time_of_day=time(11, 0),
        days_of_week=0b1100000,
    )
    session.add_all(
        [
            ScheduleMedication(schedule_id=weekdays.id, medication_id=med.id),
            ScheduleMedication(schedule_id=weekend.id, medication_id=med.id),
        ]
    )
    await session.flush()

    await _login(client, "dow@example.com")
    resp = await client.get(
        "/api/schedules/today",
        params={"timezone": "UTC", "date": "2026-05-08"},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    # Both slots surface now; dow filter is dropped.
    assert len(items) == 2

    by_label = {item["schedule_label"]: item for item in items}
    assert by_label["Weekday Morning"]["scheduled_today"] is True
    assert by_label["Weekday Morning"]["days_of_week"] == 0b0011111
    assert by_label["Weekend Brunch"]["scheduled_today"] is False
    assert by_label["Weekend Brunch"]["days_of_week"] == 0b1100000


# --- UX-enhancements: unscheduled timer meds appear while running ----------
#
# These rely on the live timer state (computed against `datetime.now`),
# so doses are placed relative to *now*, not the target date.


async def test_today_includes_unscheduled_count_down_while_running(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="prn-cd@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="PRN Ibuprofen",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    # Dosed 10 min ago → ~50 min still on the clock → row should show.
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    await session.flush()

    await _login(client, "prn-cd@example.com")
    resp = await client.get("/api/schedules/today")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["medication_id"] == str(med.id)
    assert item["schedule_id"] is None
    assert item["scheduled_time"] is None
    assert item["scheduled_today"] is False
    assert item["timer_state"]["mode"] == "count_down"


async def test_today_excludes_unscheduled_count_down_after_interval(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="prn-cd-done@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="PRN Ibuprofen",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    # Dosed 2 h ago → 60 min interval elapsed → timer expired → no row.
    await make_dose(
        session,
        user=user,
        medication=med,
        taken_at=datetime.now(UTC) - timedelta(hours=2),
    )
    await session.flush()

    await _login(client, "prn-cd-done@example.com")
    resp = await client.get("/api/schedules/today")
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []


async def test_today_unscheduled_count_up_respects_24h_horizon(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="prn-cu@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    recent = await make_medication(
        session, user=user, name="Recent CU", timer_preference="count_up"
    )
    stale = await make_medication(
        session, user=user, name="Stale CU", timer_preference="count_up"
    )
    await make_dose(
        session,
        user=user,
        medication=recent,
        taken_at=datetime.now(UTC) - timedelta(hours=1),
    )
    await make_dose(
        session,
        user=user,
        medication=stale,
        taken_at=datetime.now(UTC) - timedelta(hours=25),
    )
    await session.flush()

    await _login(client, "prn-cu@example.com")
    resp = await client.get("/api/schedules/today")
    assert resp.status_code == 200, resp.text
    med_ids = {item["medication_id"] for item in resp.json()["items"]}
    assert str(recent.id) in med_ids
    assert str(stale.id) not in med_ids


async def test_today_unscheduled_multi_sub_dose_window_open_then_closed(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="prn-msd@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    open_med = await make_medication(
        session,
        user=user,
        name="Open Window",
        timer_preference="multi_sub_dose",
        window_duration_minutes=360,
    )
    closed_med = await make_medication(
        session,
        user=user,
        name="Closed Window",
        timer_preference="multi_sub_dose",
        window_duration_minutes=360,
    )
    # Open: dosed 30 min ago, window (6 h) still open.
    await make_dose(
        session,
        user=user,
        medication=open_med,
        taken_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    # Closed: dosed 7 h ago, window expired.
    await make_dose(
        session,
        user=user,
        medication=closed_med,
        taken_at=datetime.now(UTC) - timedelta(hours=7),
    )
    await session.flush()

    await _login(client, "prn-msd@example.com")
    resp = await client.get("/api/schedules/today")
    assert resp.status_code == 200, resp.text
    med_ids = {item["medication_id"] for item in resp.json()["items"]}
    assert str(open_med.id) in med_ids
    assert str(closed_med.id) not in med_ids


async def test_today_scheduled_timer_med_not_duplicated_as_prn(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A timer med linked to a schedule lists once (scheduled), not twice."""
    user = await create_user(
        session,
        email="sched-cd@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Scheduled CD",
        timer_preference="count_down",
        min_interval_minutes=60,
    )
    sched = await make_schedule(session, user=user)
    session.add(
        ScheduleMedication(schedule_id=sched.id, medication_id=med.id)
    )
    await make_dose(
        session,
        user=user,
        medication=med,
        schedule=sched,
        taken_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    await session.flush()

    await _login(client, "sched-cd@example.com")
    resp = await client.get("/api/schedules/today")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["schedule_id"] == str(sched.id)
