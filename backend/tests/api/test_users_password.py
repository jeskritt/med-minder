"""Admin password-reset endpoint tests (FR-007)."""

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


async def test_reset_non_admin_403(
    client: AsyncClient, session: AsyncSession, non_admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, non_admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{target.id}/password", json={"generate": True}
    )
    assert resp.status_code == 403


async def test_reset_typed_password_200(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{target.id}/password",
        json={"password": "a fresh long password"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["temporary_password"] is None
    # New password authenticates.
    login = await client.post(
        "/auth/login",
        json={"email": target.email, "password": "a fresh long password"},
    )
    assert login.status_code == 204


async def test_reset_generate_returns_temp_once(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{target.id}/password", json={"generate": True}
    )
    assert resp.status_code == 200, resp.text
    temp = resp.json()["temporary_password"]
    assert isinstance(temp, str) and len(temp) >= 12
    login = await client.post(
        "/auth/login", json={"email": target.email, "password": temp}
    )
    assert login.status_code == 204


async def test_reset_revokes_target_sessions(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    # Target signs in and we capture their cookie.
    login = await client.post(
        "/auth/login",
        json={"email": target.email, "password": FIXTURE_PASSWORD},
    )
    target_cookie = login.cookies.get("mm_session")
    assert target_cookie is not None

    # Admin resets the target's password.
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{target.id}/password", json={"generate": True}
    )
    assert resp.status_code == 200

    # The target's pre-existing session no longer authenticates (FR-007/SC-005).
    client.cookies.set("mm_session", target_cookie)
    me = await client.get("/me")
    assert me.status_code == 401


async def test_reset_self_403(client: AsyncClient, admin_user: User) -> None:
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{admin_user.id}/password", json={"generate": True}
    )
    assert resp.status_code == 403


async def test_reset_short_password_422(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{target.id}/password", json={"password": "tiny"}
    )
    assert resp.status_code == 422


async def test_reset_both_or_neither_422(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    both = await client.post(
        f"/api/v1/users/{target.id}/password",
        json={"password": "a fresh long password", "generate": True},
    )
    assert both.status_code == 422
    neither = await client.post(
        f"/api/v1/users/{target.id}/password", json={}
    )
    assert neither.status_code == 422


async def test_reset_missing_user_404(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{uuid4()}/password", json={"generate": True}
    )
    assert resp.status_code == 404


async def test_reset_writes_one_audit_row(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    resp = await client.post(
        f"/api/v1/users/{target.id}/password", json={"generate": True}
    )
    assert resp.status_code == 200
    count = (
        await session.execute(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(
                AdminAuditLog.target_user_id == target.id,
                AdminAuditLog.action == "password_reset",
            )
        )
    ).scalar_one()
    assert count == 1
