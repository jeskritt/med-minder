"""Edit-user endpoint tests (FR-006/FR-009/FR-023)."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import AdminAuditLog, User
from medminder.domain.users import create_user
from tests.api.conftest import FIXTURE_PASSWORD, login_as


async def _make_target(session: AsyncSession, *, role: str = "user") -> User:
    return await create_user(
        session,
        email=f"t-{uuid4().hex}@example.com",
        name="Target",
        role=role,  # type: ignore[arg-type]
        password=FIXTURE_PASSWORD,
    )


async def test_edit_non_admin_403(
    client: AsyncClient, session: AsyncSession, non_admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, non_admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{target.id}", json={"name": "Nope"}
    )
    assert resp.status_code == 403


async def test_edit_name_and_role_200(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{target.id}", json={"name": "Renamed", "role": "admin"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["role"] == "admin"


async def test_edit_writes_one_audit_row(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.patch(f"/api/v1/users/{target.id}", json={"name": "X"})
    assert resp.status_code == 200
    count = (
        await session.execute(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.target_user_id == target.id)
        )
    ).scalar_one()
    assert count == 1


async def test_edit_duplicate_email_409(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    a = await _make_target(session)
    b = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{a.id}", json={"email": b.email}
    )
    assert resp.status_code == 409


async def test_edit_malformed_email_422(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{target.id}", json={"email": "not-an-email"}
    )
    assert resp.status_code == 422


async def test_edit_self_403(client: AsyncClient, admin_user: User) -> None:
    await login_as(client, admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{admin_user.id}", json={"name": "Me"}
    )
    assert resp.status_code == 403


async def test_edit_unknown_field_422(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{target.id}", json={"name": "X", "foo": "bar"}
    )
    assert resp.status_code == 422


async def test_edit_empty_body_422(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.patch(f"/api/v1/users/{target.id}", json={})
    assert resp.status_code == 422


async def test_edit_missing_user_404(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.patch(
        f"/api/v1/users/{uuid4()}", json={"name": "Ghost"}
    )
    assert resp.status_code == 404
