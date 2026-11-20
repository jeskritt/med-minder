"""Database layer: SQLAlchemy 2.0 typed ``Base`` plus engine helpers.

This module is intentionally narrow.  Models live under
``medminder.db.models``; importing this package guarantees every model
class is registered on ``Base.metadata`` (Alembic relies on that).
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from medminder.settings import Settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 typed declarative base for every MedMinder table."""


def make_async_ssl_arg(settings: Settings) -> str | ssl.SSLContext | None:
    """Build the ``ssl`` value for asyncpg ``connect_args`` from ``settings``.

    Returns ``None`` when ``DATABASE_SSL_MODE`` is unset (leaving asyncpg's
    default ``prefer`` behaviour intact).  For ``verify-ca`` and
    ``verify-full``, returns an explicit :class:`ssl.SSLContext` backed by
    ``DATABASE_SSL_CA_FILE`` (or the OS trust store if unset).
    """
    mode = settings.database_ssl_mode
    if mode is None:
        return None
    if mode in {"disable", "allow", "prefer", "require"}:
        return mode
    ctx = ssl.create_default_context(cafile=settings.database_ssl_ca_file)
    ctx.check_hostname = mode == "verify-full"
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def make_sync_connect_args(settings: Settings) -> dict[str, Any]:
    """Build psycopg ``connect_args`` for Alembic from ``settings``."""
    mode = settings.database_ssl_mode
    if mode is None:
        return {}
    args: dict[str, Any] = {"sslmode": mode}
    if settings.database_ssl_ca_file is not None:
        args["sslrootcert"] = settings.database_ssl_ca_file
    elif mode in {"verify-ca", "verify-full"}:
        args["sslrootcert"] = "system"
    return args


def make_async_engine(settings: Settings) -> AsyncEngine:
    """Construct the async SQLAlchemy engine from ``settings``.

    Supabase's transaction-mode pooler does not support prepared
    statements, so asyncpg's per-connection caches must be disabled.
    The kwargs are harmless against a non-pooler Postgres.
    """
    connect_args: dict[str, Any] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    ssl_arg = make_async_ssl_arg(settings)
    if ssl_arg is not None:
        connect_args["ssl"] = ssl_arg
    return create_async_engine(
        settings.database_url,
        connect_args=connect_args,
        future=True,
    )


def make_async_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Build an ``async_sessionmaker`` bound to ``engine``."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a single transaction; commit on success."""
    async with factory() as session:
        async with session.begin():
            yield session


# Import models so ``Base.metadata`` is fully populated for Alembic.
from medminder.db import models as _models  # noqa: E402,F401
