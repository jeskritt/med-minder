"""Create-user endpoint tests (FR-003/FR-004/FR-018/FR-023)."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import AdminAuditLog, User
from medminder.domain.users import create_user, get_user_by_email, soft_delete_user
from tests.api.conftest import FIXTURE_PASSWORD, login_as


async def _new_email() -> str:
    return f"new-{uuid4().hex}@example.com"


async def test_create_typed_password_201(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    email = await _new_email()
    resp = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "name": "Typed",
            "role": "user",
            "password": "a fine long password",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "user"
    # No temp password is returned for a typed password.
    assert body["temporary_password"] is None
    # The created user can authenticate immediately, no forced rotation (FR-018).
    login = await client.post(
        "/auth/login", json={"email": email, "password": "a fine long password"}
    )
    assert login.status_code == 204


async def test_create_generated_password_returns_temp_once(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    email = await _new_email()
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "name": "Gen", "role": "user", "generate": True},
    )
    assert resp.status_code == 201, resp.text
    temp = resp.json()["temporary_password"]
    assert isinstance(temp, str) and len(temp) >= 12
    # The generated password actually works for login.
    login = await client.post(
        "/auth/login", json={"email": email, "password": temp}
    )
    assert login.status_code == 204


async def test_create_writes_one_audit_row(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    email = await _new_email()
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "name": "Aud", "role": "user", "generate": True},
    )
    assert resp.status_code == 201
    created = await get_user_by_email(session, email=email)
    assert created is not None
    count = (
        await session.execute(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.target_user_id == created.id)
        )
    ).scalar_one()
    assert count == 1


async def test_create_duplicate_email_409(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    email = await _new_email()
    await create_user(
        session, email=email, name="Existing", role="user", password=FIXTURE_PASSWORD
    )
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "name": "Dup", "role": "user", "generate": True},
    )
    assert resp.status_code == 409


async def test_create_duplicate_soft_deleted_email_409(
    client: AsyncClient, session: AsyncSession, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    email = await _new_email()
    await create_user(
        session, email=email, name="Gone", role="user", password=FIXTURE_PASSWORD
    )
    await soft_delete_user(session, email=email)
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "name": "Reuse", "role": "user", "generate": True},
    )
    assert resp.status_code == 409


async def test_create_short_password_422(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.post(
        "/api/v1/users",
        json={
            "email": await _new_email(),
            "name": "Short",
            "role": "user",
            "password": "tiny",
        },
    )
    assert resp.status_code == 422


async def test_create_both_password_and_generate_422(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.post(
        "/api/v1/users",
        json={
            "email": await _new_email(),
            "name": "Both",
            "role": "user",
            "password": "a fine long password",
            "generate": True,
        },
    )
    assert resp.status_code == 422


async def test_create_neither_password_nor_generate_422(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.post(
        "/api/v1/users",
        json={"email": await _new_email(), "name": "Neither", "role": "user"},
    )
    assert resp.status_code == 422


async def test_create_malformed_email_422(
    client: AsyncClient, admin_user: User
) -> None:
    await login_as(client, admin_user.email)
    resp = await client.post(
        "/api/v1/users",
        json={"email": "not-an-email", "name": "Bad", "role": "user", "generate": True},
    )
    assert resp.status_code == 422
