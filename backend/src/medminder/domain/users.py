"""User management primitives shared by the CLI and (future) HTTP auth.

All functions take an :class:`AsyncSession` so the caller decides where
the transaction boundary lives.  The CLI wraps each command in a
single transaction; future Phase 2 auth code will share the request-
scoped session.

Email is normalized via ``LOWER(email)`` for lookup but stored as
typed (D8).  Soft delete sets ``deleted_at`` and is the only delete
path exposed in v1 (D6).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import User
from medminder.db.models.users import UserRole
from medminder.domain.passwords import (
    hash_password,
    password_too_short,
    verify_password,
)


class DomainError(Exception):
    """Base for user-domain errors that the CLI maps to non-zero exits."""


class UserNotFoundError(DomainError):
    pass


class DuplicateEmailError(DomainError):
    pass


class PasswordTooShortError(DomainError):
    pass


class NoChangesSpecifiedError(DomainError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def get_user_by_email(
    session: AsyncSession,
    *,
    email: str,
    include_deleted: bool = False,
) -> User | None:
    """Case-insensitive lookup; returns ``None`` if no match."""
    stmt = select(User).where(func.lower(User.email) == email.lower())
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_users(
    session: AsyncSession,
    *,
    role: UserRole | None = None,
    include_deleted: bool = False,
) -> Sequence[User]:
    stmt = select(User).order_by(User.created_at)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    return (await session.execute(stmt)).scalars().all()


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    role: UserRole,
    password: str,
    timezone_name: str = "UTC",
) -> User:
    if password_too_short(password):
        raise PasswordTooShortError(
            f"Password must be at least 12 characters (got {len(password)})."
        )
    existing = await get_user_by_email(
        session, email=email, include_deleted=True
    )
    if existing is not None:
        raise DuplicateEmailError(f"A user with email {email!r} already exists.")
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role=role,
        timezone=timezone_name,
    )
    session.add(user)
    await session.flush()
    return user


async def update_user(
    session: AsyncSession,
    *,
    email: str,
    new_email: str | None = None,
    new_name: str | None = None,
    new_role: UserRole | None = None,
    new_password: str | None = None,
) -> User:
    if all(
        v is None for v in (new_email, new_name, new_role, new_password)
    ):
        raise NoChangesSpecifiedError("No changes specified.")
    user = await get_user_by_email(session, email=email)
    if user is None:
        raise UserNotFoundError(f"No active user with email {email!r}.")
    if new_email is not None and new_email.lower() != email.lower():
        clash = await get_user_by_email(
            session, email=new_email, include_deleted=True
        )
        if clash is not None:
            raise DuplicateEmailError(
                f"A user with email {new_email!r} already exists."
            )
        user.email = new_email
    if new_name is not None:
        user.name = new_name
    if new_role is not None:
        user.role = new_role
    if new_password is not None:
        if password_too_short(new_password):
            raise PasswordTooShortError(
                "Password must be at least 12 characters "
                f"(got {len(new_password)})."
            )
        user.password_hash = hash_password(new_password)
    await session.flush()
    return user


async def soft_delete_user(
    session: AsyncSession, *, email: str
) -> uuid.UUID:
    user = await get_user_by_email(session, email=email)
    if user is None:
        raise UserNotFoundError(f"No active user with email {email!r}.")
    user.deleted_at = _utcnow()
    await session.flush()
    return user.id


__all__ = [
    "DomainError",
    "DuplicateEmailError",
    "NoChangesSpecifiedError",
    "PasswordTooShortError",
    "UserNotFoundError",
    "create_user",
    "get_user_by_email",
    "hash_password",
    "list_users",
    "soft_delete_user",
    "update_user",
    "verify_password",
]
