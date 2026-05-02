"""Domain-level user CRUD tests against real Postgres."""

from __future__ import annotations

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


async def test_update_missing_user(session: AsyncSession) -> None:
    with pytest.raises(UserNotFoundError):
        await update_user(
            session, email="nope@example.com", new_name="x"
        )


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
    await create_user(
        session,
        email="a@example.com",
        name="A",
        role="user",
        password="correct horse battery staple",
    )
    await create_user(
        session,
        email="b@example.com",
        name="B",
        role="admin",
        password="correct horse battery staple",
    )
    admins = await list_users(session, role="admin")
    assert {u.email for u in admins} == {"b@example.com"}

    await soft_delete_user(session, email="a@example.com")
    active = await list_users(session)
    assert {u.email for u in active} == {"b@example.com"}
    everyone = await list_users(session, include_deleted=True)
    assert {u.email for u in everyone} == {"a@example.com", "b@example.com"}
