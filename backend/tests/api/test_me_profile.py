"""Integration tests for ``PATCH /me`` (User Story 2 — display name)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204, resp.text
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    return cookie


async def test_patch_me_updates_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="nm@example.com", name="Old", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "nm@example.com"))
    resp = await client.patch("/me", json={"name": "New Name"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "New Name"


async def test_patch_me_trims_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="nm2@example.com", name="Old", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "nm2@example.com"))
    resp = await client.patch("/me", json={"name": "  Trimmed  "})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Trimmed"


async def test_patch_me_rejects_blank_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="nm3@example.com", name="Old", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "nm3@example.com"))
    resp = await client.patch("/me", json={"name": "   "})
    assert resp.status_code == 422


async def test_patch_me_rejects_overlong_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="nm4@example.com", name="Old", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "nm4@example.com"))
    resp = await client.patch("/me", json={"name": "a" * 101})
    assert resp.status_code == 422


async def test_patch_me_rejects_extra_fields(
    client: AsyncClient, session: AsyncSession
) -> None:
    """FR-010: the editor cannot change email/role — extra fields are rejected."""
    await create_user(
        session, email="nm5@example.com", name="Old", role="user", password=_PASSWORD
    )
    client.cookies.set("mm_session", await _login(client, "nm5@example.com"))
    resp = await client.patch(
        "/me", json={"name": "New", "email": "hacker@example.com", "role": "admin"}
    )
    assert resp.status_code == 422


async def test_patch_me_unauthenticated(client: AsyncClient) -> None:
    resp = await client.patch("/me", json={"name": "New Name"})
    assert resp.status_code == 401
