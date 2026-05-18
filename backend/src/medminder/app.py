"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medminder.api import auth as auth_api
from medminder.api import doses as doses_api
from medminder.api import me as me_api
from medminder.api import medication_interactions as medication_interactions_api
from medminder.api import medications as medications_api
from medminder.api import schedules as schedules_api
from medminder.api.schemas.errors import (
    ConflictOut,
    InteractionCooldownViolation,
    MinIntervalViolation,
    WindowFullViolation,
)
from medminder.db import make_async_engine, make_async_session_factory
from medminder.domain.interactions import MedicationInteractionConflictError
from medminder.domain.timers import MinIntervalNotElapsedError, WindowFullError
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
    app.include_router(medications_api.router)
    app.include_router(medication_interactions_api.router)
    app.include_router(doses_api.router)
    app.include_router(schedules_api.router)

    @app.exception_handler(MinIntervalNotElapsedError)
    async def _min_interval_handler(
        _request: Request, exc: MinIntervalNotElapsedError
    ) -> JSONResponse:
        body = MinIntervalViolation(
            code="min_interval_not_elapsed",
            medication_id=exc.medication_id,
            next_allowed_at=exc.next_allowed_at,
            remaining_seconds=exc.remaining_seconds,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(WindowFullError)
    async def _window_full_handler(
        _request: Request, exc: WindowFullError
    ) -> JSONResponse:
        body = WindowFullViolation(
            code="window_full",
            medication_id=exc.medication_id,
            window_end=exc.window_end,
            slots_used=exc.slots_used,
            slots_total=exc.slots_total,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(MedicationInteractionConflictError)
    async def _interaction_conflict_handler(
        _request: Request, exc: MedicationInteractionConflictError
    ) -> JSONResponse:
        latest = max(
            exc.conflict.conflicts, key=lambda c: c.cooldown_elapses_at
        )
        body = InteractionCooldownViolation(
            code="interaction_cooldown_active",
            medication_id=exc.medication_id,
            conflicts=[
                ConflictOut(
                    conflicting_medication_id=c.conflicting_medication_id,
                    conflicting_medication_name=c.conflicting_medication_name,
                    cooldown_elapses_at=c.cooldown_elapses_at,
                    remaining_seconds=c.remaining_seconds,
                )
                for c in exc.conflict.conflicts
            ],
            cooldown_elapses_at=latest.cooldown_elapses_at,
            remaining_seconds=latest.remaining_seconds,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    return app
