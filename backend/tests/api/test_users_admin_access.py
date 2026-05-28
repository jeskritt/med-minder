"""Access-control tests for the admin user surface (FR-001/SC-003)."""

from __future__ import annotations

from httpx import AsyncClient

from medminder.db.models import User
from tests.api.conftest import login_as


async def test_list_unauthenticated_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 401


async def test_create_unauthenticated_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/users",
        json={"email": "x@example.com", "name": "X", "role": "user", "generate": True},
    )
    assert resp.status_code == 401


async def test_list_non_admin_403(
    client: AsyncClient, non_admin_user: User
) -> None:
    await login_as(client, non_admin_user.email)
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 403


async def test_create_non_admin_403(
    client: AsyncClient, non_admin_user: User
) -> None:
    await login_as(client, non_admin_user.email)
    resp = await client.post(
        "/api/v1/users",
        json={"email": "x@example.com", "name": "X", "role": "user", "generate": True},
    )
    assert resp.status_code == 403


async def test_list_admin_200(client: AsyncClient, admin_user: User) -> None:
    await login_as(client, admin_user.email)
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()["items"]}
    assert admin_user.email in emails
