"""Integration tests for ``PUT /me/quiet-hours`` (self-service quiet hours)."""

from __future__ import annotations

from datetime import time

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user, get_user_by_email

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204, resp.text
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    return cookie


async def _signed_in(client: AsyncClient, session: AsyncSession, email: str) -> None:
    await create_user(
        session, email=email, name="QH", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, email))


async def test_set_quiet_hours_persists_and_echoes(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "qh-set@example.com")

    resp = await client.put("/me/quiet-hours", json={"start": "22:00", "end": "07:00"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quiet_hours_start"] == "22:00:00"
    assert body["quiet_hours_end"] == "07:00:00"

    # Reflected on GET /me and stored on the row.
    me = (await client.get("/me")).json()
    assert me["quiet_hours_start"] == "22:00:00"
    assert me["quiet_hours_end"] == "07:00:00"
    user = await get_user_by_email(session, email="qh-set@example.com")
    assert user is not None
    assert user.quiet_hours_start == time(22, 0)
    assert user.quiet_hours_end == time(7, 0)


async def test_clear_quiet_hours_nulls_both(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "qh-clear@example.com")
    await client.put("/me/quiet-hours", json={"start": "22:00", "end": "07:00"})

    resp = await client.put("/me/quiet-hours", json={"start": None, "end": None})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quiet_hours_start"] is None
    assert body["quiet_hours_end"] is None
    user = await get_user_by_email(session, email="qh-clear@example.com")
    assert user is not None
    assert user.quiet_hours_start is None
    assert user.quiet_hours_end is None


async def test_one_sided_window_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "qh-one@example.com")
    resp = await client.put("/me/quiet-hours", json={"start": "22:00", "end": None})
    assert resp.status_code == 422


async def test_equal_bounds_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "qh-eq@example.com")
    resp = await client.put("/me/quiet-hours", json={"start": "09:00", "end": "09:00"})
    assert resp.status_code == 422


async def test_malformed_time_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "qh-bad@example.com")
    resp = await client.put("/me/quiet-hours", json={"start": "25:99", "end": "07:00"})
    assert resp.status_code == 422


async def test_unauthenticated(client: AsyncClient) -> None:
    resp = await client.put("/me/quiet-hours", json={"start": "22:00", "end": "07:00"})
    assert resp.status_code == 401
