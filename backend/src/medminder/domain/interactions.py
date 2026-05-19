"""Drug-interaction cooldown detection (Phase 6).

Pure Python: no sqlalchemy, no fastapi imports at runtime (mirrors
``medminder.domain.timers``). The detector is order-independent and
honours the symmetric single-row rule (matched in either direction);
it never raises. ``create_dose`` decides whether to raise
:class:`MedicationInteractionConflictError`; the warning surface consumes
the same :class:`InteractionConflict` value object read-only. The
conversion to wire-format Pydantic models lives in
``medminder.api.schemas.interactions``.

Enforcement model: ADR-0008 (warn + explicit confirm + audited
override; always overridable; distinct from the non-overridable
Phase 5 overdose 409s). :class:`MedicationInteractionConflictError` is a
plain ``Exception`` carried to the FastAPI 409 handler exactly like
``MinIntervalNotElapsedError`` / ``WindowFullError`` in
``domain.timers`` — it is intentionally *not* a ``DoseError``
subclass, so this module stays self-contained (no ``domain.doses``
import, no circular import).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from medminder.db.models import MedicationInteraction


@dataclass(frozen=True)
class ConflictItem:
    """One currently-active conflict against a prospective dose."""

    conflicting_medication_id: uuid.UUID
    conflicting_medication_name: str
    armed_dose_taken_at: datetime
    cooldown_elapses_at: datetime
    remaining_seconds: int


@dataclass(frozen=True)
class InteractionConflict:
    """Detector output: every active conflict for one medication.

    ``conflicts`` is non-empty whenever this object exists; the absence
    of a conflict is represented by the detector returning ``None``.
    """

    as_of: datetime
    conflicts: list[ConflictItem]


class MedicationInteractionConflictError(Exception):
    """Raised by ``create_dose`` for an unacknowledged active conflict.

    Plain ``Exception`` (sibling of ``MinIntervalNotElapsedError`` /
    ``WindowFullError``); the ``app.py`` handler maps it to HTTP 409
    with the ``InteractionCooldownViolation`` body. Always overridable
    via ``interaction_acknowledged`` (ADR-0008).
    """

    def __init__(
        self,
        *,
        medication_id: uuid.UUID,
        conflict: InteractionConflict,
    ) -> None:
        super().__init__(
            f"Active drug-interaction cooldown for medication "
            f"{medication_id}: {len(conflict.conflicts)} conflict(s)."
        )
        self.medication_id = medication_id
        self.conflict = conflict


def _partner_id(
    rule: MedicationInteraction, medication_id: uuid.UUID
) -> uuid.UUID | None:
    """Return the *other* side of a symmetric rule, or ``None`` if the
    rule does not involve ``medication_id``."""
    if rule.medication_id == medication_id:
        return rule.conflicting_medication_id
    if rule.conflicting_medication_id == medication_id:
        return rule.medication_id
    return None


def detect_interaction_conflict(
    *,
    medication_id: uuid.UUID,
    rules: list[MedicationInteraction],
    partner_last_non_voided: Mapping[uuid.UUID, datetime],
    medication_names: Mapping[uuid.UUID, str],
    prospective_taken_at: datetime,
    now: datetime,
) -> InteractionConflict | None:
    """Detect active interaction conflicts for a prospective dose.

    For each rule that involves ``medication_id`` (matched in either
    order), the partner medication arms a cooldown iff its most-recent
    non-voided dose ``armed`` satisfies
    ``armed + cooldown_minutes > prospective_taken_at`` (boundary
    exclusive, consistent with the Phase 5 timer boundary). Soft-deleted
    partners are excluded by the caller (absent from
    ``medication_names`` / ``partner_last_non_voided``) and therefore
    never produce a conflict (FR-018).

    Pure and order-independent; never raises. Returns ``None`` when no
    conflict is active. ``remaining_seconds`` is measured from ``now``
    (the display clock) and clamped at zero; the headline values are
    taken from the latest-ending active conflict (FR-009 / US2.6).
    """
    conflicts: list[ConflictItem] = []
    seen_partners: set[uuid.UUID] = set()
    for rule in rules:
        partner = _partner_id(rule, medication_id)
        if partner is None or partner in seen_partners:
            continue
        seen_partners.add(partner)
        armed = partner_last_non_voided.get(partner)
        name = medication_names.get(partner)
        if armed is None or name is None:
            continue
        elapses_at = armed + timedelta(minutes=rule.cooldown_minutes)
        if elapses_at > prospective_taken_at:
            remaining = max(0, int((elapses_at - now).total_seconds()))
            conflicts.append(
                ConflictItem(
                    conflicting_medication_id=partner,
                    conflicting_medication_name=name,
                    armed_dose_taken_at=armed,
                    cooldown_elapses_at=elapses_at,
                    remaining_seconds=remaining,
                )
            )
    if not conflicts:
        return None
    return InteractionConflict(as_of=now, conflicts=conflicts)


__all__ = [
    "ConflictItem",
    "InteractionConflict",
    "MedicationInteractionConflictError",
    "detect_interaction_conflict",
]
