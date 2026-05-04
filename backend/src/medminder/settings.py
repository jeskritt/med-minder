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
    def _require_session_secret_outside_dev(self) -> "Settings":
        """Refuse to boot if a non-dev env still has the dev fallback secret."""
        if (
            self.env != "development"
            and self.session_secret == DEV_SESSION_SECRET_FALLBACK
        ):
            raise ValueError(
                "SESSION_SECRET must be set to a strong, environment-specific "
                "value when ENV is not 'development'."
            )
        return self
