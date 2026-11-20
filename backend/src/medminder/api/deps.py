"""Request-scoped FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medminder.api.csrf import issue_csrf_token
from medminder.db.models import User
from medminder.domain.rate_limit import LoginRateLimiter, SlidingWindowLimiter
from medminder.domain.sessions import SESSION_LIFETIME, authenticate_token
from medminder.settings import Settings

_COOKIE_SALT = "mm_session"


def cookie_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Build the ``itsdangerous`` serializer used to sign session cookies."""
    return URLSafeTimedSerializer(settings.session_secret, salt=_COOKIE_SALT)


def get_login_rate_limiter(request: Request) -> LoginRateLimiter:
    """Return the process-local login rate limiter bound to the app."""
    limiter: LoginRateLimiter = request.app.state.login_rate_limiter
    return limiter


def get_password_change_rate_limiter(request: Request) -> SlidingWindowLimiter:
    """Return the process-local password-change rate limiter bound to the app."""
    limiter: SlidingWindowLimiter = request.app.state.password_change_rate_limiter
    return limiter


def get_settings(request: Request) -> Settings:
    """Return the ``Settings`` instance bound to the running app."""
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request DB session inside a single transaction (commit on success)."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        async with session.begin():
            yield session


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
    )


def set_session_cookie(
    response: Response,
    *,
    signed_value: str,
    settings: Settings,
) -> None:
    """Write a fresh ``mm_session`` cookie with the rolling Max-Age."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=signed_value,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def set_csrf_cookie(response: Response, *, token: str, settings: Settings) -> None:
    """Write the non-HttpOnly ``mm_csrf`` cookie for the double-submit check.

    Readable by JS by design (ADR-0019): the SPA echoes it in the
    ``X-CSRF-Token`` header.  Shares the session cookie's ``SameSite`` /
    ``Secure`` posture.
    """
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=False,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    """Write a clearing cookie that overrides any live session cookie."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value="",
        max_age=0,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def clear_csrf_cookie(response: Response, *, settings: Settings) -> None:
    """Write a clearing cookie that removes any live CSRF cookie."""
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value="",
        max_age=0,
        httponly=False,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


async def get_current_user(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> User:
    """Validate the ``mm_session`` cookie, refresh its Max-Age, return the user.

    Raises 401 with a generic body for any failure mode (missing /
    tampered / expired) — both FR-007 and FR-008 lean on this dep.
    """
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if cookie_value is None or cookie_value == "":
        raise _unauthorized()
    try:
        token = cookie_serializer(settings).loads(cookie_value)
    except BadSignature:
        raise _unauthorized() from None
    if not isinstance(token, str):
        raise _unauthorized()
    user = await authenticate_token(db, plaintext_token=token)
    if user is None:
        raise _unauthorized()
    set_session_cookie(response, signed_value=cookie_value, settings=settings)
    # Self-heal the CSRF cookie if a logged-in client somehow lacks one
    # (e.g. it expired or predates the feature) — ADR-0019.
    if request.cookies.get(settings.csrf_cookie_name) is None:
        set_csrf_cookie(response, token=issue_csrf_token(), settings=settings)
    return user


async def require_admin(
    user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    """Authorize the caller as an admin, or raise 403.

    Server-side gate for the entire ``/api/v1/users`` surface (FR-001) — the
    control does not depend on the UI hiding the nav entry. An unauthenticated
    caller already gets 401 from ``get_current_user``; an authenticated
    non-admin gets a generic 403 here.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user
