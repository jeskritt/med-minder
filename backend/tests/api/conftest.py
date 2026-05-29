"""Test client fixture for HTTP integration tests.

The fixture builds a fresh ``FastAPI`` app per test and overrides the
``get_session`` dependency so handlers run inside the same transaction
the test fixture rolls back at teardown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_session
from medminder.app import create_app
from medminder.db.models import User
from medminder.domain.users import create_user
from medminder.settings import Settings

TEST_SESSION_SECRET = "test-only-stable-secret-for-itsdangerous-signing-12345"

# Shared by the admin/non-admin fixtures and their login helper.
FIXTURE_PASSWORD = "correct horse battery staple"


@pytest_asyncio.fixture
async def app_settings() -> Settings:
    """Settings instance with a fixed dev-mode secret for stable cookie signatures."""
    return Settings(
        env="development",
        session_secret=TEST_SESSION_SECRET,
    )


@pytest_asyncio.fixture
async def client(
    session: AsyncSession,
    app_settings: Settings,
) -> AsyncIterator[AsyncClient]:
    """``httpx.AsyncClient`` bound to an ASGI app sharing the test's session."""
    app = create_app(settings=app_settings)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    # The app's own engine was unused (override took over) but still
    # needs disposing — ASGITransport does not run lifespan.
    await app.state.engine.dispose()


@pytest_asyncio.fixture
async def admin_user(session: AsyncSession) -> User:
    """An active admin with a known password (unique email per test)."""
    return await create_user(
        session,
        email=f"admin-{uuid4().hex}@example.com",
        name="Admin",
        role="admin",
        password=FIXTURE_PASSWORD,
    )


@pytest_asyncio.fixture
async def non_admin_user(session: AsyncSession) -> User:
    """An active regular user with a known password (unique email per test)."""
    return await create_user(
        session,
        email=f"user-{uuid4().hex}@example.com",
        name="Regular",
        role="user",
        password=FIXTURE_PASSWORD,
    )


async def login_as(client: AsyncClient, email: str) -> None:
    """Authenticate ``client`` as ``email`` (sets its ``mm_session`` cookie)."""
    resp = await client.post(
        "/auth/login", json={"email": email, "password": FIXTURE_PASSWORD}
    )
    assert resp.status_code == 204, resp.text
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)
