"""Current-user router: ``GET /me``."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from medminder.api.deps import get_current_user
from medminder.db.models import User

router = APIRouter(tags=["me"])


class Me(BaseModel):
    """Public view of the authenticated user (contract ``Me``)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    name: str
    role: Literal["admin", "user"]


@router.get("/me", response_model=Me)
async def get_me(user: User = Depends(get_current_user)) -> User:  # noqa: B008
    """Return the authenticated user's id / name / role.

    Cookie ``Max-Age`` is refreshed by ``get_current_user`` (FR-003 +
    FR-009).
    """
    return user
