"""Unit tests for ``medminder.cli._dsn.to_pg_env``."""

from __future__ import annotations

import pytest

from medminder.cli._dsn import to_pg_env


def test_basic_url_translates_to_pg_env_vars() -> None:
    env = to_pg_env("postgresql+asyncpg://alice:secret@db.example:5433/medminder")
    assert env == {
        "PGHOST": "db.example",
        "PGPORT": "5433",
        "PGUSER": "alice",
        "PGPASSWORD": "secret",
        "PGDATABASE": "medminder",
    }


def test_psycopg_driver_is_also_accepted() -> None:
    env = to_pg_env("postgresql+psycopg://alice:secret@db.example:5433/medminder")
    assert env["PGHOST"] == "db.example"
    assert env["PGDATABASE"] == "medminder"


def test_sslmode_propagates_to_pgsslmode() -> None:
    env = to_pg_env("postgresql+asyncpg://u:p@h/medminder?sslmode=require")
    assert env["PGSSLMODE"] == "require"


def test_full_ssl_bundle_propagates() -> None:
    env = to_pg_env(
        "postgresql://u:p@h/m"
        "?sslmode=verify-full"
        "&sslrootcert=/etc/ssl/root.pem"
        "&sslcert=/etc/ssl/c.pem"
        "&sslkey=/etc/ssl/k.pem"
    )
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/etc/ssl/root.pem"
    assert env["PGSSLCERT"] == "/etc/ssl/c.pem"
    assert env["PGSSLKEY"] == "/etc/ssl/k.pem"


def test_application_name_and_connect_timeout_propagate() -> None:
    env = to_pg_env(
        "postgresql://u:p@h/m?application_name=medminder-cli&connect_timeout=10"
    )
    assert env["PGAPPNAME"] == "medminder-cli"
    assert env["PGCONNECT_TIMEOUT"] == "10"


def test_unknown_query_param_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported DATABASE_URL query"):
        to_pg_env("postgresql://u:p@h/m?wat=lol")


def test_missing_database_name_raises() -> None:
    with pytest.raises(ValueError, match="must include a database name"):
        to_pg_env("postgresql+asyncpg://u:p@h:5432")


def test_missing_database_name_with_trailing_slash_raises() -> None:
    with pytest.raises(ValueError, match="must include a database name"):
        to_pg_env("postgresql+asyncpg://u:p@h:5432/")


def test_percent_encoded_database_name_is_decoded() -> None:
    env = to_pg_env("postgresql://u:p@h/my%20db")
    assert env["PGDATABASE"] == "my db"


def test_percent_encoded_user_and_password_decoded() -> None:
    env = to_pg_env("postgresql://us%40er:p%40ss@h/m")
    assert env["PGUSER"] == "us@er"
    assert env["PGPASSWORD"] == "p@ss"


def test_unsupported_scheme_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported DB URL scheme"):
        to_pg_env("mysql://u:p@h/m")
