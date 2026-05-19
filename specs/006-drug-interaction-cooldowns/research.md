# Phase 0 Research — Phase 6: Drug-Interaction Cooldowns

This document captures the design decisions made before implementation
begins. Each decision lists what was chosen, why, and what was
rejected. ADR-0008 fixed the enforcement *model* (warn + explicit
confirm + audited override, always overridable). ADR-0008 explicitly
deferred three points to this plan — D2 (override storage shape),
D4 (unacknowledged-conflict HTTP status), and D1 (detector signature);
those are resolved below.

---

## D1 — Where the interaction detector lives & its signature

**Decision**: New module
`backend/src/medminder/domain/interactions.py`, sibling to
`domain/timers.py`. It exposes one pure, order-independent function
plus frozen value objects and one exception class:

```python
def detect_interaction_conflict(
    *,
    medication_id: uuid.UUID,
    medication_names: Mapping[uuid.UUID, str],
    rules: list[MedicationInteraction],          # rules touching medication_id, either side
    partner_last_non_voided: Mapping[uuid.UUID, datetime],  # conflicting med id -> most-recent non-voided taken_at
    prospective_taken_at: datetime,
    now: datetime,
) -> InteractionConflict | None
```

It matches the symmetric single row in either order
(`LEAST/GREATEST` semantics of `ix_medication_interactions_pair`),
returns `None` when no conflict, and **never raises**. Value objects
(frozen dataclasses): `InteractionConflict(as_of, conflicts:
list[ConflictItem])` and `ConflictItem(conflicting_medication_id,
conflicting_medication_name, armed_dose_taken_at,
cooldown_elapses_at, remaining_seconds)`. Exception
`MedicationInteractionConflict` is a plain `Exception` defined **in
`domain/interactions.py`**, mirroring `MinIntervalNotElapsedError` /
`WindowFullError` in `domain/timers.py` (those are plain Exceptions —
*not* `DoseError` subclasses — precisely so they bubble past
`api/doses.py`'s inline `except` to the `app.py` 409 handler). This
keeps the module self-contained (no `domain.doses` import → no
circular import) and is the exact sibling of the existing 409
pattern. ADR-0008's "`DoseError` subclass" was illustrative; the
exception's exact form was ADR-0008-deferred to this plan.

**Rationale**: Mirrors the established pure-detector pattern
(`multi_sub_dose_window_full` / `compute_timer_state` in
`domain/timers.py`): inputs are primitives/ORM, output is a value
object or `None`, no raising. Satisfies Constitution Principle III
(testable without DB/HTTP) and ADR-0008's "pure detector in the
domain layer". Resolves the ADR-0008-deferred signature question.

**Alternatives considered**:
- *Co-locate inside `domain/doses.py`.* Rejected — `doses.py` is the
  write path; detection is also read by the warning surface (D5).
  Mixing forces the read concern through the write path.
- *Detector raises the conflict directly.* Rejected — it must also
  feed the non-raising warning surface (FR-011); raising is the
  caller's choice (D3), exactly as `multi_sub_dose_window_full`
  returns an error object the caller decides to raise.
- *Pass ORM `Dose` lists like `compute_timer_state`.* Rejected — the
  detector only needs each partner's most-recent non-voided
  `taken_at`; a `Mapping[uuid, datetime]` keeps it minimal and
  trivially unit-testable.

---

## D2 — Override-audit storage shape (ADR-0008-deferred)

**Decision**: New **append-only companion table**
`dose_interaction_overrides`, **one row per (dose,
conflicting_medication)**. Model
`backend/src/medminder/db/models/dose_interaction_overrides.py`,
mirroring `dose_voids.py`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `uuid_pk()` |
| `dose_id` | UUID FK → `doses.id` `ondelete=RESTRICT` | the recorded dose |
| `conflicting_medication_id` | UUID FK → `medications.id` `ondelete=RESTRICT` | a medication that was in active conflict when the user proceeded |
| `created_at` | timestamptz | `created_at_col()` |

Unique constraint on `(dose_id, conflicting_medication_id)`. Written
in the same transaction as the `doses` row when an acknowledged dose
clears an active conflict. One row per conflicting medication so a
multi-conflict override (FR-009) is fully attributable.

**Rationale**: ADR-0005 (dose voids) is the cited precedent —
append-only, never updated/deleted, attributable. A companion table
matches that precedent exactly and keeps `doses` append-only and
unmutated (Constitution "Soft delete only / `doses` append-only").
Row-per-conflict normalises the multi-conflict case (FR-009) without
array/JSON columns, which keeps `mypy --strict` typing clean and
makes the cross-user-isolation negative test (FR-019) a simple join.
The user selected this option over a per-dose JSON/array row and over
a column on `doses`.

**Alternatives considered**:
- *Per-dose row with a `conflicting_medication_ids` array/JSON
  column.* Rejected — denormalised; array typing under strict mypy
  and Pydantic strict is awkward; harder to assert per-conflict in
  isolation tests.
- *JSONB column on `doses`.* Rejected — mutates the append-only dose
  row, weakest fit with the ADR-0005 audit precedent.
- *Reuse `dose_voids`-like single-row-per-dose (unique `dose_id`).*
  Rejected — cannot represent "warned about A and B, proceeded" as
  separately attributable facts (FR-009 / FR-003 "which conflicting
  medication(s)").

**Migration**: one Alembic revision (next id `0004`), generated via
`just migrate-rev "Phase 6: dose_interaction_overrides"`; `alembic
check` must report no drift afterward (the model declares the table
so autogen and model agree).

---

## D3 — Acknowledgment parameter & write-path placement

**Decision**: `create_dose()` in `domain/doses.py` gains
`interaction_acknowledged: bool = False`. The interaction check runs
**after** the existing Phase 5 guards (count_down min-interval,
multi_sub_dose window) and before the `Dose(...)` insert. Flow:

1. Run existing Phase 5 guards unchanged (they raise non-overridable
   409s first — FR-010).
2. Load the user's `medication_interactions` rows touching this med
   (either side) and each partner's most-recent non-voided
   `taken_at` (reuse the `not_(select(DoseVoid.id).where(...)
   .exists())` pattern already in `create_dose`).
3. Call `detect_interaction_conflict(...)`.
4. Conflict **and not** `interaction_acknowledged` → raise
   `MedicationInteractionConflict` (no `doses` row written).
5. Conflict **and** acknowledged → insert the `doses` row **and** one
   `dose_interaction_overrides` row per active conflict, same
   transaction.
6. No conflict → unchanged behaviour; `interaction_acknowledged` is
   ignored (no override rows).

**Rationale**: A single insertion point covers the UI, direct API
calls, and any future CLI path (mirrors D3 of Phase 5 for the
count_down guard, FR-005). Phase 5 guards staying first guarantees an
overdose 409 is never weakened by an interaction acknowledgment
(FR-010). Same-transaction override write makes the audit atomic with
the dose.

**Alternatives considered**:
- *Interaction check before Phase 5 guards.* Rejected — could let an
  acknowledgment short-circuit before a non-overridable overdose
  guard is evaluated; FR-010 requires the overdose guard to win.
- *Separate "acknowledge" endpoint then a normal POST.* Rejected —
  TOCTOU race; doubles round trips (same reasoning as Phase 5 D3).

---

## D4 — Unacknowledged-conflict HTTP status (ADR-0008-deferred)

**Decision**: **HTTP 409 Conflict** with a distinct stable
`code: "interaction_cooldown_active"`. New wire model
`InteractionCooldownViolation` in
`backend/src/medminder/api/schemas/errors.py`, a sibling to
`MinIntervalViolation` / `WindowFullViolation`. A FastAPI exception
handler in `app.py` (sibling to `_min_interval_handler` /
`_window_full_handler`) maps `MedicationInteractionConflict` → 409 +
this body. Differentiation from the non-overridable overdose 409s is
by `code` + a dedicated frontend error class + the "take anyway"
modal — never by leaving it as a generic dead-end.

**Rationale**: 409 = well-formed request that conflicts with current
state (consistent with the Phase 5 violations). FR-004 already
mandates a "stable error/identifier code distinct from the Phase 5
overdose codes"; the existing client branch
(`useTakeDose` switches on `response.status === 409` + `body.code`)
extends with one more code and a distinct error subclass, satisfying
ADR-0008's "API and client must clearly differentiate" with the
lowest-risk, pattern-consistent change. The user selected this over
428 and 422.

**Alternatives considered**:
- *428 Precondition Required.* Rejected by the user — semantically
  tidy ("re-send with acknowledgment") but novel for this codebase
  and forces a new client status branch for no real gain over a
  distinct `code`.
- *422 Unprocessable (reuse `DoseValidationError`).* Rejected —
  conflates an overridable advisory with input-validation failure;
  weakest semantic fit and would collide with the existing 422 path.

---

## D5 — Warning surface (read side, FR-011–014)

**Decision**: Add `interaction_state: InteractionStateOut | None` to
`MedicationOut`, `MedicationDetailOut`
(`api/schemas/medications.py`) and `TodayItem`
(`api/schemas/today.py`). A new adapter `to_interaction_state_out`
(sibling to `to_timer_state_out` in `api/schemas/timers.py`) converts
the domain `InteractionConflict` at the API boundary. Each summary
endpoint (`api/medications.py` list + detail, `api/schedules.py`
today) computes it at `now` from the user's interaction rules +
`load_non_voided_history_for_meds` (reuse, `domain/doses.py`). `None`
when the medication has no currently-active conflict. The frontend
reuses the Phase 5 client-counter (`lib/timers.ts` `tickFrom` /
`formatRemaining`, seeded from server `as_of`, 1s interval, no
polling); the indicator clears on refetch
(`useToday` already has `refetchOnWindowFocus`; `useTakeDose`
invalidates `["today"]`/`["medications"]`/`["medication", id]` on
settle).

**Rationale**: FR-011 requires interaction state on every summary
endpoint; the Phase 5 timer-state injection points and the
client-counter already exist and are the sanctioned pattern (Phase 5
D2/D4). Server-authoritative remaining time (clock-skew safe,
FR-013); no new polling mechanism.

**Alternatives considered**:
- *Separate `GET /interactions` endpoint the client polls.* Rejected
  — FR-013 forbids periodic polling; duplicates the established
  refetch-on-focus/after-mutation cadence.
- *Compute remaining time client-side from raw rules+doses.* Rejected
  — ADR-0008 is server-authoritative; a manipulated client clock must
  not clear a conflict (spec Edge Cases — clock skew).

---

## D6 — Rule management (US3, FR-015–018)

**Decision**: New router
`backend/src/medminder/api/medication_interactions.py` with
**create / list / delete only — no update** (clarified scope:
changing a cooldown is delete-then-recreate). Endpoints are scoped to
the logged-in user; both medications must be owned and non-deleted;
`cooldown_minutes` a bounded positive int. Duplicate unordered pair →
409 (rely on `ix_medication_interactions_pair`); self-pair → 422
(rely on `ck_interactions_distinct_pair`). Surfaced in the existing
medication add/edit form as a repeatable "Conflicts with" section.
On the **edit** route the form diffs rules → create added / delete
removed. On the **create** route (medication has no id yet) the route
sequences: POST medication → POST each rule with the returned id; a
rule POST failure surfaces a partial-success error (medication saved;
list which rules failed) so the user retries from the edit form.

**Rationale**: Matches the `/speckit-clarify` outcomes (create+delete
only; US3 is a committed deliverable, demoable with no admin/CLI
step). DB constraints already enforce the invariants, so the API
maps constraint violations to status codes rather than re-checking.
Sequencing on create is required because a rule references an
existing partner medication and the new medication's id only exists
post-create (user-selected behaviour).

**Alternatives considered**:
- *Add a rule-update endpoint.* Rejected — out of clarified scope;
  the row has no history, so delete+recreate is functionally
  identical with less surface area.
- *Edit-only "Conflicts with" section (hidden on create).* Rejected
  by the user — narrower than US3 scenario 5's "add/edit form".
- *Single transactional "create medication + rules" endpoint.*
  Rejected — couples two resources; the rule endpoints must exist
  standalone for the edit flow and for direct-API tests anyway.

---

## D7 — Test layout & coverage strategy

**Decision**:

| File | Scope | Notes |
|---|---|---|
| `backend/tests/domain/test_interactions.py` | Pure-function | Symmetry (A→B and B→A), boundary (`taken_at + cooldown` exclusive), voided-dose-does-not-arm, first-dose-never-warns, multi-conflict, soft-deleted partner. Target ≥ 95% on `domain/interactions.py`. |
| `backend/tests/domain/test_interactions_no_db_imports.py` | Principle III | After importing `domain.interactions`, assert neither `sqlalchemy` nor `fastapi` is in `sys.modules` (mirrors Phase 5's analogous test). |
| `backend/tests/domain/test_doses_interaction_guard.py` | Domain integration | `create_dose` with/without `interaction_acknowledged`; asserts no `doses` row on unacknowledged conflict and one `dose_interaction_overrides` row per conflict on acknowledged. |
| `backend/tests/api/test_doses_interaction_conflict.py` | API integration | `POST /api/doses` direct (frontend-bypassing) → 409 `interaction_cooldown_active`, exact body, zero dose rows; retry acknowledged → 201 + override rows (FR-005 / SC-001). |
| `backend/tests/api/test_interaction_state.py` | API integration | `interaction_state` on today / list / detail per scenario + clears on cooldown elapse and on voiding the arming dose; **cross-user negative** (FR-019). |
| `backend/tests/api/test_medication_interactions_api.py` | API integration | Rule create/list/delete; duplicate pair → 409; self-pair / non-positive cooldown → 422; cross-user pairing rejected (FR-020). |
| `backend/tests/db/test_dose_interaction_overrides.py` | Schema | FK RESTRICT, `(dose_id, conflicting_medication_id)` uniqueness. |
| `frontend/src/__tests__/InteractionConfirmModal.test.tsx` | Component | "take anyway" body + confirm/cancel; distinct from the non-overridable overdose path. |
| `frontend/src/__tests__/medicationForm.conflicts.test.tsx` | Component | Add/remove conflict rows; Zod refine (positive int, no self-pair, no in-form duplicate); selector excludes self + already-paired. |
| `frontend/src/__tests__/interactionIndicator.test.tsx` | Component | Indicator names the conflicting med + ticking remaining; clears on refetch. |

**Rationale**: Honors FR-022 / SC-009 (project ≥ 85%, new
`domain/interactions.py` ≥ 95%, no module below the constitution's
70% floor). The pure detector reaches ≥ 95% via one parametrized
block. The frontend-bypassing API test is the testable core of
FR-005 / former UC-4.3 under the ADR-0008 model. Reuses
`backend/tests/api/conftest.py` (`httpx.AsyncClient` +
`ASGITransport`, login helper) and the real-Postgres
rollback fixture in `backend/tests/conftest.py`.

**Alternatives considered**:
- *Only API-level tests for the detector.* Rejected — the detector is
  pure and safety-relevant; exhaustive unit coverage is cheap and the
  ≥ 95% target depends on it.
- *Skip the cross-user negative test.* Rejected — FR-019 / Principle I
  make it mandatory (single-tenant, but isolation must be proven).
