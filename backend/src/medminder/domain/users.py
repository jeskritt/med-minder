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
from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import User
from medminder.db.models.users import UserRole
from medminder.domain.audit import record_admin_action
from medminder.domain.passwords import (
    hash_password,
    hash_password_async,
    password_too_short,
    verify_password,
    verify_password_async,
)
from medminder.domain.sessions import revoke_all_user_sessions


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


class IncorrectPasswordError(DomainError):
    """Raised when a self-service password change supplies a wrong current password."""

    pass


class SelfActionError(DomainError):
    """Raised when an admin targets their own account via the admin surface.

    Self-management (name/password/etc.) goes through the profile editor, not
    the admin user-management endpoints (FR-009/FR-019). The API maps this to
    403.
    """

    pass


class LastAdminError(DomainError):
    """Raised when an action would remove the last remaining active admin.

    Covers both deactivating and demoting the sole admin (FR-010/SC-006). The
    API maps this to 409.
    """

    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def get_user_by_email(
    session: AsyncSession,
    *,
    email: str,
    include_deleted: bool = False,
) -> User | None:
    """Case-insensitive, whitespace-trimmed lookup; returns ``None`` if no match."""
    normalized = email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == normalized)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    include_deleted: bool = False,
) -> User | None:
    """Look up a user by primary key; returns ``None`` if no match.

    The admin surface is id-keyed (REST ``/users/{user_id}``); this resolves
    the row so the existing email-keyed domain functions can be reused.
    """
    stmt = select(User).where(User.id == user_id)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def count_active_admins(session: AsyncSession) -> int:
    """Count active admins, locking those rows for the rest of the txn.

    Backs the last-admin guard (FR-010/SC-006). Takes a ``FOR UPDATE`` lock on
    the active-admin rows so two concurrent last-admin removals serialize
    instead of both reading "2" and both proceeding (FR-021) — Postgres
    forbids ``FOR UPDATE`` with an aggregate, so we lock the rows and count
    them in Python.
    """
    stmt = (
        select(User.id)
        .where(User.role == "admin", User.deleted_at.is_(None))
        .with_for_update()
    )
    return len((await session.execute(stmt)).scalars().all())


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
    existing = await get_user_by_email(session, email=email, include_deleted=True)
    if existing is not None:
        raise DuplicateEmailError(f"A user with email {email!r} already exists.")
    user = User(
        email=email,
        password_hash=await hash_password_async(password),
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
    new_timezone: str | None = None,
    new_quiet_hours_start: time | None = None,
    new_quiet_hours_end: time | None = None,
    clear_quiet_hours: bool = False,
) -> User:
    # Quiet hours (Phase 7) are admin-managed like timezone. `None` means
    # "no change"; pass `clear_quiet_hours=True` to set both columns NULL.
    no_field_changes = all(
        v is None
        for v in (
            new_email,
            new_name,
            new_role,
            new_password,
            new_timezone,
            new_quiet_hours_start,
            new_quiet_hours_end,
        )
    )
    if no_field_changes and not clear_quiet_hours:
        raise NoChangesSpecifiedError("No changes specified.")
    user = await get_user_by_email(session, email=email)
    if user is None:
        raise UserNotFoundError(f"No active user with email {email!r}.")
    if new_email is not None:
        # Skip the clash query on case-only edits (the LOWER(email)
        # uniqueness index would self-match), but still apply the new
        # casing — D8 stores email as typed.
        if new_email.lower() != email.lower():
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
    if new_timezone is not None:
        user.timezone = new_timezone
    if clear_quiet_hours:
        user.quiet_hours_start = None
        user.quiet_hours_end = None
    else:
        if new_quiet_hours_start is not None:
            user.quiet_hours_start = new_quiet_hours_start
        if new_quiet_hours_end is not None:
            user.quiet_hours_end = new_quiet_hours_end
    if new_password is not None:
        if password_too_short(new_password):
            raise PasswordTooShortError(
                f"Password must be at least 12 characters (got {len(new_password)})."
            )
        user.password_hash = await hash_password_async(new_password)
        await session.flush()
        # FR-010: revoke every active session on password change.
        await revoke_all_user_sessions(session, user_id=user.id)
    else:
        await session.flush()
    return user


async def change_own_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Self-service password change for the already-authenticated ``user``.

    Verifies ``current_password`` before any mutation, enforces the shared
    12-char minimum, sets the new hash, then revokes **all** of the user's
    sessions (the API layer re-issues a fresh session for the current device,
    so this device stays signed in while every other device is logged out —
    FR-005).

    Takes the authenticated :class:`User` object rather than an email/id, so
    there is no parameter that could target another user (FR-006).

    Raises:
    - IncorrectPasswordError: if ``current_password`` does not verify (→ 403).
    - PasswordTooShortError: if ``new_password`` < 12 chars (→ 422).
    """
    if not await verify_password_async(user.password_hash, current_password):
        raise IncorrectPasswordError("Current password is incorrect.")
    if password_too_short(new_password):
        raise PasswordTooShortError(
            f"Password must be at least 12 characters (got {len(new_password)})."
        )
    user.password_hash = await hash_password_async(new_password)
    await session.flush()
    # FR-005: revoke every session; the API layer mints a fresh one for the
    # current device (mirrors the CLI password-change revoke in update_user).
    await revoke_all_user_sessions(session, user_id=user.id)


async def soft_delete_user(session: AsyncSession, *, email: str) -> uuid.UUID:
    user = await get_user_by_email(session, email=email)
    if user is None:
        raise UserNotFoundError(f"No active user with email {email!r}.")
    user.deleted_at = _utcnow()
    await session.flush()
    # FR-011: revoke every active session on soft-delete.
    await revoke_all_user_sessions(session, user_id=user.id)
    return user.id


async def admin_update_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    new_email: str | None = None,
    new_name: str | None = None,
    new_role: UserRole | None = None,
) -> User:
    """Admin-edit another user's name/email/role, then audit it (FR-006).

    Resolve-by-id → self-edit guard (FR-009/FR-019) → last-admin demote guard
    (FR-010) → reuse ``update_user`` → record the action. The actor cannot edit
    their own row here (that is the profile editor's job).

    Raises ``UserNotFoundError`` (→404), ``SelfActionError`` (→403),
    ``LastAdminError`` (→409), ``DuplicateEmailError`` (→409).
    """
    target = await get_user_by_id(session, user_id=user_id)
    if target is None:
        raise UserNotFoundError(f"No active user with id {user_id}.")
    if target.id == actor.id:
        raise SelfActionError("Manage your own account in the profile editor.")

    old_role = target.role
    demoting_admin = old_role == "admin" and new_role == "user"
    if demoting_admin and await count_active_admins(session) <= 1:
        raise LastAdminError("Cannot demote the last remaining admin.")

    user = await update_user(
        session,
        email=target.email,
        new_email=new_email,
        new_name=new_name,
        new_role=new_role,
    )

    role_changed = new_role is not None and new_role != old_role
    fields = [
        name
        for name, value in (
            ("email", new_email),
            ("name", new_name),
            ("role", new_role),
        )
        if value is not None
    ]
    details: dict[str, object] = {"fields": fields}
    if role_changed:
        details["role"] = f"{old_role}→{new_role}"
    await record_admin_action(
        session,
        actor_id=actor.id,
        action="role_change" if role_changed else "update",
        target_user_id=user.id,
        details=details,
    )
    return user


async def admin_reset_password(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    new_password: str,
) -> User:
    """Admin-reset another user's password, revoking their sessions (FR-007).

    Resolve-by-id → self guard (use the profile editor for your own password) →
    reuse ``update_user(new_password=…)`` (which revokes every session of the
    target) → audit. The caller (API) decides typed vs generated and owns the
    one-time reveal; this records only the field name, never the value (FR-020).

    Raises ``UserNotFoundError`` (→404), ``SelfActionError`` (→403),
    ``PasswordTooShortError`` (→422).
    """
    target = await get_user_by_id(session, user_id=user_id)
    if target is None:
        raise UserNotFoundError(f"No active user with id {user_id}.")
    if target.id == actor.id:
        raise SelfActionError("Change your own password in the profile editor.")
    user = await update_user(
        session, email=target.email, new_password=new_password
    )
    await record_admin_action(
        session,
        actor_id=actor.id,
        action="password_reset",
        target_user_id=user.id,
        details={"fields": ["password"]},
    )
    return user


async def admin_deactivate_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
) -> uuid.UUID:
    """Admin-deactivate (soft-delete) another user, revoking sessions (FR-008).

    Resolve-by-id → self guard (FR-009) → last-admin guard (FR-010) → reuse
    ``soft_delete_user`` (which revokes every session) → audit. No in-app
    restore exists (FR-016).

    Raises ``UserNotFoundError`` (→404), ``SelfActionError`` (→403),
    ``LastAdminError`` (→409).
    """
    target = await get_user_by_id(session, user_id=user_id)
    if target is None:
        raise UserNotFoundError(f"No active user with id {user_id}.")
    if target.id == actor.id:
        raise SelfActionError("You cannot deactivate your own account.")
    if target.role == "admin" and await count_active_admins(session) <= 1:
        raise LastAdminError("Cannot deactivate the last remaining admin.")
    deleted_id = await soft_delete_user(session, email=target.email)
    await record_admin_action(
        session,
        actor_id=actor.id,
        action="deactivate",
        target_user_id=deleted_id,
        details={},
    )
    return deleted_id


__all__ = [
    "DomainError",
    "DuplicateEmailError",
    "IncorrectPasswordError",
    "LastAdminError",
    "NoChangesSpecifiedError",
    "PasswordTooShortError",
    "SelfActionError",
    "UserNotFoundError",
    "admin_deactivate_user",
    "admin_reset_password",
    "admin_update_user",
    "change_own_password",
    "count_active_admins",
    "create_user",
    "get_user_by_email",
    "get_user_by_id",
    "hash_password",
    "list_users",
    "soft_delete_user",
    "update_user",
    "verify_password",
]
