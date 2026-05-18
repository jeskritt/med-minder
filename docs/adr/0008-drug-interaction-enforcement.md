# ADR 0008: Drug-interaction cooldowns — warn + explicit confirm, not a hard block

## Status

Proposed — 2026-05-17 (pre-Phase 6). To be marked `Accepted` with the
Phase 6 PR, matching ADR-0002's Proposed→Accepted-with-the-phase-PR
lifecycle.

## Context

Phase 6 implements the drug-interaction cooldowns the schema has
carried since Phase 1. `MedicationInteraction`
(`backend/src/medminder/db/models/medication_interactions.py`) stores a
single symmetric row `(medication_id, conflicting_medication_id,
cooldown_minutes)`; uniqueness on the *unordered* pair is enforced by
the `ix_medication_interactions_pair` UNIQUE index on
`(LEAST, GREATEST)`, with `ck_interactions_cooldown_pos` and
`ck_interactions_distinct_pair`. The model docstring already scopes
this: "Phase 6 enforces the actual cooldown logic; Phase 1 just stores
the table."

The roadmap describes Phase 6 as "clear UI warnings before the user
can mark the conflicting med as taken" — ambiguous between a server
hard-block and a client-only warning. This is a non-obvious decision
where reasonable engineers disagree, so it needs an ADR before
implementation.

Two existing precedents pull in opposite directions:

- The `create_dose` guards in
  `backend/src/medminder/domain/doses.py` **hard-block**: count_down
  raises `MinIntervalNotElapsedError` and multi_sub_dose raises
  `WindowFullError`, surfaced as non-overridable HTTP 409s. These exist
  to prevent **overdose** — the user genuinely cannot proceed.
- The project's pain-med UX philosophy: passive notifications, the
  user retains agency, and hard guards are reserved for overdose
  prevention. A missed-window / PRN cooldown is advisory, not a
  prohibition.

A drug-interaction cooldown is advisory in the same sense as the
pain-med case: it is safety-relevant information the user should not
miss, but the user (often managing their own regimen) must retain the
ability to proceed — while leaving an honest record that they did.

## Decision

Drug-interaction cooldowns are enforced as **warn + explicit confirm**,
never as a hard server block.

- **Pure detector in the domain layer.** A pure, order-independent
  function (sibling to `multi_sub_dose_window_full` /
  `compute_timer_state` in `backend/src/medminder/domain/timers.py`)
  evaluates whether a prospective dose falls inside an active
  interaction cooldown. It honors the symmetric single-row rule by
  matching the pair in either order (the `LEAST/GREATEST` semantics of
  `ix_medication_interactions_pair`). It returns conflict information
  (the conflicting medication and remaining cooldown); it does **not**
  raise a blocking error.
- **`create_dose` gains an explicit `interaction_acknowledged`
  parameter.** Unacknowledged request **with** a detected conflict ⇒ a
  structured, **always-overridable** conflict response: a distinct
  error type (e.g. `MedicationInteractionConflict`, a new
  `DoseError` subclass alongside the existing
  `DoseForbiddenError`/`DoseValidationError` hierarchy) carrying the
  conflicting medication and remaining cooldown. Acknowledged request
  ⇒ the dose is recorded **and** the acknowledgment is persisted for
  audit. The server never refuses a dose the user has explicitly
  confirmed.
- **The override is recorded.** The acknowledgment must be durably,
  attributably stored — consistent with the append-only / auditable
  stance of ADR-0005 (dose voids). The exact storage shape (a column
  on `doses` vs. a companion row) is Phase 6 data-model work and is
  **not** decided here; this ADR only mandates that the override is
  recorded, not how.
- **UI.** A warning plus an explicit "take anyway" confirmation step
  precedes the dose POST, reusing the existing confirm-modal pattern
  (`frontend/src/components/UntakeConfirmModal.tsx`) and consistent
  with the pain-med UX philosophy.

The key distinction from the count_down / multi_sub_dose guards: those
409s are **non-overridable overdose guards**; the interaction conflict
is an **advisory, always-overridable** signal.

## Consequences

### Positive

- The user keeps agency over their own regimen while never silently
  missing a safety-relevant interaction.
- An honest, attributable record of every override preserves the
  adherence/audit history the mission promises (same rationale as
  ADR-0005).
- Reuses established plumbing: a pure domain detector like the timer
  detectors, the `DoseError` hierarchy, and the existing confirm-modal
  UI pattern.
- The symmetric pair rule is already enforced at the database, so the
  detector only has to match in both orders, not de-duplicate.

### Negative

- Introduces a *second* conflict path that is deliberately
  **overridable**, distinct from the non-overridable count_down /
  multi_sub_dose 409s. API and client error handling must clearly
  differentiate the two so an interaction conflict is never rendered
  as a dead-end the way an overdose guard is.
- `create_dose`'s signature and the dose-create API grow an
  acknowledgment parameter and a new structured conflict response.

### Neutral

- Phase 6 still owns, within these constraints: the acknowledgment
  storage shape, the exact HTTP status for the unacknowledged-conflict
  response, and the detector's precise signature/return type.
- The cooldown is evaluated server-side (authoritative) but never
  blocks; the client is responsible for surfacing the warning and
  collecting the explicit confirmation before retrying with
  acknowledgment.

## Alternatives considered

- **Passive warn only, no audit of the override** — rejected. It keeps
  agency but loses the attributable record of "the user was warned and
  proceeded," degrading the adherence/audit history ADR-0005 and the
  mission depend on.
- **Server hard-block (optionally with an override param)** — rejected.
  It contradicts the pain-med UX philosophy ("hard guards only for
  overdose prevention; user has agency"). An interaction cooldown is
  advisory; making it a 409 the user must defeat treats it like an
  overdose guard, which it is not.
- **Fold into the count_down 409 path** — rejected. It conflates a
  non-overridable overdose guard with an advisory, always-overridable
  interaction warning; the two have different severity, different UX,
  and must not share an error code.

## References

- `specs/roadmap.md` — Phase 6 (Drug-interaction cooldowns).
- `backend/src/medminder/db/models/medication_interactions.py` —
  symmetric `(LEAST, GREATEST)` pair, `cooldown_minutes`, CHECKs.
- `backend/tests/db/test_medication_interactions.py` — schema-level
  invariants already covered.
- `backend/src/medminder/domain/doses.py` — the count_down /
  multi_sub_dose hard-block guards and `DoseError` hierarchy this
  decision deliberately diverges from.
- `backend/src/medminder/domain/timers.py` — pure-detector pattern
  (`compute_timer_state`, `multi_sub_dose_window_full`) the interaction
  detector mirrors.
- `frontend/src/components/UntakeConfirmModal.tsx` — confirm-modal
  pattern the "take anyway" step reuses.
- ADR-0005 (dose voids) — append-only / attributable-audit precedent.
- ADR-0002 (in-process APScheduler) — Proposed→Accepted status
  lifecycle precedent.
- Project pain-med UX philosophy — passive notifications, user agency,
  hard guards reserved for overdose prevention.
