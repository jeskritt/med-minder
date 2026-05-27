"""Integration tests for ``PUT /me/timezone`` (self-service timezone)."""

from __future__ import annotations

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
        session, email=email, name="TZ", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, email))


async def test_set_timezone_persists_and_echoes(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "tz-set@example.com")

    resp = await client.put("/me/timezone", json={"timezone": "America/Edmonton"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["timezone"] == "America/Edmonton"

    # Reflected on GET /me and stored on the row.
    me = (await client.get("/me")).json()
    assert me["timezone"] == "America/Edmonton"
    user = await get_user_by_email(session, email="tz-set@example.com")
    assert user is not None
    assert user.timezone == "America/Edmonton"


async def test_unknown_zone_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "tz-bad@example.com")
    resp = await client.put("/me/timezone", json={"timezone": "Mars/Phobos"})
    assert resp.status_code == 422
    # The row keeps its original (default UTC) zone.
    user = await get_user_by_email(session, email="tz-bad@example.com")
    assert user is not None
    assert user.timezone == "UTC"


async def test_empty_zone_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _signed_in(client, session, "tz-empty@example.com")
    resp = await client.put("/me/timezone", json={"timezone": ""})
    assert resp.status_code == 422


async def test_unauthenticated(client: AsyncClient) -> None:
    resp = await client.put("/me/timezone", json={"timezone": "America/Edmonton"})
    assert resp.status_code == 401
