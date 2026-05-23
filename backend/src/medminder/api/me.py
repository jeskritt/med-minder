"""Current-user router: ``GET /me``, ``PATCH /me``, ``POST /me/password``."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import (
    cookie_serializer,
    get_current_user,
    get_session,
    get_settings,
    set_session_cookie,
)
from medminder.db.models import User
from medminder.domain.sessions import create_session
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
