"""Test client fixture for HTTP integration tests.

The fixture builds a fresh ``FastAPI`` app per test and overrides the
``get_session`` dependency so handlers run inside the same transaction
the test fixture rolls back at teardown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_session
from medminder.app import create_app
from medminder.settings import Settings

TEST_SESSION_SECRET = "test-only-stable-secret-for-itsdangerous-signing-12345"


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
