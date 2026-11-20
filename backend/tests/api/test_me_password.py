"""Integration tests for ``POST /me/password`` (User Story 1).

Covers FR-003 (403 on wrong current password, distinct from 422), FR-005 /
SC-003 (current device stays signed in via a re-issued cookie; all other
sessions are revoked), and the unauthenticated guard.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import cookie_serializer
from medminder.domain.sessions import create_session
from medminder.domain.users import create_user
from medminder.settings import Settings

_PASSWORD = "correct horse battery staple"
_NEW_PASSWORD = "a brand new passphrase here"


async def _login(client: AsyncClient, email: str, password: str = _PASSWORD) -> str:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 204, resp.text
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    return cookie


async def test_change_password_keeps_this_device_revokes_others(
    client: AsyncClient, session: AsyncSession, app_settings: Settings
) -> None:
    """Correct change → 204 + fresh cookie; other sessions die, this one lives."""
    user = await create_user(
        session, email="pw@example.com", name="PW", role="user", password=_PASSWORD
    )
    cookie_a = await _login(client, "pw@example.com")
    # A second, independent session for the same user (minted directly so the
    # second login does not delete the first session's row).
    _, token_b = await create_session(session, user_id=user.id)
    cookie_b = cookie_serializer(app_settings).dumps(token_b)

    client.cookies.set("mm_session", cookie_a)
    resp = await client.post(
        "/me/password",
        json={"current_password": _PASSWORD, "new_password": _NEW_PASSWORD},
    )
    assert resp.status_code == 204, resp.text
    cookie_a_new = resp.cookies.get("mm_session")
    assert cookie_a_new is not None and cookie_a_new != cookie_a
    # Fresh CSRF cookie is also rotated on password change.
    assert resp.cookies.get("mm_csrf") is not None

    # Other device (session B) is now revoked.
    client.cookies.set("mm_session", cookie_b)
    assert (await client.get("/me")).status_code == 401

    # Current device, on the re-issued cookie, still authenticates.
    client.cookies.set("mm_session", cookie_a_new)
    assert (await client.get("/me")).status_code == 200


async def test_wrong_current_password_returns_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="pw403@example.com", name="X", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "pw403@example.com"))
    resp = await client.post(
        "/me/password",
        json={"current_password": "not the password", "new_password": _NEW_PASSWORD},
    )
    assert resp.status_code == 403


async def test_too_short_new_password_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="pw422@example.com", name="X", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "pw422@example.com"))
    resp = await client.post(
        "/me/password",
        json={"current_password": _PASSWORD, "new_password": "short"},
    )
    assert resp.status_code == 422


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/me/password",
        json={"current_password": _PASSWORD, "new_password": _NEW_PASSWORD},
    )
    assert resp.status_code == 401


async def test_wrong_current_password_is_rate_limited(
    client: AsyncClient, session: AsyncSession, app_settings: Settings
) -> None:
    """Repeated wrong current_password attempts trigger 429 with Retry-After."""
    await create_user(
        session, email="pw-rl@example.com", name="RL", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "pw-rl@example.com"))
    for _ in range(app_settings.login_rate_limit_max_attempts):
        resp = await client.post(
            "/me/password",
            json={"current_password": "wrong password", "new_password": _NEW_PASSWORD},
        )
        assert resp.status_code == 403

    blocked = await client.post(
        "/me/password",
        json={"current_password": _PASSWORD, "new_password": _NEW_PASSWORD},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
