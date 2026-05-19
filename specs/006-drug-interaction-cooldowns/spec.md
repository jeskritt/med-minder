# Feature Specification: Phase 6 — Drug-Interaction Cooldowns

**Feature Branch**: `006-drug-interaction-cooldowns`
**Created**: 2026-05-17
**Status**: Draft
**Input**: User description: "@specs/roadmap.md phase 6"

## Clarifications

### Session 2026-05-17

- **Enforcement model fixed by ADR-0008** (Proposed pre-Phase 6, to be
  Accepted with the Phase 6 PR): a drug-interaction cooldown is **warn +
  explicit confirm**, never a hard server block. The server never refuses a
  dose the user has explicitly confirmed; an unacknowledged dose with a
  detected conflict yields a structured, **always-overridable** conflict
  response; an acknowledged dose is recorded **and** the override is
  durably, attributably persisted for audit. This deliberately diverges
  from the non-overridable Phase 5 `count_down` / `multi_sub_dose` 409
  overdose guards, and supersedes the "blocked server-side / block holds
  against bypass" wording of UC-4.3 in `docs/user_stories.md` for
  interactions (see Assumptions — that doc should be reconciled).
- Q: where is interaction-rule management surfaced in Phase 6? → A:
  In the **end-user medication add/edit UI** (a "conflicts with" section
  on the Phase 3 medication form). Molly manages her own interaction
  rules; Phase 6 is demoable end-to-end with no admin/CLI step. Rules are
  scoped to the owning user's own medications.
- Q: Is in-place editing of an existing interaction rule in Phase 6
  scope? → A: No — create + delete only. Changing a cooldown is
  delete-then-recreate; there is no rule-update path.
- Q: Is the rule-authoring UI (User Story 3) a committed Phase 6
  deliverable or a cuttable P3? → A: Committed. US1–US3 all ship;
  "demoable end-to-end with no admin/CLI step" is binding.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Migraine Molly: warned, then explicitly confirms a conflicting dose (Priority: P1)

Molly takes a migraine medication that conflicts with ibuprofen and requires
a 2-hour cooldown before Tylenol. After she marks her migraine medication as
taken, attempting to mark a conflicting medication must surface a clear
warning that names the medication she took, names the medication she is about
to take, and states how much longer the cooldown runs — *before* the dose is
recorded. Molly is not forbidden: she manages her own regimen and may have a
clinical reason to proceed. If she explicitly confirms ("take anyway"), the
dose is recorded **and** the fact that she overrode an active interaction
warning is permanently, attributably recorded. The detection is
server-authoritative: a client cannot silently slip a conflicting dose past
it without either clearing the cooldown or carrying an explicit
acknowledgment.

**Why this priority**: This is the entire point of Phase 6 and the core of
Molly's primary flow in `docs/user_stories.md`, decided by ADR-0008. It is
the smallest slice that delivers user value (the user never silently misses
a safety-relevant interaction, while keeping agency) and is independently
shippable against a seeded rule.

**Independent Test**: With an interaction rule "Migraine med ↔ ibuprofen,
cooldown 120 min" in place, mark the migraine medication as taken. Then mark
ibuprofen *without* acknowledgment (through the UI and again via a direct API
call): both return a structured conflict response identifying both
medications and a non-zero remaining cooldown, and no `doses` row is written
for ibuprofen. Retry *with* acknowledgment: the ibuprofen dose is recorded
and an attributable override record is persisted.

**Acceptance Scenarios**:

1. **Given** an interaction rule between medication A and medication B with a
   120-minute cooldown and no recorded doses, **When** the user marks A as
   taken, **Then** the dose is recorded normally (the first dose of a pair
   never triggers a conflict).
2. **Given** A was marked taken 10 minutes ago and a 120-minute A↔B cooldown
   exists, **When** the user attempts to mark B as taken **without**
   acknowledgment, **Then** no `doses` row is written for B and a structured
   conflict response is returned that names A, names B, and states the
   remaining cooldown (~110 minutes).
3. **Given** the conditions in scenario 2, **When** the user explicitly
   confirms ("take anyway") and the request is retried **with**
   acknowledgment, **Then** the B dose is recorded **and** an attributable
   override record (who/when/which conflict) is persisted; the server does
   not refuse the confirmed dose.
4. **Given** the conditions in scenario 2, **When** a client issues the
   mark-as-taken request for B directly to the server bypassing the UI but
   **without** acknowledgment, **Then** the server still returns the
   structured conflict response and writes no `doses` row — the warning
   cannot be silently bypassed.
5. **Given** A was taken 3 hours ago and the A↔B cooldown is 120 minutes,
   **When** the user marks B as taken, **Then** the dose is recorded
   normally with no warning because the cooldown has fully elapsed.
6. **Given** the single interaction row was created as A↔B, **When** B is
   taken first and the user then attempts A within the cooldown, **Then**
   the same warning/confirm flow applies symmetrically — one row guards both
   directions.
7. **Given** A's most recent dose has been voided (Phase 4 un-take) so no
   non-voided A dose falls inside the cooldown, **When** the user marks B as
   taken, **Then** the dose is recorded normally because voided doses do not
   arm an interaction cooldown.

---

### User Story 2 — Molly: sees the conflict context and a live cooldown timer (Priority: P2)

So Molly can make an informed decision (and ideally avoid the conflict
without a failed attempt), the conflicting medication shows a clear,
human-readable status before she acts ("Interacts with Migraine med — safe
at 3:45 PM") with a live-updating remaining-cooldown time, consistent with
the Phase 5 timer display patterns. The warning and the confirm step clear
once the cooldown elapses or the arming dose is voided, without requiring a
manual page reload.

**Why this priority**: Builds the legibility layer on top of the detector
and warn/confirm flow from US1. US1 already protects the user; US2 makes the
situation understandable in advance instead of only at confirm time. It
lands second because the content it surfaces is produced by US1's detector.

**Independent Test**: With an active A↔B cooldown after dosing A, open the
today view and medication list. B shows an interaction indicator naming A
and a remaining time that ticks down in real time and survives a page
reload (server-authoritative). Tapping B presents the explicit "take anyway"
confirmation reusing the existing confirm-modal pattern. Advance past the
cooldown (or void A's dose) and confirm the indicator and the confirm step
clear on the next refetch.

**Acceptance Scenarios**:

1. **Given** an active interaction cooldown affecting B, **When** the user
   opens the today view or medication list, **Then** B shows a clearly
   marked interaction state that names the conflicting medication and the
   remaining time.
2. **Given** the conditions in scenario 1, **When** the user remains on the
   page, **Then** the displayed remaining time decreases at least once per
   visible minute without a manual refresh, seeded from server-authoritative
   state (Phase 5 client-counter approach; no periodic polling).
3. **Given** a B with an active conflict, **When** the user taps
   mark-as-taken, **Then** an explicit "take anyway" confirmation step
   (reusing the existing confirm-modal pattern) is shown before any dose is
   recorded, stating the conflicting medication and remaining cooldown.
4. **Given** a B whose conflicting cooldown reaches zero, **When** the
   client refetches on focus or after any mark-as-taken action, **Then**
   B's interaction indicator clears and marking B no longer requires the
   confirmation step.
5. **Given** a B with an active conflict, **When** the user voids the
   conflicting A dose that armed the cooldown, **Then** on the next refetch
   B is no longer flagged (no other non-voided A dose remains in window).
6. **Given** B conflicts with more than one medication and at least one
   conflicting cooldown is active, **When** the user views B, **Then** the
   warning identifies every currently-conflicting medication and the
   remaining time reflects the latest-ending cooldown.

---

### User Story 3 — Setting up an interaction rule (Priority: P3)

For the warn/confirm flow in US1/US2 to be usable, there must be a way to
record that "Migraine med conflicts with ibuprofen, cooldown 120 minutes"
as a single symmetric rule, and to review or remove it. Rules are authored
in the **end-user medication add/edit UI**: a "conflicts with" section on
the existing Phase 3 medication form lets the owning user pair one of their
medications with another of their medications and set a positive
`cooldown_minutes`. Molly manages her own rules; no admin or CLI step is
required for Phase 6 to be demoable end-to-end.

**Why this priority**: The detector and warn/confirm flow (US1/US2) are the
safety-relevant core and are demonstrable against a seeded rule. Rule
authoring is the least safety-sensitive slice and therefore sequenced
last, but it is a committed Phase 6 deliverable (not cuttable): the
clarified "demoable end-to-end with no admin/CLI step" requirement only
holds if US3 ships.

**Independent Test**: Create a symmetric A↔B rule with a positive cooldown,
confirm the warn/confirm flow from US1 applies in both directions, then
remove it and confirm both medications are takeable again with no warning.

**Acceptance Scenarios**:

1. **Given** no rule exists between A and B, **When** an A↔B rule with a
   positive cooldown is created, **Then** the US1 warn/confirm flow applies
   in both directions immediately.
2. **Given** an existing A↔B rule, **When** a duplicate rule for the same
   unordered pair is created, **Then** it is rejected (one row per
   unordered pair).
3. **Given** an existing A↔B rule, **When** it is deleted, **Then** neither
   medication warns about the other on subsequent mark-as-taken attempts.
4. **Given** a cooldown value of zero or negative, or a self-pair, **When**
   the rule is created, **Then** it is rejected with a clear validation
   message. (There is no in-place edit path; changing a cooldown is
   delete-then-recreate.)
5. **Given** the medication add/edit form, **When** the user adds a
   "conflicts with" entry selecting another of their own medications and a
   positive cooldown and saves, **Then** the symmetric rule is persisted
   and the US1 warn/confirm flow applies in both directions; the form only
   offers the logged-in user's own non-deleted medications.

---

### Edge Cases

- **First dose of a pair never warns**: the rule only arms a cooldown
  *after* one medication of the pair has a non-voided dose; the medication
  taken first is always recorded with no warning.
- **Acknowledged dose is never refused**: per ADR-0008 the server records
  any explicitly confirmed dose; it never returns a dead-end for an
  acknowledged interaction conflict.
- **Voided doses do not arm cooldowns**: consistent with Phase 5, a
  `dose_voids`-voided dose is not the "last dose" and does not arm the
  partner medication's conflict.
- **Symmetric, single-row semantics**: exactly one
  `medication_interactions` row exists per unordered pair (existing
  `(LEAST, GREATEST)` unique index); it is matched in either order.
- **Multiple simultaneous conflicts**: a medication may conflict with
  several others; the warning lists every active conflict and the remaining
  time reflects the latest-ending one. A single acknowledgment confirming
  the action covers the dose being recorded.
- **Self-pair is impossible**: the existing `ck_interactions_distinct_pair`
  check prevents self-conflict; own re-dose cadence is Phase 5
  `count_down`, not interactions.
- **Composition with Phase 5 guards**: a medication may be subject to both
  a non-overridable Phase 5 overdose guard (`count_down` /
  `multi_sub_dose` → 409) **and** an overridable interaction conflict. A
  Phase 5 overdose block takes precedence and is *not* made overridable by
  an interaction acknowledgment; the two paths stay distinct.
- **Soft-deleted medications**: never appear in any interaction-state
  response; historical doses still exist but no interaction surface is
  presented for hidden medications.
- **Cross-user isolation**: detection, warnings, and override records are
  scoped to the logged-in user's own medications and doses.
- **Clock skew**: whether a conflict is active is decided server-side from
  stored `taken_at` values; a manipulated client clock cannot clear it.
- **Cooldown boundary**: at exactly `armed_dose.taken_at + cooldown` the
  conflict is no longer active (remaining seconds clamped at zero,
  consistent with Phase 5 boundary semantics).
- **Daylight-saving transitions**: all cooldown arithmetic uses UTC;
  user-facing strings honour the user's `timezone`.

## Requirements *(mandatory)*

### Functional Requirements

#### Detection & warn/confirm flow (User Story 1) — governed by ADR-0008

- **FR-001**: The system MUST provide a pure, order-independent evaluation
  that, given a prospective dose for a medication, determines whether any
  medication sharing an interaction rule with it has a non-voided dose whose
  `taken_at` is within that rule's `cooldown_minutes` of the prospective
  dose time. It MUST return conflict information (conflicting medication,
  remaining cooldown) and MUST NOT itself raise a blocking error.
- **FR-002**: The mark-as-taken operation MUST accept an explicit
  interaction-acknowledgment input. With a detected conflict and **no**
  acknowledgment, the operation MUST NOT write a `doses` row and MUST return
  a structured, overridable conflict response. With acknowledgment (or no
  detected conflict), the dose MUST be recorded.
- **FR-003**: When an acknowledged dose is recorded over an active
  interaction conflict, the system MUST durably and attributably persist
  the override (at minimum: which dose, which conflicting medication(s),
  and that the user was warned and proceeded), consistent with the
  append-only / auditable stance of ADR-0005. *(Exact storage shape is
  Phase 6 plan/data-model work per ADR-0008's Neutral consequences and is
  not fixed by this spec.)*
- **FR-004**: The conflict response MUST include: a stable error/identifier
  code distinct from the Phase 5 overdose codes, the affected medication's
  identifier, each conflicting medication's identifier and display name, the
  timestamp at which the cooldown elapses, and the remaining seconds
  (non-negative).
- **FR-005**: Detection MUST be server-authoritative and MUST hold against
  direct API calls that bypass UI guarding: an unacknowledged conflicting
  dose submitted directly to the API MUST still receive the conflict
  response and write no dose. This MUST be exercised by an integration test
  that bypasses the frontend (preserving the testable intent of UC-4.3
  under the ADR-0008 model).
- **FR-006**: Enforcement MUST be symmetric from a single
  `medication_interactions` row, matched in either order; no
  direction-specific storage is required.
- **FR-007**: A medication's *first* dose of an interacting pair MUST never
  produce a conflict; only a partner medication's prior non-voided dose
  within the cooldown can.
- **FR-008**: Voided doses (Phase 4 `dose_voids`) MUST NOT arm an
  interaction cooldown; only non-voided doses are considered.
- **FR-009**: When a medication conflicts with more than one other
  medication, the conflict response MUST identify every currently-active
  conflict; a single acknowledgment confirms recording the dose.
- **FR-010**: Interaction conflicts MUST remain distinct from Phase 5
  overdose guards: a `count_down` / `multi_sub_dose` 409 is non-overridable
  and MUST NOT be defeated by an interaction acknowledgment; the two
  conflict paths MUST be separately identifiable by API and client.

#### Warning surface (User Story 2)

- **FR-011**: Every endpoint returning medication summaries (today view,
  medication list, single medication detail) MUST report, for each of the
  logged-in user's non-deleted medications, whether an interaction conflict
  is currently active and — when active — the conflicting medication
  name(s) and the time the cooldown elapses.
- **FR-012**: The today view and medication list MUST present an active
  interaction with a clear, human-readable status naming the conflicting
  medication and the remaining cooldown (e.g. "Interacts with Migraine med
  — safe at 3:45 PM").
- **FR-013**: The remaining-cooldown display MUST advance using the Phase 5
  client-counter approach (local monotonic clock seeded from server state;
  refetch on focus and after any mark-as-taken; no periodic polling).
- **FR-014**: Marking a medication with an active interaction conflict MUST
  present an explicit "take anyway" confirmation step before the dose is
  recorded, reusing the existing confirm-modal pattern. The step MUST state
  the conflicting medication and remaining cooldown and MUST clear
  automatically (on the next refetch) once the cooldown elapses or the
  arming dose is voided — without a manual page reload.

#### Rule management (User Story 3)

- **FR-015**: The system MUST provide a way to create a symmetric
  interaction rule for an unordered medication pair with a positive
  `cooldown_minutes`, to view existing rules, and to remove a rule. Rule
  authoring, viewing, and removal are surfaced in the medication add/edit
  UI ("conflicts with" section); the medication selector MUST offer only
  the logged-in user's own non-deleted medications. Rules are immutable
  in place: Phase 6 provides create and remove only; changing a
  `cooldown_minutes` is delete-then-recreate (no update endpoint or
  inline-edit affordance).
- **FR-016**: Creating a rule for a pair that already has one MUST be
  rejected (one row per unordered pair, per the existing
  `ix_medication_interactions_pair` unique index).
- **FR-017**: A non-positive `cooldown_minutes`, or a rule whose two
  medications are identical, MUST be rejected with a clear validation
  message (consistent with the existing `ck_interactions_cooldown_pos` /
  `ck_interactions_distinct_pair` constraints).
- **FR-018**: A soft-deleted medication participating in interaction rules
  MUST NOT cause enforcement errors and MUST NOT warn on unrelated
  medications.

#### Cross-cutting (security, typing, coverage, docs)

- **FR-019** (security): Detection, warning, and override-audit reporting
  MUST be scoped to the logged-in user's own medications and doses; a
  cross-user negative test MUST prove no rule, dose, conflict, or override
  record leaks across users.
- **FR-020** (security): Rule-management operations MUST validate and
  authorise inputs at the boundary (only the owning user's medications may
  be paired; cooldown is a bounded positive integer).
- **FR-021** (typing): New backend domain code MUST satisfy `mypy
  --strict`; new client code MUST satisfy `tsc --noEmit` strict.
- **FR-022** (coverage): Project coverage MUST stay ≥85%; the new
  interaction-detector domain module SHOULD reach ≥95% line coverage given
  its pure-function nature; no module falls below the 70% per-module floor.
- **FR-023** (docs): A sequence diagram of the warn/acknowledge/record flow
  MUST be added under `docs/diagrams/`, and **ADR-0008 MUST move from
  `Proposed` to `Accepted`** with the Phase 6 PR (matching ADR-0002's
  lifecycle), per the per-phase exit criteria in `specs/roadmap.md`.

### Key Entities

- **MedicationInteraction** *(existing table, shipped Phase 1; enforcement
  added here)*: a single symmetric cooldown rule for an unordered pair.
  Existing fields: `medication_id`, `conflicting_medication_id`,
  `cooldown_minutes` (positive), `created_at`. Unordered-pair uniqueness and
  self-pair prohibition already enforced at the database. **No new
  persistent table or column is required for detection.**
- **InteractionConflict** *(value object, server-computed, not persisted —
  detector output)*: `as_of`; a list of active conflicts, each with the
  conflicting medication's id and display name, the arming dose's
  `taken_at`, the `cooldown_elapses_at` timestamp, and `remaining_seconds`
  (non-negative).
- **InteractionConflictResponse** *(structured overridable response for
  FR-002/FR-004; sibling to, but distinct from, the Phase 5 overdose error
  shapes; the concrete wire model is named `InteractionCooldownViolation`
  in plan/contracts/data-model)*: `code` (stable, e.g.
  `"interaction_cooldown_active"`, distinct from Phase 5 codes),
  `medication_id`, `conflicts` (id + display name per conflicting
  medication), `cooldown_elapses_at`, `remaining_seconds`.
- **Interaction override record** *(audit; persisted)*: an attributable
  record that a user was warned of an active interaction and explicitly
  proceeded — links to the recorded dose and the conflicting
  medication(s). **Storage shape (column on `doses` vs. companion row) is
  Phase 6 plan/data-model work per ADR-0008 and not fixed here**, but the
  record MUST exist (FR-003).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After Molly marks her migraine medication as taken, an
  attempt to mark a conflicting medication *without* acknowledgment —
  through the UI or via a direct API call — yields the structured conflict
  response and writes zero `doses` rows for the blocked medication, 100% of
  the time the cooldown is active. Verified by an integration test
  bypassing the frontend.
- **SC-002**: The warning identifies the conflicting medication by name and
  the remaining cooldown; a user reading it can tell *why* it is flagged
  and *when* it elapses without consulting support or docs.
- **SC-003**: When Molly explicitly confirms, the dose is recorded **and**
  an attributable override record is persisted, 100% of the time; the
  server never returns a dead-end for an acknowledged interaction conflict.
- **SC-004**: An active interaction shows on the today view within 2
  seconds of opening it; the displayed remaining time matches wall-clock
  truth within 5 seconds across a 10-minute observation window and survives
  a page reload.
- **SC-005**: When the cooldown elapses or the arming dose is voided, the
  warning and the confirm step clear on the next focus/refetch with no
  manual reload, in 100% of observed cases.
- **SC-006**: Detection is symmetric: in 100% of tested orderings (A then
  B, B then A) a single rule produces the warn/confirm flow for the second
  medication for the configured cooldown.
- **SC-007**: Molly's primary flow from `docs/user_stories.md` (mark
  migraine med → attempt conflicting med → see clear warning + remaining
  cooldown → explicitly proceed with an audited override) passes on a
  deployed build before the phase is complete, per `specs/mission.md`.
- **SC-008**: All Phase 6 exit criteria from `specs/roadmap.md` are
  satisfied: the warn/acknowledge/record diagram is committed under
  `docs/diagrams/`, **ADR-0008 is promoted to `Accepted`**, and a
  security-review note covering the new write-path acknowledgment, override
  audit, and cross-user isolation is present in the PR description.
- **SC-009**: Project coverage stays ≥85% (machine-enforced by
  `--cov-fail-under=85`). The new interaction-detector module reaching
  ≥95% line coverage and the constitution's 70% per-module floor are
  verified by manual review of the coverage report in the gate task
  (no separate per-module machine gate is added in Phase 6).

## Assumptions

- **ADR-0008 governs the enforcement model** and supersedes any
  hard-block reading: warn + explicit confirm, server never refuses an
  acknowledged dose, override is audited. The "blocked server-side / block
  holds against bypass" wording of **UC-4.3 in `docs/user_stories.md` is
  superseded for interactions** and should be reconciled in that doc as
  part of Phase 6 (the testable intent — server-authoritative, not
  silently bypassable without acknowledgment — is preserved by FR-005).
- "Within the cooldown" is evaluated as: the conflicting medication has a
  non-voided dose whose `taken_at` is at or after `prospective_dose_time -
  cooldown_minutes`. The arming dose is the conflicting medication's most
  recent non-voided dose.
- The interaction detector mirrors the existing pure-detector pattern in
  `backend/src/medminder/domain/timers.py` and reuses the `DoseError`
  hierarchy and the existing `UntakeConfirmModal` confirm-modal pattern
  (per ADR-0008 References).
- The override-audit storage shape, the exact HTTP status of the
  unacknowledged-conflict response, and the detector's precise signature
  are explicitly deferred to `/speckit-plan` per ADR-0008's Neutral
  consequences.
- Interaction conflicts compose with, but never weaken, Phase 5 guards: a
  `count_down` / `multi_sub_dose` overdose 409 stays non-overridable; the
  interaction acknowledgment only ever covers the interaction conflict.
- No schema migration is required for *detection* (the
  `medication_interactions`, `doses`, `dose_voids` tables suffice);
  recording the override (FR-003) may require schema work, decided in
  `/speckit-plan`.
- The blocked-state display reuses the Phase 5 client counter helper and
  refetch cadence rather than a new polling mechanism.
- Medications with no interaction rules, and mode `none` medications, are
  unaffected; their mark-as-taken behaviour is unchanged from Phases 4–5.
- The `--cov-fail-under=85` gate in `backend/pyproject.toml` remains the
  project-wide floor; ≥95% is the target for the new pure-function
  detector module.

## Dependencies

- Phase 1 — `medication_interactions`, `doses`, `dose_voids` schema.
- Phase 3 — medication CRUD (medications to pair; candidate host surface
  for rule management depending on Question 1).
- Phase 4 — mark-as-taken write path, `DoseError` hierarchy, `dose_voids`,
  and the `UntakeConfirmModal` confirm pattern reused by the "take anyway"
  step.
- Phase 5 — server-authoritative timer state and the client counter /
  refetch cadence reused for the remaining-cooldown display; the
  `timers.py` pure-detector pattern the interaction detector mirrors.
- ADR-0008 — the binding warn-+-explicit-confirm decision; promoted to
  `Accepted` with the Phase 6 PR.
- ADR-0005 — append-only / attributable-audit precedent for the override
  record.
