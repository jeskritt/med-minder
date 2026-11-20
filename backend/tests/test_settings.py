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


def test_database_url_sync_prefers_migration_database_url() -> None:
    """``MIGRATION_DATABASE_URL`` overrides ``DATABASE_URL`` for Alembic."""
    s = Settings(
        database_url="postgresql+asyncpg://app:pw@host:6543/db",
        migration_database_url="postgresql+asyncpg://migrator:pw2@host:5432/db",
    )
    assert s.database_url_sync == "postgresql+psycopg://migrator:pw2@host:5432/db"

    s_plain = Settings(
        database_url="postgresql+asyncpg://app:pw@host:6543/db",
        migration_database_url="postgresql://migrator:pw2@host:5432/db",
    )
    assert s_plain.database_url_sync == "postgresql+psycopg://migrator:pw2@host:5432/db"


def test_database_ssl_ca_file_requires_verify_mode() -> None:
    """Setting a CA file without verify-ca/verify-full is rejected."""
    with pytest.raises(ValueError, match="DATABASE_SSL_CA_FILE requires"):
        Settings(database_ssl_ca_file="/etc/secrets/supabase-ca.crt")

    with pytest.raises(ValueError, match="DATABASE_SSL_CA_FILE requires"):
        Settings(
            database_ssl_mode="require",
            database_ssl_ca_file="/etc/secrets/supabase-ca.crt",
        )

    s_ca = Settings(
        database_ssl_mode="verify-ca",
        database_ssl_ca_file="/etc/secrets/supabase-ca.crt",
    )
    assert s_ca.database_ssl_mode == "verify-ca"
    assert s_ca.database_ssl_ca_file == "/etc/secrets/supabase-ca.crt"

    s_full = Settings(
        database_ssl_mode="verify-full",
        database_ssl_ca_file="/etc/secrets/supabase-ca.crt",
    )
    assert s_full.database_ssl_mode == "verify-full"


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


def test_cors_origins_defaults_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS defaults to Vite dev origin in dev and deny-all ([]) in prod."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    dev = Settings(env="development")
    assert dev.cors_origins == ["http://localhost:5173"]

    prod = Settings(
        env="production",
        session_secret="a-real-strong-secret-value",
        push_encryption_key=_PROD_PUSH_KEY,
    )
    assert prod.cors_origins == []

    prod_explicit = Settings(
        env="production",
        session_secret="a-real-strong-secret-value",
        push_encryption_key=_PROD_PUSH_KEY,
        cors_origins=["https://med.example.com"],
    )
    assert prod_explicit.cors_origins == ["https://med.example.com"]
