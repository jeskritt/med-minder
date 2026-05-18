"""Domain-level user CRUD tests against real Postgres."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import (
    DuplicateEmailError,
    NoChangesSpecifiedError,
    PasswordTooShortError,
    UserNotFoundError,
    create_user,
    get_user_by_email,
    list_users,
    soft_delete_user,
    update_user,
    verify_password,
)


async def test_create_and_fetch(session: AsyncSession) -> None:
    user = await create_user(
        session,
        email="Foo@Example.com",
        name="Foo",
        role="user",
        password="correct horse battery staple",
    )
    assert user.id is not None
    fetched = await get_user_by_email(session, email="foo@example.com")
    assert fetched is not None
    assert fetched.id == user.id


async def test_password_round_trip(session: AsyncSession) -> None:
    user = await create_user(
        session,
        email="x@example.com",
        name="X",
        role="user",
        password="correct horse battery staple",
    )
    assert verify_password(user.password_hash, "correct horse battery staple")
    assert not verify_password(user.password_hash, "wrong wrong wrong wrong")


async def test_short_password_rejected(session: AsyncSession) -> None:
    with pytest.raises(PasswordTooShortError):
        await create_user(
            session,
            email="x@example.com",
            name="X",
            role="user",
            password="short",
        )


async def test_duplicate_email_rejected_case_insensitive(
    session: AsyncSession,
) -> None:
    await create_user(
        session,
        email="Foo@Example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    with pytest.raises(DuplicateEmailError):
        await create_user(
            session,
            email="FOO@EXAMPLE.com",
            name="B",
            role="user",
            password="correct horse battery staple",
        )


async def test_update_requires_a_change(session: AsyncSession) -> None:
    await create_user(
        session,
        email="a@example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    with pytest.raises(NoChangesSpecifiedError):
        await update_user(session, email="a@example.com")


async def test_update_changes_each_field(session: AsyncSession) -> None:
    user = await create_user(
        session,
        email="a@example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    await update_user(
        session,
        email="a@example.com",
        new_name="A2",
        new_role="admin",
        new_password="another correct horse value",
        new_email="A2@example.com",
    )
    await session.refresh(user)
    assert user.name == "A2"
    assert user.role == "admin"
    assert verify_password(user.password_hash, "another correct horse value")
    assert user.email == "A2@example.com"


async def test_update_persists_case_only_email_change(
    session: AsyncSession,
) -> None:
    """D8: case-only edits keep the casing as typed even though the
    LOWER(email) identity is unchanged."""
    user = await create_user(
        session,
        email="Foo@example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    await update_user(
        session,
        email="Foo@example.com",
        new_email="FOO@EXAMPLE.com",
    )
    await session.refresh(user)
    assert user.email == "FOO@EXAMPLE.com"


async def test_update_missing_user(session: AsyncSession) -> None:
    with pytest.raises(UserNotFoundError):
        await update_user(session, email="nope@example.com", new_name="x")


async def test_update_short_password_rejected(session: AsyncSession) -> None:
    await create_user(
        session,
        email="a@example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    with pytest.raises(PasswordTooShortError):
        await update_user(
            session,
            email="a@example.com",
            new_password="tiny",
        )


async def test_soft_delete_sets_deleted_at(session: AsyncSession) -> None:
    user = await create_user(
        session,
        email="a@example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    deleted_id = await soft_delete_user(session, email="a@example.com")
    assert deleted_id == user.id
    await session.refresh(user)
    assert user.deleted_at is not None
    # default lookup excludes the soft-deleted user
    assert await get_user_by_email(session, email="a@example.com") is None
    # explicit include_deleted brings it back
    again = await get_user_by_email(
        session, email="a@example.com", include_deleted=True
    )
    assert again is not None and again.id == user.id


async def test_soft_delete_missing(session: AsyncSession) -> None:
    with pytest.raises(UserNotFoundError):
        await soft_delete_user(session, email="nope@example.com")


async def test_list_users_filters(session: AsyncSession) -> None:
    # list_users() is global (every row, not just this test's). Assert
    # membership of the rows we create, not exact whole-table equality
    # — the latter breaks against any user committed outside the test
    # transaction (e.g. e2e-seeded users in a shared dev DB). Unique
    # emails keep the assertions unambiguous regardless of residue.
    user_email = f"a-{uuid4().hex}@example.com"
    admin_email = f"b-{uuid4().hex}@example.com"
    await create_user(
        session,
        email=user_email,
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    await create_user(
        session,
        email=admin_email,
        name="B",
        role="admin",
        password="correct horse battery staple",
    )

    admin_emails = {u.email for u in await list_users(session, role="admin")}
    assert admin_email in admin_emails
    assert user_email not in admin_emails

    await soft_delete_user(session, email=user_email)
    active_emails = {u.email for u in await list_users(session)}
    assert user_email not in active_emails
    assert admin_email in active_emails

    everyone_emails = {
        u.email for u in await list_users(session, include_deleted=True)
    }
    assert user_email in everyone_emails
    assert admin_email in everyone_emails
