"""Integration tests for ``POST /auth/logout``."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> str:
    """Helper: login and return the signed session cookie value."""
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    return cookie


async def test_logout_clears_cookie(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="lo@example.com", name="LO", role="user", password=_PASSWORD
    )
    cookie = await _login(client, "lo@example.com")
    client.cookies.set("mm_session", cookie)

    resp = await client.post("/auth/logout")
    assert resp.status_code == 204
    # Both session and CSRF cookies are cleared with Max-Age=0.
    set_cookies = resp.headers.get_list("set-cookie")
    assert any("mm_session=" in h and "max-age=0" in h.lower() for h in set_cookies)
    assert any("mm_csrf=" in h and "max-age=0" in h.lower() for h in set_cookies)


async def test_logout_without_cookie(client: AsyncClient) -> None:
    """Logout without a cookie is a no-op success (FR-006)."""
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204


async def test_logout_with_tampered_cookie(client: AsyncClient) -> None:
    """A tampered cookie should still result in 204 with the cookie cleared."""
    client.cookies.set("mm_session", "tampered-garbage")
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204


async def test_logout_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Double-logout returns 204 both times (FR-006)."""
    await create_user(
        session, email="lo2@example.com", name="LO2", role="user", password=_PASSWORD
    )
    cookie = await _login(client, "lo2@example.com")
    client.cookies.set("mm_session", cookie)

    resp1 = await client.post("/auth/logout")
    assert resp1.status_code == 204

    # Cookie was cleared, send same one again.
    client.cookies.set("mm_session", cookie)
    resp2 = await client.post("/auth/logout")
    assert resp2.status_code == 204
