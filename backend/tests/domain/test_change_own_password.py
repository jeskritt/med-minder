"""Tests for self-service password change (``change_own_password``).

Covers FR-003 (current-password re-auth), FR-004 (12-char minimum), and
FR-005 (revoke all sessions). The endpoint layer re-issues the current
device's session; that part is exercised in ``tests/api/test_me_password.py``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.passwords import verify_password
from medminder.domain.sessions import authenticate_token, create_session
from medminder.domain.users import (
    IncorrectPasswordError,
    PasswordTooShortError,
    change_own_password,
    create_user,
)

_PASSWORD = "correct horse battery staple"
_NEW_PASSWORD = "a completely new passphrase here"


async def test_correct_current_password_changes_hash_and_revokes_sessions(
    session: AsyncSession,
) -> None:
    """Correct current password → new hash verifies and all sessions are revoked."""
    user = await create_user(
        session,
        email="cp1@example.com",
        name="CP1",
        role="user",
        password=_PASSWORD,
    )
    _, tok1 = await create_session(session, user_id=user.id)
    _, tok2 = await create_session(session, user_id=user.id)

    await change_own_password(
        session,
        user=user,
        current_password=_PASSWORD,
        new_password=_NEW_PASSWORD,
    )

    assert verify_password(user.password_hash, _NEW_PASSWORD) is True
    assert verify_password(user.password_hash, _PASSWORD) is False
    # FR-005: every existing session is revoked (the API re-issues a new one).
    assert await authenticate_token(session, plaintext_token=tok1) is None
    assert await authenticate_token(session, plaintext_token=tok2) is None


async def test_wrong_current_password_raises_and_mutates_nothing(
    session: AsyncSession,
) -> None:
    """Wrong current password → IncorrectPasswordError; hash + sessions untouched."""
    user = await create_user(
        session,
        email="cp2@example.com",
        name="CP2",
        role="user",
        password=_PASSWORD,
    )
    _, tok = await create_session(session, user_id=user.id)
    original_hash = user.password_hash

    with pytest.raises(IncorrectPasswordError):
        await change_own_password(
            session,
            user=user,
            current_password="not the password",
            new_password=_NEW_PASSWORD,
        )

    assert user.password_hash == original_hash
    result = await authenticate_token(session, plaintext_token=tok)
    assert result is not None and result.id == user.id


async def test_too_short_new_password_raises_and_mutates_nothing(
    session: AsyncSession,
) -> None:
    """New password < 12 chars → PasswordTooShortError; nothing changes."""
    user = await create_user(
        session,
        email="cp3@example.com",
        name="CP3",
        role="user",
        password=_PASSWORD,
    )
    _, tok = await create_session(session, user_id=user.id)
    original_hash = user.password_hash

    with pytest.raises(PasswordTooShortError):
        await change_own_password(
            session,
            user=user,
            current_password=_PASSWORD,
            new_password="short",
        )

    assert user.password_hash == original_hash
    result = await authenticate_token(session, plaintext_token=tok)
    assert result is not None and result.id == user.id
