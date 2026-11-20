"""Security response-headers middleware (Phase 10 hardening).

Adds defensive headers to every response.  ``Strict-Transport-Security``
is emitted only outside development (gated by ``session_cookie_secure``,
which is the same HTTPS-only signal used for the session cookie) so the
HTTP dev server is unaffected.  The Content-Security-Policy is deliberately
conservative: it covers the Vite-built SPA served same-origin in production
(ADR-0017) without inline scripts.  ``style-src`` keeps ``'unsafe-inline'``
because component styles still emit inline ``style`` attributes — tightening
that further needs a build-time nonce and is out of scope here.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from medminder.settings import Settings

_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)


_NO_STORE_PREFIXES = ("/api/", "/auth/", "/me/")


def _is_sensitive_path(path: str) -> bool:
    return path == "/me" or path.startswith(_NO_STORE_PREFIXES)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive security headers to every response."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        # ``setdefault`` so a handler that sets its own value (rare) wins.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", _CONTENT_SECURITY_POLICY)
        if _is_sensitive_path(request.url.path):
            # Medication records, auth responses, and one-time temp passwords
            # must never be persisted in browser or intermediary HTTP caches.
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")
        if self._settings.session_cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response


__all__ = ["SecurityHeadersMiddleware"]
