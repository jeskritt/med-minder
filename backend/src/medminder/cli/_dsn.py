"""Translate a SQLAlchemy DB URL into ``PG*`` env vars.

``pg_dump`` and ``pg_restore`` are configured via libpq's standard
environment variables; passing the credentials this way (rather than
on the command line) keeps them out of process listings.
"""

from __future__ import annotations

from urllib.parse import unquote, urlparse


def to_pg_env(database_url: str) -> dict[str, str]:
    """Return ``PGHOST``/``PGPORT``/``PGUSER``/``PGPASSWORD``/``PGDATABASE``.

    Accepts SQLAlchemy-style URLs (``postgresql+asyncpg://...``,
    ``postgresql+psycopg://...``) as well as plain ``postgresql://``.
    The driver suffix is stripped before parsing.
    """
    raw = database_url
    if "+" in raw.split("://", 1)[0]:
        scheme, rest = raw.split("://", 1)
        scheme = scheme.split("+", 1)[0]
        raw = f"{scheme}://{rest}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError(f"Unsupported DB URL scheme: {parsed.scheme!r}")

    env: dict[str, str] = {}
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port is not None:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    db = parsed.path.lstrip("/")
    if db:
        env["PGDATABASE"] = db
    return env
