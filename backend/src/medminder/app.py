"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from medminder.api import adherence as adherence_api
from medminder.api import auth as auth_api
from medminder.api import doses as doses_api
from medminder.api import me as me_api
from medminder.api import medication_interactions as medication_interactions_api
from medminder.api import medications as medications_api
from medminder.api import push as push_api
from medminder.api import reminders as reminders_api
from medminder.api import schedules as schedules_api
from medminder.api import schedules_crud as schedules_crud_api
from medminder.api import users as users_api
from medminder.api.csrf import CsrfMiddleware
from medminder.api.schemas.errors import (
    ConflictOut,
    DailyCapViolation,
    InteractionCooldownViolation,
    MinIntervalViolation,
    WindowFullViolation,
)
from medminder.api.security_headers import SecurityHeadersMiddleware
from medminder.db import make_async_engine, make_async_session_factory
from medminder.domain.interactions import MedicationInteractionConflictError
from medminder.domain.rate_limit import LoginRateLimiter, SlidingWindowLimiter
from medminder.domain.timers import (
    DailyCapReachedError,
    MinIntervalNotElapsedError,
    WindowFullError,
)
from medminder.settings import Settings


class _SPAStaticFiles(StaticFiles):
    """Serve the built frontend, falling back to ``index.html`` on 404.

    Client-side routes (``/medications``, ``/reminders``, ``/admin/...``)
    have no matching file on disk, so a hard refresh or deep link would
    otherwise 404.  Returning ``index.html`` lets the React router take
    over.  Mounted at ``/`` *after* the API routers, so real endpoints
    (``/auth/*``, ``/me``, ``/api/*``, ``/healthz``) still win; only
    unmatched paths reach this mount (see ADR-0017)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


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
        scheduler = None
        if settings.reminders_enabled:
            # Lazy import so apscheduler isn't required when reminders are off
            # (tests/CI/Alembic run with reminders_enabled=False).
            from medminder.scheduler import build_scheduler

            scheduler = build_scheduler(settings, session_factory)
            scheduler.start()
            _app.state.scheduler = scheduler
        else:
            logging.getLogger(__name__).info(
                "reminder scheduler disabled (REMINDERS_ENABLED=false)"
            )
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)
            await engine.dispose()

    app = FastAPI(
        title="MedMinder",
        docs_url="/docs" if settings.env == "development" else None,
        openapi_url="/openapi.json" if settings.env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Stash app-scoped state for request-scoped dependencies.
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.login_rate_limiter = LoginRateLimiter(
        max_attempts=settings.login_rate_limit_max_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    app.state.password_change_rate_limiter = SlidingWindowLimiter(
        max_attempts=settings.login_rate_limit_max_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )

    # --- Security headers ----------------------------------------------
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)

    # --- CSRF (double-submit, ADR-0019) --------------------------------
    app.add_middleware(CsrfMiddleware, settings=settings)

    # --- CORS ----------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
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
    app.include_router(schedules_crud_api.router)
    app.include_router(push_api.router)
    app.include_router(reminders_api.router)
    app.include_router(users_api.router)
    app.include_router(adherence_api.router)

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
            next_available_at=exc.next_available_at,
            slots_used=exc.slots_used,
            slots_total=exc.slots_total,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(DailyCapReachedError)
    async def _daily_cap_handler(
        _request: Request, exc: DailyCapReachedError
    ) -> JSONResponse:
        body = DailyCapViolation(
            code="daily_cap_reached",
            medication_id=exc.medication_id,
            max_per_day=exc.max_per_day,
            count_today=exc.count_today,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(MedicationInteractionConflictError)
    async def _interaction_conflict_handler(
        _request: Request, exc: MedicationInteractionConflictError
    ) -> JSONResponse:
        latest = max(exc.conflict.conflicts, key=lambda c: c.cooldown_elapses_at)
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

    # --- Static frontend (single-service deploy, ADR-0017) -------------
    # Mounted LAST so the API routers and /healthz match first; only
    # unmatched paths fall through to the SPA.  Skipped entirely when no
    # build is configured (dev/tests), leaving the API surface unchanged.
    if settings.frontend_dist is not None:
        dist = Path(settings.frontend_dist)
        if dist.is_dir():
            app.mount(
                "/",
                _SPAStaticFiles(directory=dist, html=True),
                name="spa",
            )

    return app
