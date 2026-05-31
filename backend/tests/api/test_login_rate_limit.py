"""Login rate-limiting at the HTTP boundary (ADR-0018)."""

from __future__ import annotations

from httpx import AsyncClient

from medminder.db.models import User
from tests.api.conftest import FIXTURE_PASSWORD

_WRONG = "definitely-not-the-password"


async def _bad_login(client: AsyncClient, email: str) -> int:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _WRONG}
    )
    return resp.status_code


async def test_sixth_failure_is_throttled(
    client: AsyncClient, non_admin_user: User
) -> None:
    email = non_admin_user.email
    for _ in range(5):
        assert await _bad_login(client, email) == 401
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _WRONG}
    )
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0
    # Generic body — never reveals whether the account exists.
    assert "incorrect" not in resp.text.lower()


async def test_successful_login_resets_the_counter(
    client: AsyncClient, non_admin_user: User
) -> None:
    email = non_admin_user.email
    for _ in range(4):
        assert await _bad_login(client, email) == 401
    # A correct login clears both the IP and email counters.
    ok = await client.post(
        "/auth/login", json={"email": email, "password": FIXTURE_PASSWORD}
    )
    assert ok.status_code == 204
    # So a subsequent wrong attempt is evaluated fresh (401, not 429).
    assert await _bad_login(client, email) == 401


async def test_ip_lockout_blocks_even_valid_credentials(
    client: AsyncClient, non_admin_user: User
) -> None:
    email = non_admin_user.email
    for _ in range(5):
        assert await _bad_login(client, email) == 401
    # The IP key is now over the threshold, so even the right password is
    # rejected with 429 before any verification happens.
    resp = await client.post(
        "/auth/login", json={"email": email, "password": FIXTURE_PASSWORD}
    )
    assert resp.status_code == 429
