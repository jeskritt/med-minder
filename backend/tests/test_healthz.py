"""Tests for the /healthz endpoint."""

from httpx import ASGITransport, AsyncClient

from medminder.app import create_app


async def test_healthz_returns_ok() -> None:
    """GET /healthz returns 200 with exact body {"status": "ok"}."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_no_extra_fields() -> None:
    """The /healthz response contains only the 'status' key."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    body = response.json()
    assert list(body.keys()) == ["status"]
