"""Wire-format schemas for drug-interaction cooldowns (Phase 6).

Pydantic v2 models matching
``specs/006-drug-interaction-cooldowns/contracts/interactions.openapi.yaml``.
The domain ``InteractionConflict`` lives in
``medminder.domain.interactions``; the adapter
``to_interaction_state_out`` is the only crossing of that boundary
(keeps the domain free of pydantic), mirroring
``api.schemas.timers.to_timer_state_out``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from medminder.api.schemas.errors import ConflictOut
from medminder.domain import interactions as domain_interactions


class InteractionStateOut(BaseModel):
    """Read-surface interaction state for a medication (FR-011/FR-012).

    ``null`` at the API boundary when no conflict is currently active;
    when present the client seeds its local counter from ``as_of`` and
    ticks ``remaining_seconds`` down without polling (FR-013).
    """

    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    conflicts: list[ConflictOut] = Field(min_length=1)
    cooldown_elapses_at: datetime
    remaining_seconds: int = Field(ge=0)


class InteractionRuleCreate(BaseModel):
    """Inbound payload to create a symmetric interaction rule (US3)."""

    model_config = ConfigDict(extra="forbid")

    other_medication_id: uuid.UUID
    cooldown_minutes: int = Field(ge=1)


class InteractionRuleOut(BaseModel):
    """One interaction rule involving the queried medication (US3)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    medication_id: uuid.UUID
    conflicting_medication_id: uuid.UUID
    conflicting_medication_name: str
    cooldown_minutes: int = Field(ge=1)
    created_at: datetime


def to_interaction_state_out(
    conflict: domain_interactions.InteractionConflict | None,
) -> InteractionStateOut | None:
    """Convert a domain ``InteractionConflict`` to its wire form.

    Returns ``None`` when ``conflict is None`` so callers can pass a
    non-conflicting medication through verbatim. The headline
    ``cooldown_elapses_at`` / ``remaining_seconds`` reflect the
    latest-ending active conflict (FR-009 / US2.6).
    """
    if conflict is None:
        return None
    latest = max(conflict.conflicts, key=lambda c: c.cooldown_elapses_at)
    return InteractionStateOut(
        as_of=conflict.as_of,
        conflicts=[
            ConflictOut(
                conflicting_medication_id=c.conflicting_medication_id,
                conflicting_medication_name=c.conflicting_medication_name,
                cooldown_elapses_at=c.cooldown_elapses_at,
                remaining_seconds=c.remaining_seconds,
            )
            for c in conflict.conflicts
        ],
        cooldown_elapses_at=latest.cooldown_elapses_at,
        remaining_seconds=latest.remaining_seconds,
    )


__all__ = [
    "InteractionRuleCreate",
    "InteractionRuleOut",
    "InteractionStateOut",
    "to_interaction_state_out",
]
