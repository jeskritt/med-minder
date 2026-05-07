"""HTTP integration tests for the medications router.

Covers the four CRUD endpoints plus auth scoping and the
complete-replacement schedule semantics.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user

_PASSWORD = "correct horse battery staple"


async def _login_as(
    client: AsyncClient, session: AsyncSession, *, email: str
) -> None:
    """Create a user, log them in, and persist their cookie on the client."""
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


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Ibuprofen",
        "quantity_per_dose": "200",
        "unit": "mg",
        "times_per_day": 2,
        "start_date": "2026-05-01",
        "end_date": "2026-05-10",
        "total_doses": 20,
        "refill_count": 30,
        "refill_threshold": 5,
        "schedules": ["08:00", "20:00"],
    }
    base.update(overrides)
    return base


async def test_unauthenticated_list_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/medications")
    assert resp.status_code == 401


async def test_create_then_list_returns_medication(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="alice@example.com")

    create = await client.post("/api/v1/medications", json=_body())
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Ibuprofen"
    assert len(body["schedules"]) == 2

    listed = await client.get("/api/v1/medications")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == body["id"]
    assert [s["time_of_day"] for s in items[0]["schedules"]] == [
        "08:00:00",
        "20:00:00",
    ]


async def test_create_validates_end_before_start(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="b@example.com")
    resp = await client.post(
        "/api/v1/medications",
        json=_body(start_date="2026-05-10", end_date="2026-05-01"),
    )
    assert resp.status_code == 422


async def test_create_rejects_zero_total_doses(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Spec: ``total_doses`` must be NULL for untracked, never ``0``."""
    await _login_as(client, session, email="c@example.com")
    resp = await client.post("/api/v1/medications", json=_body(total_doses=0))
    assert resp.status_code == 422


async def test_create_accepts_null_total_doses_as_untracked(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="d@example.com")
    resp = await client.post(
        "/api/v1/medications", json=_body(total_doses=None)
    )
    assert resp.status_code == 201
    assert resp.json()["total_doses"] is None


async def test_update_replaces_schedules(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="e@example.com")
    create = await client.post("/api/v1/medications", json=_body())
    med_id = create.json()["id"]

    updated = await client.put(
        f"/api/v1/medications/{med_id}",
        json=_body(schedules=["09:00", "13:00", "21:00"], times_per_day=3),
    )
    assert updated.status_code == 200
    schedules = updated.json()["schedules"]
    assert [s["time_of_day"] for s in schedules] == [
        "09:00:00",
        "13:00:00",
        "21:00:00",
    ]


async def test_update_404_for_unknown_medication(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="f@example.com")
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await client.put(f"/api/v1/medications/{bogus}", json=_body())
    assert resp.status_code == 404


async def test_delete_soft_deletes(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="g@example.com")
    create = await client.post("/api/v1/medications", json=_body())
    med_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/medications/{med_id}")
    assert resp.status_code == 204

    listed = await client.get("/api/v1/medications")
    assert listed.json()["items"] == []


async def test_delete_404_for_already_deleted(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="h@example.com")
    create = await client.post("/api/v1/medications", json=_body())
    med_id = create.json()["id"]

    first = await client.delete(f"/api/v1/medications/{med_id}")
    assert first.status_code == 204
    second = await client.delete(f"/api/v1/medications/{med_id}")
    assert second.status_code == 404


async def test_users_cannot_see_each_others_medications(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="alice@x.com")
    create = await client.post("/api/v1/medications", json=_body())
    assert create.status_code == 201

    # Switch identities — log out, log in as bob.
    await client.post("/auth/logout")
    client.cookies.clear()
    await _login_as(client, session, email="bob@x.com")

    resp = await client.get("/api/v1/medications")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_users_cannot_update_each_others_medications(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login_as(client, session, email="owner@x.com")
    create = await client.post("/api/v1/medications", json=_body())
    med_id = create.json()["id"]

    await client.post("/auth/logout")
    client.cookies.clear()
    await _login_as(client, session, email="intruder@x.com")

    resp = await client.put(f"/api/v1/medications/{med_id}", json=_body())
    assert resp.status_code == 404
