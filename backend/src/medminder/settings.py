"""Application settings loaded from environment variables."""

from pydantic import model_validator
from pydantic_settings import BaseSettings

DEV_SESSION_SECRET_FALLBACK = "dev-only-insecure-session-secret-do-not-use-in-prod"  # noqa: S105
"""Fixed dev-only fallback for ``SESSION_SECRET``.

Used when ``ENV=development`` and no ``SESSION_SECRET`` env var is set,
so a fresh checkout of the repo can boot without configuration.  Any
non-development environment that boots with this value will refuse to
start (see ``Settings.model_validator``).
"""

DEV_PUSH_ENCRYPTION_KEY_FALLBACK = "NknnBqb6tbuye8eJ-C29YBOGfyHJ_VXCYO0jTelbZvc="
"""Fixed dev-only fallback for ``PUSH_ENCRYPTION_KEY`` (a valid Fernet key).

Lets dev/test boot and round-trip push key encryption without configuration.
Any non-development environment that boots with this value refuses to start
(see ``Settings.model_validator``).  Generate a real key with
``Fernet.generate_key()`` from ``cryptography.fernet``.
"""


class Settings(BaseSettings):
    """MedMinder configuration.

    Values are read from environment variables (or a ``.env`` file when
    running locally via Docker Compose).
    """

    env: str = "development"
    """Runtime environment: ``development`` | ``production``."""

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/medminder"
    )
    """SQLAlchemy async DB URL used by the FastAPI app at runtime."""

    cors_origins: list[str] = ["http://localhost:5173"]
    """Allowed CORS origins.  Defaults to the Vite dev server.
    Set to your production frontend URL in deployment."""

    session_secret: str = DEV_SESSION_SECRET_FALLBACK
    """HMAC key used by ``itsdangerous`` to sign the session cookie.

    Must be set explicitly in any non-development environment.  Rotating
    the value invalidates every outstanding cookie on next request — by
    design.
    """

    session_cookie_name: str = "mm_session"
    """Name of the signed session cookie set by ``POST /auth/login``."""

    # --- CSRF double-submit (Phase 10, ADR-0019) -----------------------
    csrf_protection_enabled: bool = True
    """Whether the CSRF double-submit middleware enforces unsafe requests."""

    csrf_cookie_name: str = "mm_csrf"
    """Non-HttpOnly cookie the SPA echoes back in the ``X-CSRF-Token`` header."""

    trusted_proxy_count: int = 0
    """Number of trusted reverse proxies in front of the app.

    When > 0, ``_client_ip`` reads the real client IP from the
    ``X-Forwarded-For`` header, taking the Nth-from-rightmost entry
    where N = trusted_proxy_count.  Koyeb adds one proxy layer, so
    set to 1 in production.  When 0, the raw peer address is used.
    """

    # --- Login rate-limiting (Phase 10, ADR-0018) ----------------------
    login_rate_limit_enabled: bool = True
    """Whether ``POST /auth/login`` is throttled.  On by default (incl. tests)."""

    login_rate_limit_max_attempts: int = 5
    """Failed login attempts per key (IP / email) before a 429."""

    login_rate_limit_window_seconds: int = 900
    """Rolling window for ``login_rate_limit_max_attempts`` (default 15 min)."""

    # --- Reminders / Web Push (Phase 7) --------------------------------
    vapid_public_key: str = ""
    """Public VAPID application-server key (URL-safe base64, raw P-256 point).

    Served to the browser so it can create a push subscription.  Generate a
    pair with ``python scripts/generate_vapid_keys.py``.  Empty in dev/test →
    push sends are skipped (reminders are still recorded and visible in-app)."""

    vapid_private_key: str = ""
    """Private VAPID key (URL-safe base64 raw key) — **secret**.

    Never sent to the client, logged, or returned in any response.  Empty →
    push delivery is disabled (the rest of the feature still works)."""

    vapid_subject: str = "mailto:admin@example.com"
    """VAPID ``sub`` claim — an operator contact (``mailto:`` or ``https:``)."""

    push_encryption_key: str = DEV_PUSH_ENCRYPTION_KEY_FALLBACK
    """Fernet key used to encrypt push subscription keys at rest (ADR-0020).

    URL-safe base64 of 32 random bytes.  Environment-only; must be set
    explicitly outside development (the dev fallback is refused there).
    Rotating it makes existing subscriptions undecryptable — they are
    treated as gone and the browser re-subscribes."""

    reminders_enabled: bool = True
    """Whether the in-process scheduler starts with the app.

    Off in tests/CI/Alembic so no background tick races the rollback fixture;
    the dispatch/generation domain functions are exercised directly instead."""

    reminder_tick_seconds: int = 30
    """Interval of the recurring dispatch tick (see ADR-0002 / plan D1)."""

    reminder_grace_minutes: int = 15
    """Misfire grace window: a due reminder older than this is not pushed
    (it stays ``pending``/overdue and visible in-app).  See FR-006a."""

    reminder_send_max_attempts: int = 3
    """Max attempts for a transient push send before giving up (FR-016).
    A subscription reported gone (HTTP 404/410) is deleted, not retried."""

    # --- Single-service deployment (ADR-0017) --------------------------
    frontend_dist: str | None = None
    """Filesystem path to the built frontend (Vite ``dist``) to serve.

    When set and the directory exists, the app serves the static SPA at
    ``/`` with an ``index.html`` fallback for client-side routes — the
    single-service production deployment (FastAPI serves both the API and
    the React build from one origin, so the ``SameSite=Lax`` session
    cookie works without CORS; see ADR-0017).  Unset in dev and tests,
    where the Vite dev server serves the frontend, so the static mount is
    skipped entirely and the API surface is unchanged."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    @property
    def database_url_sync(self) -> str:
        """Synchronous variant of ``database_url`` used by Alembic.

        Alembic's migration runner is synchronous, so we swap the
        ``+asyncpg`` driver for ``+psycopg``.  The rest of the URL
        (host, port, credentials, database) is unchanged, keeping
        ``DATABASE_URL`` the single source of truth.
        """
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def session_cookie_secure(self) -> bool:
        """Whether the ``Secure`` cookie attribute should be set.

        ``True`` outside development so cookies only travel over HTTPS;
        ``False`` in development so the Vite dev server (HTTP) works.
        """
        return self.env != "development"

    @model_validator(mode="after")
    def _require_secrets_outside_dev(self) -> "Settings":
        """Refuse to boot if a non-dev env still holds a dev fallback secret."""
        if self.env == "development":
            return self
        if self.session_secret == DEV_SESSION_SECRET_FALLBACK:
            raise ValueError(
                "SESSION_SECRET must be set to a strong, environment-specific "
                "value when ENV is not 'development'."
            )
        if self.push_encryption_key == DEV_PUSH_ENCRYPTION_KEY_FALLBACK:
            raise ValueError(
                "PUSH_ENCRYPTION_KEY must be set to a unique Fernet key "
                "when ENV is not 'development'."
            )
        return self
