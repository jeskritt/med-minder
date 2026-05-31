"""CSRF double-submit protection (Phase 10 hardening, ADR-0019).

Defense-in-depth on top of the same-origin deployment (ADR-0017) and the
``SameSite=Lax`` session cookie.  A non-HttpOnly ``mm_csrf`` cookie is issued
alongside the session; the SPA echoes it in an ``X-CSRF-Token`` header on every
unsafe request and this middleware requires header == cookie (constant-time).

Exemptions:

* Safe methods (GET/HEAD/OPTIONS/TRACE) — no state change.
* ``/auth/login`` (pre-auth: no session to protect) and ``/auth/logout``
  (idempotent, clears only the caller's own cookie).
* ``/healthz``, ``/docs``, ``/openapi.json``, ``/redoc`` (GET surfaces).
* The two service-worker notification-action endpoints
  (``/api/v1/reminders/{id}/snooze`` and ``/take``): a service worker cannot
  read ``document.cookie`` on every browser, so it sends the header only when
  the Cookie Store API is available.  ``SameSite=Lax`` already blocks the
  cross-site POST that CSRF would need, so exempting these two self-only
  mutations leaves no practical hole (ADR-0019).
"""

from __future__ import annotations

import re
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from medminder.settings import Settings

CSRF_HEADER_NAME = "x-csrf-token"
_TOKEN_NBYTES = 32

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_EXEMPT_PATHS = frozenset(
    {"/healthz", "/auth/login", "/auth/logout", "/docs", "/openapi.json", "/redoc"}
)
_REMINDER_ACTION_RE = re.compile(r"^/api/v1/reminders/[^/]+/(snooze|take)$")


def issue_csrf_token() -> str:
    """Mint a fresh CSRF token (URL-safe, ≥ 256 bits of entropy)."""
    return secrets.token_urlsafe(_TOKEN_NBYTES)


class CsrfMiddleware(BaseHTTPMiddleware):
    """Reject unsafe requests whose ``X-CSRF-Token`` header doesn't match the cookie."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    def _is_exempt(self, request: Request) -> bool:
        if not self._settings.csrf_protection_enabled:
            return True
        if request.method in _SAFE_METHODS:
            return True
        path = request.url.path
        if path in _EXEMPT_PATHS:
            return True
        return bool(_REMINDER_ACTION_RE.match(path))

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self._is_exempt(request):
            return await call_next(request)
        cookie = request.cookies.get(self._settings.csrf_cookie_name)
        header = request.headers.get(CSRF_HEADER_NAME)
        if not cookie or not header or not secrets.compare_digest(cookie, header):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid."},
            )
        return await call_next(request)


__all__ = ["CSRF_HEADER_NAME", "CsrfMiddleware", "issue_csrf_token"]
