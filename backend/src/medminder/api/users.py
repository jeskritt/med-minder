"""Admin user-management router — ``/api/v1/users`` (FR-001..FR-016).

Every route is gated by ``require_admin`` (an authenticated non-admin gets 403,
an unauthenticated caller 401). The endpoints are thin transport over the
shared user domain (``domain.users``) so in-app and CLI behaviour cannot
diverge (FR-012); each successful action also appends one ``admin_audit_log``
row via ``record_admin_action`` (FR-013).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_session, require_admin
from medminder.db.models import User
from medminder.domain.audit import record_admin_action
from medminder.domain.passwords import generate_temp_password
from medminder.domain.users import (
    DuplicateEmailError,
    PasswordTooShortError,
    create_user,
    list_users,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])

Role = Literal["admin", "user"]


class UserOut(BaseModel):
    """Public view of a user row (contract ``UserOut``)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: Role
    created_at: datetime


class UserListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UserOut]


class UserCreate(BaseModel):
    """Create body — provide exactly one of ``password`` / ``generate``.

    The 12-char minimum on a typed password is enforced server-side in
    ``domain.passwords`` (single source of truth) → 422; it is intentionally
    not re-encoded here.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)
    name: str = Field(min_length=1, max_length=100)
    role: Role
    password: str | None = Field(default=None, max_length=1024)
    generate: bool = False

    @model_validator(mode="after")
    def _exactly_one_password_source(self) -> UserCreate:
        if (self.password is not None) == self.generate:
            raise ValueError(
                "Provide exactly one of 'password' or 'generate'."
            )
        return self


class CreatedUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserOut
    # Present (shown once) only when ``generate`` was true.
    temporary_password: str | None = None


@router.get("", response_model=UserListOut)
async def admin_list_users(
    _admin: User = Depends(require_admin),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserListOut:
    """List active (non-deactivated) users, oldest first (FR-002)."""
    users = await list_users(db)
    return UserListOut(items=[UserOut.model_validate(u) for u in users])


@router.post("", response_model=CreatedUser, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: UserCreate,
    admin: User = Depends(require_admin),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> CreatedUser:
    """Create a user with a typed or generated temp password (FR-003/FR-004).

    A generated password is returned once in ``temporary_password`` and never
    stored or logged in plaintext. No forced-rotation flag is set (FR-018).
    """
    temp: str | None = generate_temp_password() if body.generate else None
    password = temp if temp is not None else body.password
    assert password is not None  # guaranteed by UserCreate validator
    try:
        user = await create_user(
            db,
            email=body.email,
            name=body.name,
            role=body.role,
            password=password,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except PasswordTooShortError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    await record_admin_action(
        db,
        actor_id=admin.id,
        action="create",
        target_user_id=user.id,
        details={"fields": ["email", "name", "role"]},
    )
    return CreatedUser(
        user=UserOut.model_validate(user), temporary_password=temp
    )
