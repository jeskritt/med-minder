"""Deactivate-user endpoint tests (FR-008/FR-009/FR-016).

The sole-admin block (FR-010 → 409) is enforced in the domain and covered by
``tests/domain/test_admin_guards.py``: at the HTTP layer the actor is always a
counted active admin, so removing the *last* admin can only be a self-action,
which the self-guard returns as 403 (lockout prevention, SC-006).
"""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import AdminAuditLog, User
from medminder.domain.users import create_user
from tests.api.conftest import FIXTURE_PASSWORD, login_as


async def _make_target(session: AsyncSession) -> User:
    return await create_user(
        session,
        email=f"t-{uuid4().hex}@example.com",
        name="Target",
        role="user",
        password=FIXTURE_PASSWORD,
    )


async def test_deactivate_non_admin_403(
    client: AsyncClient, session: AsyncSession, non_admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, non_admin_user.email)
    resp = await client.delete(f"/api/v1/users/{target.id}")
    assert resp.status_code == 403


async def test_deactivate_removes_from_list(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.delete(f"/api/v1/users/{target.id}")
    assert resp.status_code == 204, resp.text
    listing = await client.get("/api/v1/users")
    ids = {u["id"] for u in listing.json()["items"]}
    assert str(target.id) not in ids


async def test_deactivate_revokes_sessions(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    login = await client.post(
        "/auth/login",
        json={"email": target.email, "password": FIXTURE_PASSWORD},
    )
    target_cookie = login.cookies.get("mm_session")
    assert target_cookie is not None

    await login_as(client, admin_user.email)
    resp = await client.delete(f"/api/v1/users/{target.id}")
    assert resp.status_code == 204

    client.cookies.set("mm_session", target_cookie)
    me = await client.get("/me")
    assert me.status_code == 401


async def test_deactivate_self_403(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.delete(f"/api/v1/users/{admin_user.id}")
    assert resp.status_code == 403


async def test_deactivate_missing_user_404(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.delete(f"/api/v1/users/{uuid4()}")
    assert resp.status_code == 404


async def test_deactivate_writes_one_audit_row(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.delete(f"/api/v1/users/{target.id}")
    assert resp.status_code == 204
    count = (
        await session.execute(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(
                AdminAuditLog.target_user_id == target.id,
                AdminAuditLog.action == "deactivate",
            )
        )
    ).scalar_one()
    assert count == 1
