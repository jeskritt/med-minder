"""Tests for serving the built frontend from FastAPI (ADR-0017).

The single-service production deployment serves the React SPA from the
same origin as the API.  These tests exercise the static mount in
isolation (no DB), using a throw-away ``dist`` directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from medminder.app import create_app
from medminder.settings import Settings

INDEX_MARKER = "<!doctype html><title>MedMinder SPA</title><div id=root></div>"


@pytest_asyncio.fixture
async def spa_dist(tmp_path: Path) -> Path:
    """A minimal built-frontend directory: index.html + one asset."""
    (tmp_path / "index.html").write_text(INDEX_MARKER, encoding="utf-8")
    (tmp_path / "sw.js").write_text("// service worker", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app')", encoding="utf-8")
    return tmp_path


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    return AsyncClient(transport=transport, base_url="http://testserver")


async def test_root_serves_index_html(spa_dist: Path) -> None:
    """GET / returns the SPA shell when a build is configured."""
    settings = Settings(frontend_dist=str(spa_dist))
    async with await _client(settings) as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert INDEX_MARKER in resp.text


async def test_deep_link_falls_back_to_index(spa_dist: Path) -> None:
    """A client-side route with no file on disk falls back to index.html."""
    settings = Settings(frontend_dist=str(spa_dist))
    async with await _client(settings) as client:
        resp = await client.get("/medications/some-id")
    assert resp.status_code == 200
    assert INDEX_MARKER in resp.text


async def test_static_asset_is_served(spa_dist: Path) -> None:
    """Real files (assets, service worker) are served, not the fallback."""
    settings = Settings(frontend_dist=str(spa_dist))
    async with await _client(settings) as client:
        asset = await client.get("/assets/app.js")
        sw = await client.get("/sw.js")
    assert asset.status_code == 200
    assert "console.log('app')" in asset.text
    assert sw.status_code == 200
    assert "service worker" in sw.text


async def test_api_routes_win_over_spa(spa_dist: Path) -> None:
    """Registered API routes match before the SPA mount catches a path."""
    settings = Settings(frontend_dist=str(spa_dist))
    async with await _client(settings) as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_no_mount_when_unconfigured() -> None:
    """With no build configured (dev/tests default), / is not served."""
    settings = Settings(frontend_dist=None)
    async with await _client(settings) as client:
        resp = await client.get("/")
    assert resp.status_code == 404


async def test_no_mount_when_dir_missing(tmp_path: Path) -> None:
    """A configured-but-absent dist directory is skipped, not a boot error."""
    missing = tmp_path / "does-not-exist"
    settings = Settings(frontend_dist=str(missing))
    async with await _client(settings) as client:
        resp = await client.get("/")
    assert resp.status_code == 404
