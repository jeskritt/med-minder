"""Integration tests for ``GET /me``."""

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


async def test_me_returns_user_info(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session, email="me@example.com", name="Me User", role="user", password=_PASSWORD
    )
    cookie = await _login(client, "me@example.com")
    client.cookies.set("mm_session", cookie)

    resp = await client.get("/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Me User"
    assert body["role"] == "user"
    assert body["id"] == str(user.id)


async def test_me_unauthenticated(client: AsyncClient) -> None:
    """GET /me without a cookie returns 401."""
    resp = await client.get("/me")
    assert resp.status_code == 401


async def test_me_with_empty_cookie(client: AsyncClient) -> None:
    """An empty cookie value should return 401."""
    client.cookies.set("mm_session", "")
    resp = await client.get("/me")
    assert resp.status_code == 401


async def test_me_with_tampered_cookie(client: AsyncClient) -> None:
    """A tampered / invalid signature cookie returns 401."""
    client.cookies.set("mm_session", "tampered-value")
    resp = await client.get("/me")
    assert resp.status_code == 401


async def test_me_with_non_string_token(
    client: AsyncClient,
) -> None:
    """If the deserialized cookie payload is not a string, return 401.

    This exercises the ``isinstance(token, str)`` guard in ``get_current_user``.
    """
    from itsdangerous import URLSafeSerializer

    from tests.api.conftest import TEST_SESSION_SECRET

    # Sign a non-string payload (integer).
    serializer = URLSafeSerializer(TEST_SESSION_SECRET, salt="mm_session")
    bad_cookie: str = serializer.dumps(12345)

    client.cookies.set("mm_session", bad_cookie)
    resp = await client.get("/me")
    assert resp.status_code == 401
