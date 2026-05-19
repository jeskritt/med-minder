"""Interaction-rule management (Phase 6 / US3).

`/api/v1/medications/{medication_id}/interactions` — **create, list,
delete only** (no update; the clarified scope is delete-then-recreate).
Scoped to the logged-in user's own non-deleted medications
(cross-user isolation FR-019; boundary validation FR-020). The
unordered-pair uniqueness, positive-cooldown, and distinct-pair
invariants are enforced by the database (Phase 1 constraints); this
router validates ownership and maps constraint violations to status
codes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.api.schemas.interactions import (
    InteractionRuleCreate,
    InteractionRuleOut,
)
from medminder.db.models import Medication, MedicationInteraction, User

router = APIRouter(
    prefix="/api/v1/medications/{medication_id}/interactions",
    tags=["interactions"],
)


async def _owned_medication(
    db: AsyncSession, *, user: User, medication_id: uuid.UUID
) -> Medication:
    med = (
        await db.execute(
            select(Medication).where(
                Medication.id == medication_id,
                Medication.user_id == user.id,
                Medication.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if med is None:
        # 404 (not 403) — no existence leak for other users' / unknown ids.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    return med


def _to_out(
    rule: MedicationInteraction,
    *,
    medication_id: uuid.UUID,
    other_name: str,
) -> InteractionRuleOut:
    other_id = (
        rule.conflicting_medication_id
        if rule.medication_id == medication_id
        else rule.medication_id
    )
    return InteractionRuleOut(
        id=rule.id,
        medication_id=medication_id,
        conflicting_medication_id=other_id,
        conflicting_medication_name=other_name,
        cooldown_minutes=rule.cooldown_minutes,
        created_at=rule.created_at,
    )


@router.get("", response_model=list[InteractionRuleOut])
async def list_rules(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[InteractionRuleOut]:
    """Every rule involving this medication (matched in either order)."""
    await _owned_medication(db, user=user, medication_id=medication_id)
    rules = list(
        (
            await db.execute(
                select(MedicationInteraction).where(
                    or_(
                        MedicationInteraction.medication_id == medication_id,
                        MedicationInteraction.conflicting_medication_id
                        == medication_id,
                    )
                )
            )
        ).scalars()
    )
    if not rules:
        return []
    other_ids = {
        (
            r.conflicting_medication_id
            if r.medication_id == medication_id
            else r.medication_id
        )
        for r in rules
    }
    name_rows = (
        await db.execute(
            select(Medication.id, Medication.name).where(
                Medication.id.in_(other_ids),
                Medication.user_id == user.id,
                Medication.deleted_at.is_(None),
            )
        )
    ).all()
    names: dict[uuid.UUID, str] = {}
    for mid, name in name_rows:
        names[mid] = name
    return [
        _to_out(
            r,
            medication_id=medication_id,
            other_name=names[oid],
        )
        for r in rules
        if (
            oid := (
                r.conflicting_medication_id
                if r.medication_id == medication_id
                else r.medication_id
            )
        )
        in names
    ]


@router.post(
    "",
    response_model=InteractionRuleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    medication_id: uuid.UUID,
    payload: InteractionRuleCreate,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> InteractionRuleOut:
    """Create a symmetric rule for the unordered pair."""
    await _owned_medication(db, user=user, medication_id=medication_id)
    if payload.other_medication_id == medication_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A medication cannot conflict with itself.",
        )
    other = await _owned_medication(
        db, user=user, medication_id=payload.other_medication_id
    )
    rule = MedicationInteraction(
        medication_id=medication_id,
        conflicting_medication_id=other.id,
        cooldown_minutes=payload.cooldown_minutes,
    )
    db.add(rule)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rule already exists for this medication pair.",
        ) from exc
    await db.refresh(rule)
    return _to_out(
        rule, medication_id=medication_id, other_name=other.name
    )


@router.delete(
    "/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_rule(
    medication_id: uuid.UUID,
    interaction_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Remove a rule the user owns that involves this medication."""
    await _owned_medication(db, user=user, medication_id=medication_id)
    rule = (
        await db.execute(
            select(MedicationInteraction).where(
                MedicationInteraction.id == interaction_id,
                or_(
                    MedicationInteraction.medication_id == medication_id,
                    MedicationInteraction.conflicting_medication_id
                    == medication_id,
                ),
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    # The path medication is owned (checked above); the pair's other
    # side is also the user's own by construction (create enforces it).
    await db.delete(rule)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
