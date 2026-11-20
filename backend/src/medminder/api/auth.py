"""Auth router: ``POST /auth/login``, ``POST /auth/logout``."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.csrf import issue_csrf_token
from medminder.api.deps import (
    clear_csrf_cookie,
    clear_session_cookie,
    cookie_serializer,
    get_login_rate_limiter,
    get_session,
    get_settings,
    set_csrf_cookie,
    set_session_cookie,
)
from medminder.domain.auth import LoginOutcome, attempt_login
from medminder.domain.rate_limit import LoginRateLimiter
from medminder.domain.sessions import (
    create_session,
    delete_session_by_token_hash,
    hash_token,
)
from medminder.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_AUTH_FAILURE_DETAIL = "Email or password is incorrect."


class LoginRequest(BaseModel):
    """Inbound credentials for ``POST /auth/login`` (contract LoginRequest)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., max_length=320)
    password: str = Field(..., min_length=1, max_length=1024)


def _client_ip(request: Request, *, trusted_proxy_count: int = 0) -> str:
    """Server-derived source IP for the FR-019 audit log.

    When ``trusted_proxy_count`` is 0, we use the raw peer address.
    When > 0, we read the Nth-from-rightmost entry of
    ``X-Forwarded-For``, where N = ``trusted_proxy_count``.  This
    trusts only the entries appended by known reverse proxies
    (e.g. Koyeb) and ignores any client-injected prefix.
    """
    if trusted_proxy_count > 0:
        xff = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= trusted_proxy_count:
            return parts[-trusted_proxy_count]
    if request.client is None:
        return ""
    return request.client.host


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
    limiter: LoginRateLimiter = Depends(get_login_rate_limiter),  # noqa: B008
) -> Response:
    """Verify credentials, mint a session, set a signed cookie.

    Throttled per client IP and per email (ADR-0018): too many recent
    failures → 429 with ``Retry-After`` and an identical generic body for any
    email, so the limiter never leaks whether an account exists.  The check
    runs before any password verification, so it adds no crypto timing.
    """
    ip = _client_ip(request, trusted_proxy_count=settings.trusted_proxy_count)
    now = time.monotonic()
    if settings.login_rate_limit_enabled:
        retry_after = limiter.check(ip=ip, email=payload.email, now=now)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    user, outcome = await attempt_login(
        db,
        email=payload.email,
        password=payload.password,
        ip=ip,
        user_agent=request.headers.get("user-agent", ""),
    )

    if outcome is not LoginOutcome.SUCCESS or user is None:
        if settings.login_rate_limit_enabled:
            limiter.record_failure(ip=ip, email=payload.email, now=now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_AUTH_FAILURE_DETAIL,
        )

    if settings.login_rate_limit_enabled:
        limiter.reset(ip=ip, email=payload.email)

    # FR-016 / D9: only on success do we delete a pre-existing session
    # bound to the inbound cookie.  A failed login must not log the user
    # out.
    inbound = request.cookies.get(settings.session_cookie_name)
    if inbound:
        try:
            old_token = cookie_serializer(settings).loads(inbound)
        except BadSignature:
            old_token = None
        if isinstance(old_token, str):
            await delete_session_by_token_hash(db, token_hash=hash_token(old_token))

    _row, plaintext_token = await create_session(db, user_id=user.id)
    signed_value: str = cookie_serializer(settings).dumps(plaintext_token)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, signed_value=signed_value, settings=settings)
    # Pair the new session with a fresh CSRF token (ADR-0019) so the SPA can
    # make its first mutation right after login.
    set_csrf_cookie(response, token=issue_csrf_token(), settings=settings)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    """Best-effort: delete the matching session row and clear the cookie.

    Idempotent (FR-006) — repeated calls still return 204 with the
    clearing cookie.  A tampered or missing cookie is treated as a
    no-op success; the response always clears any cookie the client
    may have.
    """
    inbound = request.cookies.get(settings.session_cookie_name)
    if inbound:
        try:
            token = cookie_serializer(settings).loads(inbound)
        except BadSignature:
            token = None
        if isinstance(token, str):
            await delete_session_by_token_hash(db, token_hash=hash_token(token))

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings=settings)
    clear_csrf_cookie(response, settings=settings)
    return response
