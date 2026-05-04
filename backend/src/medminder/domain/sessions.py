"""Session-token domain logic.

Tokens are random ``secrets.token_urlsafe(32)`` strings (≥ 256 bits of
entropy, FR-002 / D2).  The DB only ever stores their SHA-256 digest;
the plaintext exists on the wire and inside the signed cookie, never
in persistent storage and never in logs.

Successful authentication mutates ``sessions.expires_at`` in place to
implement the rolling 30-day expiry (D4 / FR-009) — there is no
separate ``last_seen_at`` column, by design.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import SessionModel, User

SESSION_LIFETIME: timedelta = timedelta(days=30)
"""Server-side session lifetime — both initial and post-extension."""

_TOKEN_NBYTES: int = 32  # 256 bits


def _now() -> datetime:
    return datetime.now(UTC)


def generate_token() -> str:
    """Mint a new opaque session token (URL-safe, ≥ 256 bits of entropy)."""
    return secrets.token_urlsafe(_TOKEN_NBYTES)


def hash_token(plaintext: str) -> str:
    """SHA-256 hex digest of ``plaintext`` — the DB lookup key."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


async def create_session(
    session: AsyncSession, *, user_id: uuid.UUID
) -> tuple[SessionModel, str]:
    """Mint a token, persist its hash, return ``(row, plaintext_token)``."""
    plaintext = generate_token()
    row = SessionModel(
        user_id=user_id,
        token_hash=hash_token(plaintext),
        expires_at=_now() + SESSION_LIFETIME,
    )
    session.add(row)
    await session.flush()
    return row, plaintext


async def authenticate_token(
    session: AsyncSession, *, plaintext_token: str
) -> User | None:
    """Resolve token → user, extending ``expires_at`` on success.

    Returns the matching, non-soft-deleted user iff the token row
    exists and ``expires_at > now()``.  On miss / expiry / soft-deleted
    user, no row is mutated (FR-009).
    """
    digest = hash_token(plaintext_token)
    stmt = (
        select(SessionModel, User)
        .join(User, SessionModel.user_id == User.id)
        .where(
            SessionModel.token_hash == digest,
            User.deleted_at.is_(None),
        )
    )
    result = (await session.execute(stmt)).first()
    if result is None:
        return None
    sess_row, user = result
    now = _now()
    if sess_row.expires_at <= now:
        return None
    sess_row.expires_at = now + SESSION_LIFETIME
    await session.flush()
    return user  # type: ignore[no-any-return]


async def delete_session_by_token_hash(
    session: AsyncSession, *, token_hash: str
) -> bool:
    """Delete the session keyed by ``token_hash``.

    Returns ``True`` iff a row was deleted.  Idempotent under the
    ``mm_session`` cookie being replayed (logout double-click, FR-006).
    """
    result = await session.execute(
        delete(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    return (result.rowcount or 0) > 0  # type: ignore[attr-defined]


async def revoke_all_user_sessions(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Delete every ``sessions`` row for ``user_id``; return the count.

    Called by the admin CLI on password change (FR-010) and soft-delete
    (FR-011) inside the same transaction as the corresponding
    ``users``-row mutation.
    """
    result = await session.execute(
        delete(SessionModel).where(SessionModel.user_id == user_id)
    )
    return result.rowcount or 0  # type: ignore[attr-defined]
