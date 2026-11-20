"""Security-headers middleware (Phase 10 hardening)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from medminder.app import create_app
from medminder.settings import Settings


async def test_security_headers_present_on_every_response(
    client: AsyncClient,
) -> None:
    """The defensive headers ride on a plain unauthenticated response."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


async def test_hsts_absent_in_development(client: AsyncClient) -> None:
    """HSTS must not be set in dev (the dev server is plain HTTP)."""
    resp = await client.get("/healthz")
    assert "Strict-Transport-Security" not in resp.headers


async def test_hsts_present_outside_development() -> None:
    """Outside dev (HTTPS), HSTS is emitted."""
    settings = Settings(
        env="production",
        session_secret="prod-secret-not-the-dev-fallback-value-1234567890",
        push_encryption_key="prod-push-key-not-the-dev-fallback-value-1234",
    )
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        resp = await ac.get("/healthz")
    await app.state.engine.dispose()
    assert "Strict-Transport-Security" in resp.headers
    assert "max-age=" in resp.headers["Strict-Transport-Security"]


async def test_openapi_disabled_outside_development(client: AsyncClient) -> None:
    """``/openapi.json`` is served in dev and disabled (404) in production."""
    dev_resp = await client.get("/openapi.json")
    assert dev_resp.status_code == 200

    settings = Settings(
        env="production",
        session_secret="prod-secret-not-the-dev-fallback-value-1234567890",
        push_encryption_key="prod-push-key-not-the-dev-fallback-value-1234",
    )
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        prod_resp = await ac.get("/openapi.json")
    await app.state.engine.dispose()
    assert prod_resp.status_code == 404


async def test_no_store_cache_control_on_sensitive_paths(
    client: AsyncClient,
) -> None:
    """API, auth, and /me responses emit ``Cache-Control: no-store``."""
    for path in ("/me", "/api/v1/medications", "/auth/logout"):
        resp = await client.get(path)
        assert resp.headers.get("Cache-Control") == "no-store", path
        assert resp.headers.get("Pragma") == "no-cache", path

    health = await client.get("/healthz")
    assert "Cache-Control" not in health.headers
