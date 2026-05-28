"""Unit tests for the last-admin guard primitive ``count_active_admins``.

The self-action and last-admin *raise* paths live in ``admin_update_user`` /
``admin_deactivate_user`` (User Stories 2 and 3) and are exercised by those
stories' tests; this file covers the shared counting primitive (FR-010) that
backs them, and that it excludes regulars and soft-deleted admins.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import (
    count_active_admins,
    create_user,
    soft_delete_user,
    update_user,
)

_PW = "correct horse battery staple"


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
