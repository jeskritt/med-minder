"""Translate a SQLAlchemy DB URL into ``PG*`` env vars.

``pg_dump`` and ``pg_restore`` are configured via libpq's standard
environment variables; passing the credentials this way (rather than
on the command line) keeps them out of process listings.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, unquote, urlparse

# libpq query-string keys we recognize, mapped to their PG* env-var
# equivalents.  Anything outside this set is rejected (rather than
# silently dropped) so an operator who set, say, ``?sslmode=require``
# never sees their security choice quietly downgraded.
_QUERY_TO_ENV: dict[str, str] = {
    "sslmode": "PGSSLMODE",
    "sslrootcert": "PGSSLROOTCERT",
    "sslcert": "PGSSLCERT",
    "sslkey": "PGSSLKEY",
    "application_name": "PGAPPNAME",
    "connect_timeout": "PGCONNECT_TIMEOUT",
}


def to_pg_env(database_url: str) -> dict[str, str]:
    """Return ``PG*`` env vars derived from ``database_url``.

    Accepts SQLAlchemy-style URLs (``postgresql+asyncpg://...``,
    ``postgresql+psycopg://...``) as well as plain ``postgresql://``.
    The driver suffix is stripped before parsing.

    Raises ``ValueError`` if the URL has no database name or contains
    an unrecognized query parameter.
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
    db = unquote(parsed.path.lstrip("/"))
    if not db:
        raise ValueError(
            "DATABASE_URL must include a database name "
            "(e.g. postgresql://user:pass@host:5432/dbname)."
        )
    env["PGDATABASE"] = db

    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        target = _QUERY_TO_ENV.get(key)
        if target is None:
            raise ValueError(f"Unsupported DATABASE_URL query parameter: {key!r}")
        env[target] = value

    return env
