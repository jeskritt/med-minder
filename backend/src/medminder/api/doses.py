"""``POST /api/doses`` and ``POST /api/doses/{dose_id}/void``."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.api.schemas.doses import DoseCreate, DoseRead
from medminder.api.schemas.errors import (
    InteractionCooldownViolation,
    MinIntervalViolation,
    WindowFullViolation,
)
from medminder.db.models import User
from medminder.domain.doses import (
    DoseAlreadyVoidedError,
    DoseForbiddenError,
    DoseNotFoundError,
    DoseValidationError,
    create_dose,
    void_dose,
)

router = APIRouter(prefix="/api/doses", tags=["doses"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DoseRead,
    responses={
        409: {
            "model": MinIntervalViolation
            | WindowFullViolation
            | InteractionCooldownViolation
        }
    },
)
async def post_dose(
    payload: DoseCreate,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DoseRead:
    """Record a medication-taken event."""
    try:
        dose = await create_dose(
            db,
            user=user,
            medication_id=payload.medication_id,
            schedule_id=payload.schedule_id,
            taken_at=payload.taken_at or datetime.now(UTC),
            quantity=payload.quantity,
            interaction_acknowledged=payload.interaction_acknowledged,
        )
    except DoseForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except DoseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return DoseRead.model_validate(dose)


@router.post(
    "/{dose_id}/void",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def post_dose_void(
    dose_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Record a compensating un-take row in ``dose_voids``."""
    try:
        await void_dose(db, user=user, dose_id=dose_id)
    except (DoseNotFoundError, DoseForbiddenError) as exc:
        # Fold missing and cross-user into 404 to avoid an existence oracle
        # (consistent with medications, schedules, reminders, interactions).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        ) from exc
    except DoseAlreadyVoidedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
