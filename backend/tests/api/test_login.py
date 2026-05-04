"""Integration tests for ``POST /auth/login``."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user

_PASSWORD = "correct horse battery staple"


async def test_login_success_sets_cookie(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="login@example.com", name="Login", role="user", password=_PASSWORD
    )

    resp = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": _PASSWORD},
    )
    assert resp.status_code == 204
    assert "mm_session" in resp.cookies


async def test_login_wrong_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="login2@example.com", name="Login2", role="user", password=_PASSWORD
    )

    resp = await client.post(
        "/auth/login",
        json={"email": "login2@example.com", "password": "wrong-password-value"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": _PASSWORD},
    )
    assert resp.status_code == 401


async def test_login_replaces_existing_session(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A second login should replace the old session cookie (FR-016 / D9)."""
    await create_user(
        session, email="relogin@example.com", name="R", role="user", password=_PASSWORD
    )

    resp1 = await client.post(
        "/auth/login",
        json={"email": "relogin@example.com", "password": _PASSWORD},
    )
    assert resp1.status_code == 204
    cookie1 = resp1.cookies.get("mm_session")

    # Second login with the first cookie already set.
    client.cookies.set("mm_session", cookie1)
    resp2 = await client.post(
        "/auth/login",
        json={"email": "relogin@example.com", "password": _PASSWORD},
    )
    assert resp2.status_code == 204
    cookie2 = resp2.cookies.get("mm_session")
    assert cookie2 != cookie1  # new session minted


async def test_login_with_tampered_cookie(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A tampered inbound cookie should not prevent a fresh login."""
    await create_user(
        session, email="tampered@example.com", name="T", role="user", password=_PASSWORD
    )

    client.cookies.set("mm_session", "not-a-valid-signature")
    resp = await client.post(
        "/auth/login",
        json={"email": "tampered@example.com", "password": _PASSWORD},
    )
    assert resp.status_code == 204
    assert "mm_session" in resp.cookies
