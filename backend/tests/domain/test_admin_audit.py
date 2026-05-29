"""Unit tests for the admin audit writer (FR-013/FR-020)."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import AdminAuditLog
from medminder.domain.audit import record_admin_action
from medminder.domain.users import create_user


async def _count_entries(session: AsyncSession, target_id: object) -> int:
    stmt = select(func.count()).select_from(AdminAuditLog).where(
        AdminAuditLog.target_user_id == target_id
    )
    return int((await session.execute(stmt)).scalar_one())


async def test_records_exactly_one_row(session: AsyncSession) -> None:
    actor = await create_user(
        session,
        email="actor@example.com",
        name="Actor",
        role="admin",
        password="correct horse battery staple",
    )
    target = await create_user(
        session,
        email="target@example.com",
        name="Target",
        role="user",
        password="correct horse battery staple",
    )

    entry = await record_admin_action(
        session,
        actor_id=actor.id,
        action="create",
        target_user_id=target.id,
        details={"fields": ["email", "name", "role"]},
    )

    assert entry.action == "create"
    assert entry.actor_id == actor.id
    assert await _count_entries(session, target.id) == 1


async def test_details_carry_no_secret_values(session: AsyncSession) -> None:
    actor = await create_user(
        session,
        email="actor2@example.com",
        name="Actor",
        role="admin",
        password="correct horse battery staple",
    )
    target = await create_user(
        session,
        email="target2@example.com",
        name="Target",
        role="user",
        password="hunter2 hunter2 hunter2",
    )

    entry = await record_admin_action(
        session,
        actor_id=actor.id,
        action="password_reset",
        target_user_id=target.id,
        details={"fields": ["password"]},
    )

    # The marker may name the *field* "password" but must never carry the
    # plaintext or the stored hash.
    serialized = str(entry.details)
    assert "hunter2" not in serialized
    assert target.password_hash not in serialized


async def test_none_details_stored_as_empty_object(session: AsyncSession) -> None:
    actor = await create_user(
        session,
        email="actor3@example.com",
        name="Actor",
        role="admin",
        password="correct horse battery staple",
    )
    target = await create_user(
        session,
        email="target3@example.com",
        name="Target",
        role="user",
        password="correct horse battery staple",
    )
    entry = await record_admin_action(
        session,
        actor_id=actor.id,
        action="deactivate",
        target_user_id=target.id,
    )
    assert entry.details == {}


async def test_create_path_emits_no_secret_to_logs(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-020: provisioning must not write the plaintext password to logs."""
    secret = "super secret passphrase value"
    with caplog.at_level(logging.DEBUG):
        actor = await create_user(
            session,
            email="actor4@example.com",
            name="Actor",
            role="admin",
            password="correct horse battery staple",
        )
        target = await create_user(
            session,
            email="provisioned@example.com",
            name="Target",
            role="user",
            password=secret,
        )
        await record_admin_action(
            session,
            actor_id=actor.id,
            action="create",
            target_user_id=target.id,
            details={"fields": ["email", "name", "role"]},
        )
    assert secret not in caplog.text
    assert target.password_hash not in caplog.text
