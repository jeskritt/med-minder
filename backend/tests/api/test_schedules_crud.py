"""Contract tests for the shared-schedules CRUD endpoints.

UX enhancements: schedules are user-level resources.
``GET /api/v1/schedules`` lists them; ``POST`` creates; ``DELETE``
detaches medications + soft-deletes the schedule row.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user

_PASSWORD = "correct horse battery staple"


async def _login(
    client: AsyncClient, session: AsyncSession, *, email: str
) -> None:
    await create_user(
        session, email=email, name="T", role="user", password=_PASSWORD
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)


async def test_schedules_unauthenticated_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 401


async def test_post_then_list_returns_user_schedules(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-list@example.com")
    morning = await client.post(
        "/api/v1/schedules",
        json={"time_of_day": "08:00", "label": "Morning"},
    )
    assert morning.status_code == 201, morning.text
    evening = await client.post(
        "/api/v1/schedules",
        json={"time_of_day": "20:00", "label": "Evening"},
    )
    assert evening.status_code == 201

    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [s["label"] for s in items] == ["Morning", "Evening"]
    assert [s["time_of_day"] for s in items] == ["08:00:00", "20:00:00"]
    assert all(s["days_of_week"] == 127 for s in items)


async def test_post_accepts_optional_label_and_custom_dow(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-defaults@example.com")
    resp = await client.post(
        "/api/v1/schedules",
        json={"time_of_day": "07:30", "days_of_week": 31},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] == ""
    assert body["days_of_week"] == 31


async def test_delete_soft_deletes_and_detaches(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-del@example.com")
    created = await client.post(
        "/api/v1/schedules", json={"time_of_day": "09:00"}
    )
    sched_id = created.json()["id"]

    resp = await client.delete(f"/api/v1/schedules/{sched_id}")
    assert resp.status_code == 204

    listed = await client.get("/api/v1/schedules")
    assert listed.json()["items"] == []

    # Idempotent: a second delete is 404 (soft-deleted).
    second = await client.delete(f"/api/v1/schedules/{sched_id}")
    assert second.status_code == 404


async def test_delete_unknown_id_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-404@example.com")
    resp = await client.delete(f"/api/v1/schedules/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_user_cannot_delete_another_users_schedule(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="owner-sched@example.com")
    created = await client.post(
        "/api/v1/schedules", json={"time_of_day": "10:00"}
    )
    sched_id = created.json()["id"]

    await client.post("/auth/logout")
    client.cookies.clear()
    await _login(client, session, email="intruder-sched@example.com")
    resp = await client.delete(f"/api/v1/schedules/{sched_id}")
    assert resp.status_code == 404


async def test_user_cannot_see_another_users_schedules(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="alice-sched@example.com")
    await client.post(
        "/api/v1/schedules",
        json={"time_of_day": "08:00", "label": "Alice's Morning"},
    )

    await client.post("/auth/logout")
    client.cookies.clear()
    await _login(client, session, email="bob-sched@example.com")
    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_put_updates_time_label_and_dow(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-put@example.com")
    created = await client.post(
        "/api/v1/schedules",
        json={"time_of_day": "08:00", "label": "Morning"},
    )
    sched_id = created.json()["id"]

    resp = await client.put(
        f"/api/v1/schedules/{sched_id}",
        json={"time_of_day": "09:30", "label": "Mid-morning", "days_of_week": 31},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["time_of_day"] == "09:30:00"
    assert body["label"] == "Mid-morning"
    assert body["days_of_week"] == 31

    listed = await client.get("/api/v1/schedules")
    item = listed.json()["items"][0]
    assert item["time_of_day"] == "09:30:00"
    assert item["label"] == "Mid-morning"


async def test_put_unknown_id_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-put-404@example.com")
    resp = await client.put(
        f"/api/v1/schedules/{uuid.uuid4()}",
        json={"time_of_day": "09:00"},
    )
    assert resp.status_code == 404


async def test_user_cannot_update_another_users_schedule(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="owner-put@example.com")
    created = await client.post(
        "/api/v1/schedules", json={"time_of_day": "10:00"}
    )
    sched_id = created.json()["id"]

    await client.post("/auth/logout")
    client.cookies.clear()
    await _login(client, session, email="intruder-put@example.com")
    resp = await client.put(
        f"/api/v1/schedules/{sched_id}",
        json={"time_of_day": "11:00"},
    )
    assert resp.status_code == 404


async def test_list_includes_attached_medications(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sched-attached@example.com")
    morning = await client.post(
        "/api/v1/schedules", json={"time_of_day": "08:00", "label": "Morning"}
    )
    morning_id = morning.json()["id"]
    await client.post(
        "/api/v1/schedules", json={"time_of_day": "20:00", "label": "Evening"}
    )

    med = await client.post(
        "/api/v1/medications",
        json={
            "name": "Aspirin",
            "quantity_per_dose": "100",
            "unit": "mg",
            "times_per_day": 1,
            "schedules": [morning_id],
        },
    )
    assert med.status_code == 201, med.text

    listed = await client.get("/api/v1/schedules")
    items = {s["label"]: s for s in listed.json()["items"]}
    assert [m["name"] for m in items["Morning"]["medications"]] == ["Aspirin"]
    # Unattached schedule reports an empty medications list.
    assert items["Evening"]["medications"] == []
