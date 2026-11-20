"""Push-subscription API tests (Phase 7, T012)."""

from __future__ import annotations

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import PushSubscription
from medminder.domain.crypto import build_fernet, decrypt_secret
from medminder.domain.users import DuplicateEmailError, create_user
from medminder.settings import Settings

_SECRET = "test-only-stable-secret-for-itsdangerous-signing-12345"
_PW = "correct horse battery staple"
_SUB = {
    "endpoint": "https://push.example/endpoint-1",
    "keys": {"p256dh": "BPpubkey", "auth": "authsecret"},
}


@pytest_asyncio.fixture
async def app_settings() -> Settings:
    return Settings(
        env="development",
        session_secret=_SECRET,
        vapid_public_key="TESTPUBLICKEY",
    )


async def _login(client: AsyncClient, session: AsyncSession, *, email: str) -> None:
    try:
        await create_user(
            session, email=email, name="T", role="user", password=_PW
        )
    except DuplicateEmailError:
        pass  # already created earlier in this test's transaction
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PW}
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)


async def test_vapid_public_key_returns_configured_key(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="vapid@example.com")
    resp = await client.get("/api/v1/push/vapid-public-key")
    assert resp.status_code == 200
    assert resp.json() == {"public_key": "TESTPUBLICKEY"}


async def test_register_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="sub@example.com")
    first = await client.post("/api/v1/push/subscriptions", json=_SUB)
    assert first.status_code == 201, first.text
    second = await client.post("/api/v1/push/subscriptions", json=_SUB)
    assert second.status_code == 200


async def test_keys_are_encrypted_at_rest(
    client: AsyncClient, session: AsyncSession, app_settings: Settings
) -> None:
    """Stored p256dh/auth are ciphertext (ADR-0020); endpoint stays plaintext."""
    await _login(client, session, email="enc-sub@example.com")
    assert (
        await client.post("/api/v1/push/subscriptions", json=_SUB)
    ).status_code == 201

    row = (
        await session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == _SUB["endpoint"]
            )
        )
    ).scalar_one()

    # Not stored as the plaintext fixture values.
    assert row.p256dh != "BPpubkey"
    assert row.auth != "authsecret"
    # Endpoint is the lookup/unique key — left plaintext.
    assert row.endpoint == _SUB["endpoint"]
    # And they decrypt back to the originals.
    fernet = build_fernet(app_settings)
    assert decrypt_secret(fernet, row.p256dh) == "BPpubkey"
    assert decrypt_secret(fernet, row.auth) == "authsecret"


async def test_unsubscribe_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="unsub@example.com")
    await client.post("/api/v1/push/subscriptions", json=_SUB)
    resp = await client.request(
        "DELETE",
        "/api/v1/push/subscriptions",
        json={"endpoint": _SUB["endpoint"]},
    )
    assert resp.status_code == 204
    # Second delete is still 204 (no-op).
    again = await client.request(
        "DELETE",
        "/api/v1/push/subscriptions",
        json={"endpoint": _SUB["endpoint"]},
    )
    assert again.status_code == 204


async def test_unauthenticated_is_401(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/push/vapid-public-key")).status_code == 401
    assert (
        await client.post("/api/v1/push/subscriptions", json=_SUB)
    ).status_code == 401


async def test_delete_does_not_touch_another_users_subscription(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="owner-sub@example.com")
    assert (
        await client.post("/api/v1/push/subscriptions", json=_SUB)
    ).status_code == 201

    await client.post("/auth/logout")
    client.cookies.clear()
    await _login(client, session, email="intruder-sub@example.com")
    # Intruder deletes the same endpoint string → scoped to intruder → no-op.
    assert (
        await client.request(
            "DELETE",
            "/api/v1/push/subscriptions",
            json={"endpoint": _SUB["endpoint"]},
        )
    ).status_code == 204

    # Owner's subscription still exists → re-register returns 200, not 201.
    await client.post("/auth/logout")
    client.cookies.clear()
    await _login(client, session, email="owner-sub@example.com")
    assert (
        await client.post("/api/v1/push/subscriptions", json=_SUB)
    ).status_code == 200


async def test_register_rejects_ssrf_endpoints(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _login(client, session, email="ssrf-sub@example.com")
    for bad in (
        "http://169.254.169.254/latest/meta-data/",
        "https://127.0.0.1:8000/healthz",
        "https://localhost/push",
        "http://fcm.googleapis.com/fcm/send/abc",
    ):
        resp = await client.post(
            "/api/v1/push/subscriptions",
            json={"endpoint": bad, "keys": _SUB["keys"]},
        )
        assert resp.status_code == 422, bad


async def test_register_enforces_per_user_cap(
    client: AsyncClient, session: AsyncSession, app_settings: Settings
) -> None:
    await _login(client, session, email="cap-sub@example.com")
    cap = app_settings.max_push_subscriptions_per_user
    for i in range(cap):
        resp = await client.post(
            "/api/v1/push/subscriptions",
            json={
                "endpoint": f"https://push.example/device-{i}",
                "keys": _SUB["keys"],
            },
        )
        assert resp.status_code == 201

    # Refreshing an existing endpoint still succeeds at the cap.
    refresh = await client.post(
        "/api/v1/push/subscriptions",
        json={
            "endpoint": "https://push.example/device-0",
            "keys": _SUB["keys"],
        },
    )
    assert refresh.status_code == 200

    # Adding one more beyond the cap is rejected.
    overflow = await client.post(
        "/api/v1/push/subscriptions",
        json={
            "endpoint": "https://push.example/device-overflow",
            "keys": _SUB["keys"],
        },
    )
    assert overflow.status_code == 422
