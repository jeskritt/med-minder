"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """MedMinder configuration.

    Values are read from environment variables (or a ``.env`` file when
    running locally via Docker Compose).
    """

    env: str = "development"
    """Runtime environment: ``development`` | ``production``."""

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medminder"
    """SQLAlchemy-style database URL.  Not used in Phase 0, but wired
    now to prove config plumbing for Phase 1."""

    cors_origins: list[str] = ["http://localhost:5173"]
    """Allowed CORS origins.  Defaults to the Vite dev server.
    Set to your production frontend URL in deployment."""

    model_config = {"env_prefix": "", "case_sensitive": False}
