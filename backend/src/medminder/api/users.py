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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_session, require_admin
from medminder.db.models import AdminAuditLog, User
from medminder.db.models.admin_audit import AdminAuditAction
from medminder.domain.audit import record_admin_action
from medminder.domain.passwords import generate_temp_password
from medminder.domain.users import (
    DuplicateEmailError,
    LastAdminError,
    PasswordTooShortError,
    SelfActionError,
    UserNotFoundError,
    admin_deactivate_user,
    admin_reset_password,
    admin_update_user,
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


class UserUpdate(BaseModel):
    """Edit body — at least one of name/email/role (password is reset
    separately).  ``extra`` forbidden so an unknown field is a 422 (FR-023)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=320)
    role: Role | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> UserUpdate:
        if self.name is None and self.email is None and self.role is None:
            raise ValueError("Provide at least one of name, email, or role.")
        return self


class PasswordSet(BaseModel):
    """Reset body — provide exactly one of ``password`` / ``generate``."""

    model_config = ConfigDict(extra="forbid")

    password: str | None = Field(default=None, max_length=1024)
    generate: bool = False

    @model_validator(mode="after")
    def _exactly_one_password_source(self) -> PasswordSet:
        if (self.password is not None) == self.generate:
            raise ValueError("Provide exactly one of 'password' or 'generate'.")
        return self


class PasswordResetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Present (shown once) only when ``generate`` was true.
    temporary_password: str | None = None


class AuditEntryOut(BaseModel):
    """One audit-trail row (contract ``AuditEntryOut``)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    # Null for actions performed via the admin CLI, which has no authenticated
    # principal (the ``details`` carry ``"via": "cli"``); ADR-0014 / G7.
    actor_id: uuid.UUID | None
    target_user_id: uuid.UUID
    action: AdminAuditAction
    details: dict[str, object]
    created_at: datetime


class AuditListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEntryOut]


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
    if password is None:  # unreachable: UserCreate validator guarantees one of the two
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="password resolution failed",
        )
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


# Declared BEFORE the ``/{user_id}`` routes: ``audit-log`` is not a valid UUID,
# so FastAPI would 422 on the path param instead of falling through (it does
# not retry other routes on a validation failure).
@router.get("/audit-log", response_model=AuditListOut)
async def admin_list_audit_log(
    _admin: User = Depends(require_admin),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditListOut:
    """Read the admin-action audit trail, newest first (FR-014).

    Bounded by ``limit``/``offset`` (newest-first) so the response can't grow
    unbounded as the trail accumulates. Records only successful actions and
    never any secret values (FR-013); the table is append-only (FR-022) — there
    is intentionally no edit/delete route.
    """
    rows = (
        (
            await db.execute(
                select(AdminAuditLog)
                .order_by(AdminAuditLog.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return AuditListOut(items=[AuditEntryOut.model_validate(r) for r in rows])


@router.patch("/{user_id}", response_model=UserOut)
async def admin_edit_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    admin: User = Depends(require_admin),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserOut:
    """Edit a user's name/email/role (FR-006).

    Editing your own row here is refused (use the profile editor); demoting the
    last admin is refused. Password is changed via the password endpoint.
    """
    try:
        user = await admin_update_user(
            db,
            actor=admin,
            user_id=user_id,
            new_email=body.email,
            new_name=body.name,
            new_role=body.role,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SelfActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except (DuplicateEmailError, LastAdminError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Deactivate (soft-delete) a user and revoke their sessions (FR-008).

    Refused for your own account (403) and for the last remaining admin (409).
    There is no in-app restore (FR-016).
    """
    try:
        await admin_deactivate_user(db, actor=admin, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SelfActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except LastAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/password", response_model=PasswordResetOut)
async def admin_reset_user_password(
    user_id: uuid.UUID,
    body: PasswordSet,
    admin: User = Depends(require_admin),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> PasswordResetOut:
    """Reset a user's password and revoke their sessions (FR-007).

    Typed or generated (exactly one). A generated password is returned once.
    Resetting your own password here is refused (use the profile editor).
    """
    temp: str | None = generate_temp_password() if body.generate else None
    password = temp if temp is not None else body.password
    if password is None:  # unreachable: PasswordSet validator guarantees one of the two
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="password resolution failed",
        )
    try:
        await admin_reset_password(
            db, actor=admin, user_id=user_id, new_password=password
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SelfActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except PasswordTooShortError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return PasswordResetOut(temporary_password=temp)
