"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medminder.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    settings:
        Optional pre-built settings instance (useful for testing).
        When *None*, settings are loaded from the environment.
    """
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="MedMinder",
        docs_url="/docs" if settings.env == "development" else None,
        redoc_url=None,
    )

    # --- CORS ----------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes --------------------------------------------------------

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe.  Returns ``{"status": "ok"}`` — no DB call,
        no version, no hostname.  Unauthenticated by design."""
        return {"status": "ok"}

    return app
