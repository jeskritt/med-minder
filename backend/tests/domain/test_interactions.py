"""Pure-function tests for the drug-interaction detector (Phase 6).

No DB / no session — ``detect_interaction_conflict`` is pure. Targets
≥95% line coverage of ``medminder.domain.interactions`` (SC-009).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from medminder.api.schemas.interactions import to_interaction_state_out
from medminder.db.models import MedicationInteraction
from medminder.domain.interactions import (
    detect_interaction_conflict,
)


def _rule(
    med_id: uuid.UUID, other_id: uuid.UUID, cooldown_minutes: int = 120
) -> MedicationInteraction:
    # In-memory only — never added to a session.
    return MedicationInteraction(
        medication_id=med_id,
        conflicting_medication_id=other_id,
        cooldown_minutes=cooldown_minutes,
    )


def test_no_rules_returns_none() -> None:
    now = datetime.now(UTC)
    assert (
        detect_interaction_conflict(
            medication_id=uuid.uuid4(),
            rules=[],
            partner_last_non_voided={},
            medication_names={},
            prospective_taken_at=now,
            now=now,
        )
        is None
    )


def test_first_dose_of_pair_never_warns() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    # Rule exists but the partner (A) has no recorded dose yet.
    assert (
        detect_interaction_conflict(
            medication_id=b,
            rules=[_rule(a, b)],
            partner_last_non_voided={},
            medication_names={a: "A"},
            prospective_taken_at=now,
            now=now,
        )
        is None
    )


def test_active_conflict_detected_with_fields() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    armed = now - timedelta(minutes=10)
    conflict = detect_interaction_conflict(
        medication_id=b,
        rules=[_rule(a, b, cooldown_minutes=120)],
        partner_last_non_voided={a: armed},
        medication_names={a: "Sumatriptan"},
        prospective_taken_at=now,
        now=now,
    )
    assert conflict is not None
    assert len(conflict.conflicts) == 1
    item = conflict.conflicts[0]
    assert item.conflicting_medication_id == a
    assert item.conflicting_medication_name == "Sumatriptan"
    assert item.cooldown_elapses_at == armed + timedelta(minutes=120)
    # ~110 minutes remaining = 6600s
    assert 6590 <= item.remaining_seconds <= 6600


def test_symmetry_single_row_matches_either_order() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    armed = now - timedelta(minutes=5)
    rule = _rule(a, b, cooldown_minutes=60)  # stored as (A, B)
    # Ask about A; partner is B.
    conflict = detect_interaction_conflict(
        medication_id=a,
        rules=[rule],
        partner_last_non_voided={b: armed},
        medication_names={b: "B"},
        prospective_taken_at=now,
        now=now,
    )
    assert conflict is not None
    assert conflict.conflicts[0].conflicting_medication_id == b


def test_boundary_is_exclusive() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    armed = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    cooldown = 120
    elapses = armed + timedelta(minutes=cooldown)
    # Exactly at the boundary → NOT active.
    assert (
        detect_interaction_conflict(
            medication_id=b,
            rules=[_rule(a, b, cooldown)],
            partner_last_non_voided={a: armed},
            medication_names={a: "A"},
            prospective_taken_at=elapses,
            now=elapses,
        )
        is None
    )
    # One second inside → active.
    just_inside = elapses - timedelta(seconds=1)
    assert (
        detect_interaction_conflict(
            medication_id=b,
            rules=[_rule(a, b, cooldown)],
            partner_last_non_voided={a: armed},
            medication_names={a: "A"},
            prospective_taken_at=just_inside,
            now=just_inside,
        )
        is not None
    )


def test_expired_cooldown_returns_none() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    armed = now - timedelta(minutes=200)  # cooldown 120 → long expired
    assert (
        detect_interaction_conflict(
            medication_id=b,
            rules=[_rule(a, b, 120)],
            partner_last_non_voided={a: armed},
            medication_names={a: "A"},
            prospective_taken_at=now,
            now=now,
        )
        is None
    )


def test_soft_deleted_partner_excluded() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    armed = now - timedelta(minutes=1)
    # Partner has a recent dose but is absent from medication_names
    # (caller excludes soft-deleted / cross-user) → no conflict (FR-018).
    assert (
        detect_interaction_conflict(
            medication_id=b,
            rules=[_rule(a, b, 120)],
            partner_last_non_voided={a: armed},
            medication_names={},
            prospective_taken_at=now,
            now=now,
        )
        is None
    )


def test_multi_conflict_all_listed_and_remaining_clamped() -> None:
    b, a, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    # A armed 40m ago, cooldown 30 → elapses_at = now-10m (already past
    # relative to `now`). C armed 5m ago, cooldown 120 → still active.
    # Decide activeness at a prospective time inside A's window
    # (now-35m), but compute `remaining` from the later `now` to
    # exercise the max(0, …) clamp on A.
    armed_a = now - timedelta(minutes=40)
    armed_c = now - timedelta(minutes=5)
    prospective = now - timedelta(minutes=35)  # inside A's 30m window
    conflict = detect_interaction_conflict(
        medication_id=b,
        rules=[_rule(a, b, 30), _rule(c, b, 120)],
        partner_last_non_voided={a: armed_a, c: armed_c},
        medication_names={a: "A", c: "C"},
        prospective_taken_at=prospective,
        now=now,
    )
    assert conflict is not None
    ids = {x.conflicting_medication_id for x in conflict.conflicts}
    assert ids == {a, c}
    by_id = {x.conflicting_medication_id: x for x in conflict.conflicts}
    # A's cooldown already elapsed relative to `now` → clamped at 0.
    assert by_id[a].remaining_seconds == 0
    assert by_id[c].remaining_seconds > 0


def test_irrelevant_and_duplicate_rules_are_skipped() -> None:
    b, a, x, y = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    armed = now - timedelta(minutes=1)
    conflict = detect_interaction_conflict(
        medication_id=b,
        rules=[
            _rule(x, y, 120),  # involves neither b → skipped
            _rule(a, b, 120),  # active conflict
            _rule(b, a, 60),  # duplicate partner (a) → skipped
        ],
        partner_last_non_voided={a: armed},
        medication_names={a: "A"},
        prospective_taken_at=now,
        now=now,
    )
    assert conflict is not None
    assert len(conflict.conflicts) == 1
    assert conflict.conflicts[0].conflicting_medication_id == a


def test_adapter_headline_is_latest_ending() -> None:
    b, a, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    conflict = detect_interaction_conflict(
        medication_id=b,
        rules=[_rule(a, b, 30), _rule(c, b, 120)],
        partner_last_non_voided={
            a: now - timedelta(minutes=1),
            c: now - timedelta(minutes=1),
        },
        medication_names={a: "A", c: "C"},
        prospective_taken_at=now,
        now=now,
    )
    out = to_interaction_state_out(conflict)
    assert out is not None
    assert len(out.conflicts) == 2
    # Headline reflects the latest-ending cooldown (C, 120m).
    latest = max(c.cooldown_elapses_at for c in out.conflicts)
    assert out.cooldown_elapses_at == latest
    assert to_interaction_state_out(None) is None
