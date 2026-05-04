"""Unit tests for ``medminder.domain.sessions``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.sessions import (
    SESSION_LIFETIME,
    authenticate_token,
    create_session,
    delete_session_by_token_hash,
    generate_token,
    hash_token,
    revoke_all_user_sessions,
)
from medminder.domain.users import create_user

_PASSWORD = "correct horse battery staple"


# --- Pure helpers ----------------------------------------------------------


def test_generate_token_is_unique() -> None:
    """Each call returns a distinct token (probabilistic, but ~256 bits)."""
    tokens = {generate_token() for _ in range(20)}
    assert len(tokens) == 20


def test_hash_token_deterministic() -> None:
    """Same plaintext always produces the same digest."""
    tok = generate_token()
    assert hash_token(tok) == hash_token(tok)


def test_hash_token_differs_for_different_inputs() -> None:
    assert hash_token("aaa") != hash_token("bbb")


# --- create_session --------------------------------------------------------


async def test_create_session_returns_row_and_plaintext(
    session: AsyncSession,
) -> None:
    user = await create_user(
        session, email="s1@example.com", name="S1", role="user", password=_PASSWORD
    )
    row, plaintext = await create_session(session, user_id=user.id)
    assert row.user_id == user.id
    assert row.token_hash == hash_token(plaintext)
    assert row.expires_at > datetime.now(UTC)


# --- authenticate_token ----------------------------------------------------


async def test_authenticate_token_success(session: AsyncSession) -> None:
    user = await create_user(
        session, email="s2@example.com", name="S2", role="user", password=_PASSWORD
    )
    _row, plaintext = await create_session(session, user_id=user.id)

    result = await authenticate_token(session, plaintext_token=plaintext)
    assert result is not None
    assert result.id == user.id


async def test_authenticate_token_extends_expiry(session: AsyncSession) -> None:
    user = await create_user(
        session, email="s3@example.com", name="S3", role="user", password=_PASSWORD
    )
    row, plaintext = await create_session(session, user_id=user.id)
    original_expiry = row.expires_at

    # Advance time a bit so the new expiry is measurably later.
    with freeze_time(datetime.now(UTC) + timedelta(hours=1)):
        result = await authenticate_token(session, plaintext_token=plaintext)

    assert result is not None
    assert row.expires_at > original_expiry


async def test_authenticate_token_expired(session: AsyncSession) -> None:
    user = await create_user(
        session, email="s4@example.com", name="S4", role="user", password=_PASSWORD
    )
    _row, plaintext = await create_session(session, user_id=user.id)

    with freeze_time(datetime.now(UTC) + SESSION_LIFETIME + timedelta(seconds=1)):
        result = await authenticate_token(session, plaintext_token=plaintext)

    assert result is None


async def test_authenticate_token_unknown_token(session: AsyncSession) -> None:
    result = await authenticate_token(session, plaintext_token="no-such-token")
    assert result is None


async def test_authenticate_token_soft_deleted_user(session: AsyncSession) -> None:
    user = await create_user(
        session, email="s5@example.com", name="S5", role="user", password=_PASSWORD
    )
    _row, plaintext = await create_session(session, user_id=user.id)

    # Soft-delete the user.
    user.deleted_at = datetime.now(UTC)
    await session.flush()

    result = await authenticate_token(session, plaintext_token=plaintext)
    assert result is None


# --- delete_session_by_token_hash ------------------------------------------


async def test_delete_session_by_token_hash_existing(session: AsyncSession) -> None:
    user = await create_user(
        session, email="s6@example.com", name="S6", role="user", password=_PASSWORD
    )
    _row, plaintext = await create_session(session, user_id=user.id)

    deleted = await delete_session_by_token_hash(
        session, token_hash=hash_token(plaintext)
    )
    assert deleted is True

    # Token should no longer authenticate.
    assert await authenticate_token(session, plaintext_token=plaintext) is None


async def test_delete_session_by_token_hash_nonexistent(
    session: AsyncSession,
) -> None:
    deleted = await delete_session_by_token_hash(
        session, token_hash="nonexistent-hash"
    )
    assert deleted is False


# --- revoke_all_user_sessions ----------------------------------------------


async def test_revoke_all_user_sessions(session: AsyncSession) -> None:
    user = await create_user(
        session, email="s7@example.com", name="S7", role="user", password=_PASSWORD
    )
    for _ in range(3):
        await create_session(session, user_id=user.id)

    count = await revoke_all_user_sessions(session, user_id=user.id)
    assert count == 3


async def test_revoke_all_user_sessions_returns_zero_when_none(
    session: AsyncSession,
) -> None:
    import uuid

    count = await revoke_all_user_sessions(session, user_id=uuid.uuid4())
    assert count == 0
