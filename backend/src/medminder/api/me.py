"""Current-user router: ``GET /me``, ``PATCH /me``, ``POST /me/password``."""

from __future__ import annotations

import uuid
from datetime import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import (
    cookie_serializer,
    get_current_user,
    get_session,
    get_settings,
    set_session_cookie,
)
from medminder.db.models import User
from medminder.domain.reminder_dispatch import regenerate_user_reminders
from medminder.domain.sessions import create_session
from medminder.domain.timezone import InvalidTimezoneError, normalize_timezone
from medminder.domain.users import (
    IncorrectPasswordError,
    PasswordTooShortError,
    change_own_password,
    update_user,
)
from medminder.settings import Settings

router = APIRouter(tags=["me"])


class Me(BaseModel):
    """Public view of the authenticated user (contract ``Me``)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    name: str
    role: Literal["admin", "user"]
    # ``timezone`` is self-service via ``PUT /me/timezone`` (and still
    # CLI-settable); quiet hours via ``PUT /me/quiet-hours`` (both columns
    # NULL when off). The picker also reads ``timezone`` to label those inputs.
    timezone: str
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class ProfileUpdate(BaseModel):
    """Inbound body for ``PATCH /me`` — display name only (FR-007/FR-010)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _trim_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must not be blank.")
        return trimmed


class QuietHoursUpdate(BaseModel):
    """Inbound body for ``PUT /me/quiet-hours`` — self-service quiet window.

    Quiet hours are an all-or-nothing pair: dose dispatch only defers when
    *both* bounds are set (``domain.reminders.defer_for_quiet_hours``), and a
    zero-length ``[start, start)`` window would never fire, so we reject both
    the one-sided and the equal cases here. Sending both ``null`` clears the
    window (quiet hours off). Pydantic coerces ``"22:00"`` → ``time``; a
    malformed value surfaces as 422.
    """

    model_config = ConfigDict(extra="forbid")

    start: time | None = None
    end: time | None = None

    @model_validator(mode="after")
    def _both_or_neither(self) -> QuietHoursUpdate:
        if (self.start is None) != (self.end is None):
            raise ValueError("Set both start and end, or neither.")
        if self.start is not None and self.start == self.end:
            raise ValueError("Start and end must differ.")
        return self


class TimezoneUpdate(BaseModel):
    """Inbound body for ``PUT /me/timezone`` — self-service IANA timezone.

    The value must be a zone known to the system tz database; an unknown or
    malformed name is rejected here (422) so the column never holds something
    the deferral / today-bounds math can't resolve later.
    """

    model_config = ConfigDict(extra="forbid")

    timezone: str = Field(min_length=1)

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            return normalize_timezone(value)
        except InvalidTimezoneError as exc:
            raise ValueError(f"Unknown timezone {value!r}.") from exc


class PasswordChange(BaseModel):
    """Inbound body for ``POST /me/password``.

    The 12-char minimum is intentionally *not* encoded here — it stays in
    ``domain.passwords`` (``MIN_PASSWORD_LENGTH``) so the rule is shared with
    the CLI and login and surfaces the same message (FR-004).
    """

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


@router.get("/me", response_model=Me)
async def get_me(user: User = Depends(get_current_user)) -> User:  # noqa: B008
    """Return the authenticated user's id / name / role.

    Cookie ``Max-Age`` is refreshed by ``get_current_user`` (FR-003 +
    FR-009).
    """
    return user


@router.patch("/me", response_model=Me)
async def update_me(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Update the authenticated user's display name (no session effects).

    Reuses the shared ``update_user`` domain helper, scoped to the caller's
    own email — there is no path to rename another user (FR-006/FR-009).
    """
    return await update_user(db, email=user.email, new_name=body.name)


@router.put("/me/quiet-hours", response_model=Me)
async def update_quiet_hours(
    body: QuietHoursUpdate,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Set or clear the caller's own quiet-hours window (no session effects).

    Both bounds set → store them; both ``null`` → clear the window. The
    ``QuietHoursUpdate`` validator has already enforced both-or-neither, so
    here it's a clean branch into the shared ``update_user`` helper, scoped to
    the caller's own email.
    """
    if body.start is None:
        return await update_user(db, email=user.email, clear_quiet_hours=True)
    return await update_user(
        db,
        email=user.email,
        new_quiet_hours_start=body.start,
        new_quiet_hours_end=body.end,
    )


@router.put("/me/timezone", response_model=Me)
async def update_timezone(
    body: TimezoneUpdate,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Set the caller's own IANA timezone and re-sync future dose reminders.

    ``TimezoneUpdate`` has already validated the zone against the tz database,
    so this updates the user's zone via ``update_user`` and regenerates their
    future ``pending`` dose reminders so already-materialised slots don't keep
    firing at the old UTC offset (or duplicate).
    """
    updated = await update_user(db, email=user.email, new_timezone=body.timezone)
    await regenerate_user_reminders(db, user_id=updated.id)
    return updated


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    """Change the caller's password, then re-issue a fresh session cookie.

    ``change_own_password`` verifies the current password, sets the new hash,
    and revokes *all* of the user's sessions. We then mint a new session for
    this device and set its cookie (mirrors ``POST /auth/login``), so the
    current device stays signed in while other devices are logged out (FR-005).
    """
    try:
        await change_own_password(
            db,
            user=user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except IncorrectPasswordError as exc:
        # 403 — distinct from 422 (too-short) and never 401 (which the client
        # treats as session-expired and bounces to /login). (FR-003)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current password is incorrect.",
        ) from exc
    except PasswordTooShortError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    _row, plaintext_token = await create_session(db, user_id=user.id)
    signed_value: str = cookie_serializer(settings).dumps(plaintext_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, signed_value=signed_value, settings=settings)
    return response
