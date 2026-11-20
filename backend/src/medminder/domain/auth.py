"""Login flow with timing-uniform failure handling and FR-019 logging.

Argon2id verification runs on every code path — successful login,
wrong password, unknown email, soft-deleted user — so the wall-clock
distribution of failures is observably indistinguishable (D5 / FR-004
/ SC-002).  No login attempt logs an email, password, plaintext token,
or token hash (FR-019 / SC-006).
"""

from __future__ import annotations

import enum
import logging
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import User
from medminder.domain.passwords import hash_password, verify_password_async
from medminder.domain.users import get_user_by_email

logger = logging.getLogger("medminder.auth.login")

_MAX_LOG_FIELD_LEN = 256


def _sanitize_log_value(value: str, *, max_len: int = _MAX_LOG_FIELD_LEN) -> str:
    """Strip control characters (CR/LF/etc.) and cap length to prevent log injection."""
    cleaned = "".join(
        ch if ch.isprintable() and ch not in "\r\n\t" else " " for ch in value
    )
    return cleaned[:max_len]

DUMMY_HASH: Final[str] = hash_password("dummy-input-not-a-real-password")
"""Module-level Argon2id hash used by failure paths to keep verifier
timing uniform across {success, wrong-password, unknown-email,
soft-deleted}.  The plaintext is irrelevant; only the hash's existence
and shape matter.  Computed once at import."""


class LoginOutcome(enum.StrEnum):
    """Result of a single login attempt (FR-019 outcome enum)."""

    SUCCESS = "success"
    WRONG_PASSWORD = "wrong_password"  # noqa: S105
    UNKNOWN_EMAIL = "unknown_email"
    SOFT_DELETED = "soft_deleted"


async def attempt_login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str,
    user_agent: str,
) -> tuple[User | None, LoginOutcome]:
    """Resolve ``email`` → user, verify ``password``, classify outcome.

    Always runs Argon2id once: against the user's stored hash on the
    happy path, against ``DUMMY_HASH`` otherwise.  Emits exactly one
    INFO log line per attempt with no PII (FR-019).
    """
    normalized_email = email.strip().lower()
    user = await get_user_by_email(
        session, email=normalized_email, include_deleted=False
    )

    if user is None:
        # Covers both unknown-email and soft-deleted users (FR-005 / FR-014).
        await verify_password_async(DUMMY_HASH, password)
        outcome = LoginOutcome.UNKNOWN_EMAIL
        result_user: User | None = None
    elif not await verify_password_async(user.password_hash, password):
        outcome = LoginOutcome.WRONG_PASSWORD
        result_user = None
    else:
        outcome = LoginOutcome.SUCCESS
        result_user = user

    user_id_str = str(user.id) if user is not None else "none"
    logger.info(
        "auth.login outcome=%s user_id=%s source_ip=%s user_agent=%s",
        outcome.value,
        user_id_str,
        _sanitize_log_value(ip, max_len=64),
        _sanitize_log_value(user_agent),
    )
    return result_user, outcome
