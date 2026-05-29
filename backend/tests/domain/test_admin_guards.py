"""Unit tests for the last-admin guard primitive ``count_active_admins``.

The self-action and last-admin *raise* paths live in ``admin_update_user`` /
``admin_deactivate_user`` (User Stories 2 and 3) and are exercised by those
stories' tests; this file covers the shared counting primitive (FR-010) that
backs them, and that it excludes regulars and soft-deleted admins.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import User
from medminder.domain.users import (
    LastAdminError,
    SelfActionError,
    admin_deactivate_user,
    admin_update_user,
    count_active_admins,
    create_user,
    list_users,
    soft_delete_user,
    update_user,
)

_PW = "correct horse battery staple"


async def _neutralize_existing_admins(session: AsyncSession) -> None:
    """Soft-delete any committed admins so absolute-count guards are testable.

    The dev DB may carry a seeded admin; counts are global. This runs inside
    the test's rolled-back transaction, so it never touches real data.
    """
    for u in await list_users(session, role="admin"):
        u.deleted_at = datetime.now(UTC)
    await session.flush()


async def _mk(session: AsyncSession, role: str) -> User:
    return await create_user(
        session,
        email=f"{role}-{uuid4().hex}@x.com",
        name=role.title(),
        role=role,  # type: ignore[arg-type]
        password=_PW,
    )


async def test_counts_only_active_admins(session: AsyncSession) -> None:
    before = await count_active_admins(session)

    await create_user(
        session, email=f"a-{uuid4().hex}@x.com", name="A", role="admin", password=_PW
    )
    await create_user(
        session, email=f"b-{uuid4().hex}@x.com", name="B", role="admin", password=_PW
    )
    # A regular user must not be counted.
    await create_user(
        session, email=f"c-{uuid4().hex}@x.com", name="C", role="user", password=_PW
    )

    assert await count_active_admins(session) == before + 2


async def test_soft_deleted_admin_not_counted(session: AsyncSession) -> None:
    before = await count_active_admins(session)
    email = f"d-{uuid4().hex}@x.com"
    await create_user(
        session, email=email, name="D", role="admin", password=_PW
    )
    assert await count_active_admins(session) == before + 1
    await soft_delete_user(session, email=email)
    assert await count_active_admins(session) == before


async def test_demoted_admin_not_counted(session: AsyncSession) -> None:
    before = await count_active_admins(session)
    email = f"e-{uuid4().hex}@x.com"
    await create_user(
        session, email=email, name="E", role="admin", password=_PW
    )
    assert await count_active_admins(session) == before + 1
    await update_user(session, email=email, new_role="user")
    assert await count_active_admins(session) == before


async def test_self_action_guards_block_actor(session: AsyncSession) -> None:
    actor = await create_user(
        session, email=f"s-{uuid4().hex}@x.com", name="S", role="admin", password=_PW
    )
    with pytest.raises(SelfActionError):
        await admin_deactivate_user(session, actor=actor, user_id=actor.id)
    with pytest.raises(SelfActionError):
        await admin_update_user(
            session, actor=actor, user_id=actor.id, new_name="X"
        )


async def test_deactivate_last_admin_blocked(session: AsyncSession) -> None:
    await _neutralize_existing_admins(session)
    sole = await _mk(session, "admin")
    actor = await _mk(session, "user")
    assert await count_active_admins(session) == 1
    with pytest.raises(LastAdminError):
        await admin_deactivate_user(session, actor=actor, user_id=sole.id)


async def test_demote_last_admin_blocked(session: AsyncSession) -> None:
    await _neutralize_existing_admins(session)
    sole = await _mk(session, "admin")
    actor = await _mk(session, "user")
    with pytest.raises(LastAdminError):
        await admin_update_user(
            session, actor=actor, user_id=sole.id, new_role="user"
        )


async def test_deactivate_admin_when_others_remain_ok(
    session: AsyncSession,
) -> None:
    await _neutralize_existing_admins(session)
    keep = await _mk(session, "admin")
    target = await _mk(session, "admin")
    # Two active admins → deactivating one is allowed (the other remains).
    await admin_deactivate_user(session, actor=keep, user_id=target.id)
    assert await count_active_admins(session) == 1
