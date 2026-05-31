"""Unit tests for ``medminder.settings``."""

from __future__ import annotations

import pytest

from medminder.settings import (
    DEV_PUSH_ENCRYPTION_KEY_FALLBACK,
    DEV_SESSION_SECRET_FALLBACK,
    Settings,
)

# A non-fallback value for the prod-mode validator (it only checks equality).
_PROD_PUSH_KEY = "a-real-environment-specific-push-encryption-key"


def test_database_url_sync_asyncpg() -> None:
    """``database_url_sync`` swaps ``+asyncpg`` for ``+psycopg``."""
    s = Settings(database_url="postgresql+asyncpg://u:p@host:5432/db")
    assert s.database_url_sync == "postgresql+psycopg://u:p@host:5432/db"


def test_database_url_sync_plain_postgres() -> None:
    """``database_url_sync`` handles plain ``postgresql://`` scheme."""
    s = Settings(database_url="postgresql://u:p@host:5432/db")
    assert s.database_url_sync == "postgresql+psycopg://u:p@host:5432/db"


def test_database_url_sync_other_scheme() -> None:
    """Non-postgresql URLs pass through unchanged."""
    s = Settings(database_url="sqlite:///test.db")
    assert s.database_url_sync == "sqlite:///test.db"


def test_session_cookie_secure_in_dev() -> None:
    s = Settings(env="development")
    assert s.session_cookie_secure is False


def test_session_cookie_secure_in_prod() -> None:
    s = Settings(
        env="production",
        session_secret="a-real-strong-secret-value",
        push_encryption_key=_PROD_PUSH_KEY,
    )
    assert s.session_cookie_secure is True


def test_require_session_secret_outside_dev() -> None:
    """Non-dev envs reject the fallback dev secret."""
    with pytest.raises(ValueError, match="SESSION_SECRET must be set"):
        Settings(
            env="production",
            session_secret=DEV_SESSION_SECRET_FALLBACK,
            push_encryption_key=_PROD_PUSH_KEY,
        )


def test_require_push_encryption_key_outside_dev() -> None:
    """Non-dev envs reject the fallback push-encryption key."""
    with pytest.raises(ValueError, match="PUSH_ENCRYPTION_KEY must be set"):
        Settings(
            env="production",
            session_secret="a-real-strong-secret-value",
            push_encryption_key=DEV_PUSH_ENCRYPTION_KEY_FALLBACK,
        )
