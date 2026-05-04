"""Tests for session revocation on password change (FR-010) and soft-delete (FR-011)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.sessions import authenticate_token, create_session
from medminder.domain.users import create_user, soft_delete_user, update_user

_PASSWORD = "correct horse battery staple"
_NEW_PASSWORD = "a completely new passphrase here"


async def test_update_user_password_revokes_sessions(
    session: AsyncSession,
) -> None:
    """FR-010: changing a user's password deletes all their sessions."""
    user = await create_user(
        session,
        email="revoke1@example.com",
        name="R1",
        role="user",
        password=_PASSWORD,
    )
    _, tok1 = await create_session(session, user_id=user.id)
    _, tok2 = await create_session(session, user_id=user.id)

    await update_user(session, email="revoke1@example.com", new_password=_NEW_PASSWORD)

    assert await authenticate_token(session, plaintext_token=tok1) is None
    assert await authenticate_token(session, plaintext_token=tok2) is None


async def test_soft_delete_user_revokes_sessions(
    session: AsyncSession,
) -> None:
    """FR-011: soft-deleting a user deletes all their sessions."""
    user = await create_user(
        session,
        email="revoke2@example.com",
        name="R2",
        role="user",
        password=_PASSWORD,
    )
    _, tok1 = await create_session(session, user_id=user.id)
    _, tok2 = await create_session(session, user_id=user.id)

    await soft_delete_user(session, email="revoke2@example.com")

    assert await authenticate_token(session, plaintext_token=tok1) is None
    assert await authenticate_token(session, plaintext_token=tok2) is None


async def test_update_user_name_does_not_revoke_sessions(
    session: AsyncSession,
) -> None:
    """Non-password updates must NOT revoke sessions."""
    user = await create_user(
        session,
        email="revoke3@example.com",
        name="R3",
        role="user",
        password=_PASSWORD,
    )
    _, tok = await create_session(session, user_id=user.id)

    await update_user(session, email="revoke3@example.com", new_name="Renamed")

    # Session must still be valid.
    result = await authenticate_token(session, plaintext_token=tok)
    assert result is not None
    assert result.id == user.id
