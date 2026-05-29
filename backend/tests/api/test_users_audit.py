"""Audit-log endpoint tests (FR-013/FR-014/FR-022)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
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


async def test_audit_log_non_admin_403(
    client: AsyncClient, non_admin_user: User
) -> None:
    await login_as(client, non_admin_user.email)
    resp = await client.get("/api/v1/users/audit-log")
    assert resp.status_code == 403


async def test_audit_log_unauthenticated_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/audit-log")
    assert resp.status_code == 401


async def test_audit_log_orders_newest_first(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    # The whole test runs in one transaction, so server-default `now()` would
    # tie; insert explicit timestamps to exercise the ORDER BY created_at DESC.
    target = await _make_target(session)
    base = datetime.now(UTC)
    session.add(
        AdminAuditLog(
            actor_id=admin_user.id,
            target_user_id=target.id,
            action="update",
            details={"fields": ["name"]},
            created_at=base - timedelta(minutes=5),
        )
    )
    session.add(
        AdminAuditLog(
            actor_id=admin_user.id,
            target_user_id=target.id,
            action="password_reset",
            details={"fields": ["password"]},
            created_at=base,
        )
    )
    await session.flush()
    await login_as(client, admin_user.email)

    resp = await client.get("/api/v1/users/audit-log")
    assert resp.status_code == 200
    ours = [
        e
        for e in resp.json()["items"]
        if e["target_user_id"] == str(target.id)
    ]
    assert [e["action"] for e in ours] == ["password_reset", "update"]
    assert all(e["actor_id"] == str(admin_user.id) for e in ours)


async def test_audit_log_omits_secret_values(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    """FR-020: a real password reset must not leak the plaintext into the log."""
    secret = "a fresh long password value"
    target = await _make_target(session)
    await login_as(client, admin_user.email)
    reset = await client.post(
        f"/api/v1/users/{target.id}/password", json={"password": secret}
    )
    assert reset.status_code == 200

    resp = await client.get("/api/v1/users/audit-log")
    assert resp.status_code == 200
    assert secret not in resp.text
    ours = [
        e
        for e in resp.json()["items"]
        if e["target_user_id"] == str(target.id)
    ]
    assert any(e["action"] == "password_reset" for e in ours)


async def test_audit_log_has_no_mutating_route(
    client: AsyncClient, admin_user: User
) -> None:
    """Append-only (FR-022): there is no edit/delete route for the trail.

    A DELETE to the audit-log path is not a real route; it falls to the
    ``/{user_id}`` matcher and 422s on the non-UUID segment — never a 2xx.
    """
    await login_as(client, admin_user.email)
    resp = await client.delete("/api/v1/users/audit-log")
    assert resp.status_code == 422


async def test_audit_log_respects_limit(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    """The trail is bounded by ``limit`` and stays newest-first."""
    target = await _make_target(session)
    base = datetime.now(UTC)
    # Seed 5 rows with strictly increasing timestamps for this target.
    for i in range(5):
        session.add(
            AdminAuditLog(
                actor_id=admin_user.id,
                target_user_id=target.id,
                action="update",
                details={"fields": ["name"], "i": i},
                created_at=base + timedelta(minutes=i),
            )
        )
    await session.flush()
    await login_as(client, admin_user.email)

    resp = await client.get("/api/v1/users/audit-log?limit=3")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 3
    # Newest-first: created_at is non-increasing across the page.
    times = [e["created_at"] for e in items]
    assert times == sorted(times, reverse=True)

    # offset pages past the newest rows.
    page2 = await client.get("/api/v1/users/audit-log?limit=3&offset=3")
    assert page2.status_code == 200
    assert len(page2.json()["items"]) >= 1

    # Out-of-range limit is rejected (422).
    bad = await client.get("/api/v1/users/audit-log?limit=0")
    assert bad.status_code == 422
