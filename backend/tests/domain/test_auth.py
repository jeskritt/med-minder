"""Unit tests for ``medminder.domain.auth``."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.auth import (
    DUMMY_HASH,
    LoginOutcome,
    attempt_login,
)
from medminder.domain.users import create_user

GOOD_PASSWORD = "correct horse battery staple"
WRONG_PASSWORD = "obviously not the right value"
TEST_IP = "203.0.113.4"
TEST_UA = "pytest-agent/1.0"


def test_dummy_hash_is_argon2id() -> None:
    """The fallback hash must look like a real Argon2id encoded value."""
    assert DUMMY_HASH.startswith("$argon2id$")


async def test_attempt_login_success(session: AsyncSession) -> None:
    user = await create_user(
        session,
        email="alice@example.com",
        name="Alice",
        role="user",
        password=GOOD_PASSWORD,
    )
    result_user, outcome = await attempt_login(
        session,
        email="Alice@Example.com",
        password=GOOD_PASSWORD,
        ip=TEST_IP,
        user_agent=TEST_UA,
    )
    assert outcome is LoginOutcome.SUCCESS
    assert result_user is not None
    assert result_user.id == user.id


async def test_attempt_login_wrong_password(session: AsyncSession) -> None:
    await create_user(
        session,
        email="alice@example.com",
        name="Alice",
        role="user",
        password=GOOD_PASSWORD,
    )
    result_user, outcome = await attempt_login(
        session,
        email="alice@example.com",
        password=WRONG_PASSWORD,
        ip=TEST_IP,
        user_agent=TEST_UA,
    )
    assert outcome is LoginOutcome.WRONG_PASSWORD
    assert result_user is None


async def test_attempt_login_unknown_email(session: AsyncSession) -> None:
    result_user, outcome = await attempt_login(
        session,
        email="nope@example.com",
        password=GOOD_PASSWORD,
        ip=TEST_IP,
        user_agent=TEST_UA,
    )
    assert outcome is LoginOutcome.UNKNOWN_EMAIL
    assert result_user is None


async def test_attempt_login_soft_deleted(session: AsyncSession) -> None:
    user = await create_user(
        session,
        email="bob@example.com",
        name="Bob",
        role="user",
        password=GOOD_PASSWORD,
    )
    user.deleted_at = datetime.now(UTC)
    await session.flush()

    result_user, outcome = await attempt_login(
        session,
        email="bob@example.com",
        password=GOOD_PASSWORD,
        ip=TEST_IP,
        user_agent=TEST_UA,
    )
    # FR-005 / FR-014: soft-deleted users are indistinguishable from unknown.
    assert outcome is LoginOutcome.UNKNOWN_EMAIL
    assert result_user is None


async def test_attempt_login_log_lines_are_pii_free(
    session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-019: one INFO line per attempt; no email / password / token in any record.

    User-agent IS logged (FR-019 requires the actual value).
    """
    sensitive_email = "alice@example.com"
    await create_user(
        session,
        email=sensitive_email,
        name="Alice",
        role="user",
        password=GOOD_PASSWORD,
    )

    with caplog.at_level(logging.INFO, logger="medminder.auth.login"):
        # Drive three distinct outcomes (SOFT_DELETED now maps to UNKNOWN_EMAIL).
        await attempt_login(
            session,
            email=sensitive_email,
            password=GOOD_PASSWORD,
            ip=TEST_IP,
            user_agent=TEST_UA,
        )
        await attempt_login(
            session,
            email=sensitive_email,
            password=WRONG_PASSWORD,
            ip=TEST_IP,
            user_agent=TEST_UA,
        )
        await attempt_login(
            session,
            email="ghost@example.com",
            password=GOOD_PASSWORD,
            ip=TEST_IP,
            user_agent=TEST_UA,
        )
        # soft-deleted → UNKNOWN_EMAIL (FR-005)
        from sqlalchemy import update

        from medminder.db.models import User

        await session.execute(
            update(User)
            .where(User.email == sensitive_email)
            .values(deleted_at=datetime.now(UTC))
        )
        await attempt_login(
            session,
            email=sensitive_email,
            password=GOOD_PASSWORD,
            ip=TEST_IP,
            user_agent=TEST_UA,
        )

    login_records = [r for r in caplog.records if r.name == "medminder.auth.login"]
    assert len(login_records) == 4

    forbidden_substrings = (
        sensitive_email,
        "ghost@example.com",
        GOOD_PASSWORD,
        WRONG_PASSWORD,
    )
    for record in login_records:
        rendered = record.getMessage()
        for forbidden in forbidden_substrings:
            assert forbidden not in rendered, (
                f"PII leaked into log: {forbidden!r} in {rendered!r}"
            )
        # FR-019: user-agent value IS logged (not just its length).
        assert "user_agent=" in rendered

    outcomes = {
        record.getMessage().split("outcome=", 1)[1].split(" ", 1)[0]
        for record in login_records
    }
    # SOFT_DELETED no longer emitted; the deleted-user attempt yields UNKNOWN_EMAIL.
    assert outcomes == {
        LoginOutcome.SUCCESS.value,
        LoginOutcome.WRONG_PASSWORD.value,
        LoginOutcome.UNKNOWN_EMAIL.value,
    }
