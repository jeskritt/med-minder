"""CSRF double-submit middleware (ADR-0019).

These build their own client with ``csrf_protection_enabled=True`` (the shared
``client`` fixture disables it for the broad suite).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_session
from medminder.app import create_app
from medminder.domain.users import create_user
from medminder.settings import Settings
from tests.api.conftest import TEST_SESSION_SECRET

_PW = "correct horse battery staple"


@pytest_asyncio.fixture
async def csrf_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        env="development",
        session_secret=TEST_SESSION_SECRET,
        csrf_protection_enabled=True,
    )
    app = create_app(settings=settings)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await app.state.engine.dispose()


async def _login(client: AsyncClient, session: AsyncSession) -> str:
    """Create a user, log in, and return the issued CSRF token."""
    email = f"csrf-{uuid4().hex}@example.com"
    await create_user(session, email=email, name="C", role="user", password=_PW)
    resp = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert resp.status_code == 204, resp.text
    token = resp.cookies.get("mm_csrf")
    assert token is not None  # login issues the CSRF cookie
    return token


async def test_login_issues_csrf_cookie_without_a_token(
    csrf_client: AsyncClient, session: AsyncSession
) -> None:
    # /auth/login is exempt (pre-auth) — it works with no X-CSRF-Token.
    await _login(csrf_client, session)


async def test_unsafe_request_without_header_is_forbidden(
    csrf_client: AsyncClient, session: AsyncSession
) -> None:
    await _login(csrf_client, session)
    # The mm_csrf cookie is in the jar, but no matching header → 403.
    resp = await csrf_client.patch("/me", json={"name": "Nope"})
    assert resp.status_code == 403
    assert "csrf" in resp.text.lower()


async def test_unsafe_request_with_mismatched_header_is_forbidden(
    csrf_client: AsyncClient, session: AsyncSession
) -> None:
    await _login(csrf_client, session)
    resp = await csrf_client.patch(
        "/me", json={"name": "Nope"}, headers={"X-CSRF-Token": "not-the-token"}
    )
    assert resp.status_code == 403


async def test_unsafe_request_with_matching_token_passes(
    csrf_client: AsyncClient, session: AsyncSession
) -> None:
    token = await _login(csrf_client, session)
    resp = await csrf_client.patch(
        "/me", json={"name": "Renamed"}, headers={"X-CSRF-Token": token}
    )
    assert resp.status_code == 200, resp.text


async def test_safe_method_is_never_blocked(
    csrf_client: AsyncClient, session: AsyncSession
) -> None:
    await _login(csrf_client, session)
    # No CSRF header on a GET — must still succeed.
    assert (await csrf_client.get("/me")).status_code == 200


async def test_reminder_action_endpoints_are_exempt(
    csrf_client: AsyncClient, session: AsyncSession
) -> None:
    """The SW-driven snooze/take routes are CSRF-exempt (ADR-0019)."""
    await _login(csrf_client, session)
    # No X-CSRF-Token header: an exempt route reaches the handler (→ 404 for a
    # non-existent reminder), it is NOT rejected with 403.
    resp = await csrf_client.post(f"/api/v1/reminders/{uuid4()}/snooze")
    assert resp.status_code != 403
    assert resp.status_code == 404
