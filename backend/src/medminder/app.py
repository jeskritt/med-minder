"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medminder.api import auth as auth_api
from medminder.api import me as me_api
from medminder.db import make_async_engine, make_async_session_factory
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

    engine = make_async_engine(settings)
    session_factory = make_async_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="MedMinder",
        docs_url="/docs" if settings.env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Stash app-scoped state for request-scoped dependencies.
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

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

    app.include_router(auth_api.router)
    app.include_router(me_api.router)

    return app
