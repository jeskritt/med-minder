---

description: "Phase 6 — Drug-Interaction Cooldowns: actionable, dependency-ordered tasks"
---

# Tasks: Phase 6 — Drug-Interaction Cooldowns

**Input**: Design documents in `specs/006-drug-interaction-cooldowns/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/interactions.openapi.yaml, quickstart.md

**Tests**: Test tasks **are** included. The feature mandates them —
FR-005 / SC-001 require an integration test that bypasses the
frontend, FR-019 requires a cross-user negative test, and
FR-022 / SC-009 set numeric coverage gates (project ≥ 85 %,
`domain/interactions.py` ≥ 95 %, per-module floor 70 %). Enforcement
is governed by **ADR-0008** (warn + explicit confirm + audited
override; always overridable; distinct from the non-overridable
Phase 5 overdose 409s).

**Organization**: Tasks are grouped by user story. Each story is
independently testable per its `Independent Test` block in `spec.md`.
US2 consumes US1's detector (the spec sequences it second by design);
US3 is independent and demoable on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]** — parallelizable (different files, no dependency on incomplete tasks)
- **[Story]** — `[US1]`/`[US2]`/`[US3]`. Setup / Foundational / Polish carry no story label.
- File paths are absolute repo-relative.

## Path Conventions (from `plan.md` Project Structure)

- Backend: `backend/src/medminder/`, tests under `backend/tests/{domain,api,db}/`
- Frontend: `frontend/src/`, tests under `frontend/src/__tests__/`, E2E under `frontend/e2e/`
- Diagrams: `docs/diagrams/`; ADR: `docs/adr/`
- `just` recipes need bash on Windows (Git Bash/WSL); PowerShell-direct equivalents noted on the kickoff task.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish a clean, drift-free baseline before any Phase 6
change, plus thin skeletons. Phase 6 adds one migration; this phase
verifies the starting point.

- [x] T001 **Baseline sanity gate (run FIRST).** Run `just generate-client` (PowerShell-direct: `python scripts/generate_openapi_client.py`) and confirm `git status --porcelain frontend/src/api/v1.d.ts` produces **no output**; then run `cd backend && python -m alembic check` and confirm **no drift**. Both mirror the CI gate; a dirty result must be fixed before Phase 6 work begins. (See `quickstart.md` Phase A.)
- [x] T002 [P] Create placeholder `docs/diagrams/sequence-drug-interaction-check.md` with a `# Drug-interaction warn/acknowledge/record` heading and a TODO note (filled in Polish per FR-023).
- [x] T003 [P] Create `specs/006-drug-interaction-cooldowns/checklists/security.md` skeleton (Phase 6 security merge gate per `plan.md` Constitution §I): unchecked items for cross-user isolation (FR-019), boundary validation of rule inputs (FR-020), override-audit write path, and the three new rule endpoints, plus a line "Phase 6 PR description includes a Security considerations section covering the acknowledgment write path, override audit, and cross-user isolation (SC-008)".

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure-detector skeleton, exception infra, wire schemas,
and the exception handler. Every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 [P] Create `backend/src/medminder/domain/interactions.py`: frozen dataclasses `ConflictItem(conflicting_medication_id, conflicting_medication_name, armed_dose_taken_at, cooldown_elapses_at, remaining_seconds)` and `InteractionConflict(as_of, conflicts: list[ConflictItem])`, plus `detect_interaction_conflict(*, medication_id, rules, partner_last_non_voided, medication_names, prospective_taken_at, now) -> InteractionConflict | None`. **No `sqlalchemy` / `fastapi` imports at runtime** (`if TYPE_CHECKING:` for model hints); **must not import `medminder.domain.doses`**. (Full logic implemented here now, not deferred — so T014 is satisfied by this task.)
- [x] T005 [P] **Design refinement (artifacts reconciled):** `MedicationInteractionConflict` is a **plain `Exception` defined in `domain/interactions.py`**, exactly mirroring `MinIntervalNotElapsedError` / `WindowFullError` in `domain/timers.py` (which are plain Exceptions, *not* `DoseError` subclasses, precisely so they bubble past `api/doses.py`'s inline `except` to the `app.py` 409 handler). This is self-contained (no `doses` import → no circular import) and is the exact sibling of the existing 409 pattern. ADR-0008's "`DoseError` subclass" was illustrative ("e.g.") and the exception's exact form was ADR-0008-deferred to Phase 6. research.md D1 / data-model.md / plan.md updated to match.
- [x] T006 [P] Add `ConflictOut` and `InteractionCooldownViolation` (`code: Literal["interaction_cooldown_active"]`, `medication_id`, `conflicts`, `cooldown_elapses_at`, `remaining_seconds: int = Field(ge=0)`) Pydantic-v2-strict models to `backend/src/medminder/api/schemas/errors.py`, matching `contracts/interactions.openapi.yaml`.
- [x] T007 [P] Create `backend/src/medminder/api/schemas/interactions.py`: `InteractionStateOut`, `InteractionRuleCreate`, `InteractionRuleOut` (per the contract) and the adapter `to_interaction_state_out(conflict: InteractionConflict | None) -> InteractionStateOut | None` (keeps `domain/interactions.py` free of pydantic). Reuse `ConflictOut` from `api/schemas/errors.py`.
- [x] T008 Register a FastAPI exception handler for `MedicationInteractionConflict` in `backend/src/medminder/app.py` `create_app`: map to HTTP **409** with the `InteractionCooldownViolation` body (sibling to `_min_interval_handler` / `_window_full_handler`). Depends on T005, T006.
- [x] T009 [P] Create `backend/tests/domain/test_interactions_no_db_imports.py`: in a subprocess, import `medminder.domain.interactions` then assert `"sqlalchemy" not in sys.modules and "fastapi" not in sys.modules` (Constitution Principle III; subprocess so a sibling test's prior import cannot mask a violation).

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Warned, then explicitly confirms a conflicting dose (Priority: P1) 🎯 MVP

**Goal**: Server-authoritative warn + always-overridable confirm + a
durable, attributable override record on the mark-as-taken write path.
**ADR-0008 graduates `Proposed → Accepted` on this story's PR.**

**Independent Test** (from `spec.md`): with a seeded A↔B 120-min rule,
mark A taken; mark B without acknowledgment (UI and direct API) →
structured conflict, no `doses` row for B; retry with acknowledgment →
B recorded **and** an attributable override row persisted.

### Tests for User Story 1 ⚠️

> Write these FIRST and confirm they fail before implementation.

- [x] T010 [P] [US1] `backend/tests/domain/test_interactions.py` — pure detector: symmetry (A→B and B→A from one row), boundary exclusive at `armed.taken_at + cooldown`, voided dose does not arm, first dose of a pair never warns, multi-conflict (latest-ending headline), soft-deleted partner excluded. Targets ≥ 95 % on `domain/interactions.py`.
- [x] T011 [P] [US1] `backend/tests/db/test_dose_interaction_overrides.py` — FK `RESTRICT` on `dose_id` and `conflicting_medication_id`; `(dose_id, conflicting_medication_id)` uniqueness.
- [x] T012 [P] [US1] `backend/tests/domain/test_doses_interaction_guard.py` — `create_dose` with/without `interaction_acknowledged`: no `doses` row on unacknowledged conflict; on acknowledged, dose + one `dose_interaction_overrides` row per active conflict, same transaction; Phase 5 overdose guard still wins and is not weakened by the ack (FR-010).
- [x] T013 [P] [US1] `backend/tests/api/test_doses_interaction_conflict.py` — `POST /api/doses` **directly (frontend-bypassing)** via the `httpx.AsyncClient`+`ASGITransport` conftest: unacknowledged → 409 `interaction_cooldown_active`, exact body, zero dose rows; retry acknowledged → 201 + override rows (FR-005 / SC-001).

### Implementation for User Story 1

- [x] T014 [US1] Implement `detect_interaction_conflict` fully in `backend/src/medminder/domain/interactions.py`: symmetric `LEAST/GREATEST` pair match, per-conflict `cooldown_elapses_at = armed.taken_at + cooldown`, `remaining_seconds = max(0, int(elapses_at - now))`, headline = latest-ending conflict; returns `None` when no active conflict. Depends on T004.
- [x] T015 [P] [US1] Create `backend/src/medminder/db/models/dose_interaction_overrides.py` (append-only, mirrors `dose_voids.py`): `id` `uuid_pk()`, `dose_id` FK→`doses.id` `ondelete=RESTRICT` NOT NULL, `conflicting_medication_id` FK→`medications.id` `ondelete=RESTRICT` NOT NULL, `created_at` `created_at_col()`, `UniqueConstraint(dose_id, conflicting_medication_id, name="uq_dose_interaction_override_pair")`. Ensure it is imported where the models package registers metadata (so autogen sees it).
- [x] T016 [US1] Generate the migration: `just migrate-rev "Phase 6: dose_interaction_overrides"`; review the new `backend/alembic/versions/0004_*.py` (table + FKs + unique constraint only); run `just migrate` then `cd backend && python -m alembic check` → empty diff. Depends on T015.
- [x] T017 [US1] Modify `create_dose()` in `backend/src/medminder/domain/doses.py`: add `interaction_acknowledged: bool = False`; **after** the existing Phase 5 guards, load the user's `medication_interactions` rows touching the med (either side) and each partner's most-recent non-voided `taken_at` (reuse the `not_(select(DoseVoid.id).where(...).exists())` pattern already in this file), call `detect_interaction_conflict`; conflict & not acknowledged → raise `MedicationInteractionConflict`; conflict & acknowledged → insert the `doses` row **and** one `dose_interaction_overrides` row per active conflict in the same transaction; no conflict → unchanged (ack ignored). Depends on T005, T014, T015.
- [x] T018 [US1] In `backend/src/medminder/api/schemas/doses.py` add `interaction_acknowledged: bool = False` to `DoseCreate`; in `backend/src/medminder/api/doses.py` pass it through to `create_dose` and add `409: {"model": InteractionCooldownViolation}` to the endpoint `responses`. Depends on T006, T008, T017.
- [x] T019 [US1] Run `just generate-client`; confirm `frontend/src/api/v1.d.ts` now carries `DoseCreate.interaction_acknowledged` and `InteractionCooldownViolation`; CI OpenAPI-drift check passes. Depends on T018.
- [x] T020 [P] [US1] Create `frontend/src/components/InteractionConfirmModal.tsx` mirroring `frontend/src/components/UntakeConfirmModal.tsx` (props `open`/`onConfirm`/`onCancel`, no native `<dialog>`): dynamic body naming the conflicting medication(s) and a live remaining time via `formatRemaining` from `frontend/src/lib/timers.ts`; confirm label "Take anyway"; visually distinct from a non-overridable overdose dead-end.
- [x] T021 [US1] Modify `frontend/src/hooks/useTakeDose.ts`: add `InteractionConflictError` (branch on `response.status === 409 && body.code === "interaction_cooldown_active"`, parallel to `MinIntervalError`/`WindowFullError`); on catch surface the conflict body; confirming retries the mutation with `interaction_acknowledged: true`; keep the existing optimistic snapshot/restore and the settle invalidation of `["today"]`/`["medications"]`/`["medication", id]`. Depends on T019.
- [x] T022 [US1] Wire the take-anyway flow into `frontend/src/routes/today.tsx` (and the `MedicationList` take control): an interaction 409 opens `InteractionConfirmModal`, never a dead-end; confirming records the dose. Depends on T020, T021.
- [x] T023 [P] [US1] `frontend/src/__tests__/InteractionConfirmModal.test.tsx` — body content, confirm/cancel callbacks, asserts the path is distinct from the non-overridable overdose rendering.
- [x] T024 [US1] Promote `docs/adr/0008-drug-interaction-enforcement.md` Status **`Proposed` → `Accepted`** (this story's PR, per FR-023 / matching ADR-0002's lifecycle).

**Checkpoint**: US1 fully functional and independently testable (warn, override, audited record, server-authoritative).

---

## Phase 4: User Story 2 — Conflict context + live cooldown timer (Priority: P2)

**Goal**: A legible, server-seeded, self-clearing interaction indicator
so the user can decide in advance, plus the explicit confirm step.

**Independent Test** (from `spec.md`): with an active A↔B cooldown
after dosing A, the today view and medication list show an indicator
naming A with a remaining time that ticks down, survives reload, and
clears on the next refetch when the cooldown elapses or A's dose is
voided — no manual reload.

**Note**: depends on US1's `detect_interaction_conflict` (spec
sequences US2 second by design).

### Tests for User Story 2 ⚠️

- [x] T025 [P] [US2] `backend/tests/api/test_interaction_state.py` — `interaction_state` present/correct on today, list, and detail per scenario; clears when the cooldown elapses and when the arming dose is voided; **cross-user negative** proving no rule/dose/conflict leaks (FR-019); plus an explicit case: a rule whose partner medication is soft-deleted produces no `interaction_state` and no enforcement error on the surviving medication (FR-018).
- [x] T026 [P] [US2] `frontend/src/__tests__/interactionIndicator.test.tsx` — indicator names the conflicting medication and shows a ticking remaining time; clears on refetch.

### Implementation for User Story 2

- [x] T027 [US2] Add `interaction_state: InteractionStateOut | None = None` to `MedicationOut` and `MedicationDetailOut` in `backend/src/medminder/api/schemas/medications.py` and to `TodayItem` in `backend/src/medminder/api/schemas/today.py`. Depends on T007.
- [x] T028 [US2] Wire `detect_interaction_conflict` + `to_interaction_state_out` into `backend/src/medminder/api/medications.py` (list **and** detail) and `backend/src/medminder/api/schedules.py` (today): compute at `now` from the user's interaction rules + `load_non_voided_history_for_meds` (`domain/doses.py`); user-scoped; exclude soft-deleted meds (no conflict, no surface — FR-018). Depends on T014, T007, T027.
- [x] T029 [US2] Run `just generate-client`; confirm `frontend/src/api/v1.d.ts` carries `interaction_state` on the three summary shapes; CI drift check passes. Depends on T027, T028.
- [x] T030 [P] [US2] Add the interaction indicator to `frontend/src/routes/today.tsx` and `frontend/src/components/medications/MedicationList.tsx`: human-readable status naming the conflicting medication(s) and the remaining cooldown (e.g. "Interacts with Sumatriptan — safe at 3:45 PM"); reuse `tickFrom`/`formatRemaining` from `frontend/src/lib/timers.ts` seeded from `interaction_state.as_of` (1s local tick, **no polling**); clears on the existing refetch-on-focus / post-mutation invalidation. Depends on T029.

**Checkpoint**: US1 + US2 both work independently; the conflict is legible before the user acts.

---

## Phase 5: User Story 3 — Setting up an interaction rule (Priority: P3)

**Goal**: Author / view / remove a symmetric A↔B rule from the
medication form's "Conflicts with" section — **create + delete only**
(changing a cooldown is delete-then-recreate). Committed deliverable;
demoable end-to-end with no admin/CLI step.

**Independent Test** (from `spec.md`): create a symmetric A↔B rule
with a positive cooldown via the form; the US1 warn/confirm flow
applies in both directions; remove it and both meds are takeable with
no warning.

### Tests for User Story 3 ⚠️

- [x] T031 [P] [US3] `backend/tests/api/test_medication_interactions_api.py` — create/list/delete; duplicate unordered pair → 409; self-pair or non-positive `cooldown_minutes` → 422; pairing a medication the user does not own → 404/403; cross-user listing isolation (FR-019/FR-020).
- [x] T032 [P] [US3] `frontend/src/__tests__/medicationForm.conflicts.test.tsx` — add/remove conflict rows; Zod refine rejects non-positive cooldown, self-pair, in-form duplicate; the selector offers only the user's own non-deleted meds excluding self + already-paired.

### Implementation for User Story 3

- [x] T033 [US3] Create `backend/src/medminder/api/medication_interactions.py` router: `POST` / `GET` / `DELETE` under `/api/v1/medications/{medication_id}/interactions` (**no update**). Validate both medications owned by the user and non-deleted; map the `ix_medication_interactions_pair` unique violation → 409; rely on `ck_interactions_distinct_pair` / `ck_interactions_cooldown_pos` and boundary validation → 422; `GET`/`POST` responses include `conflicting_medication_name`. Depends on T007.
- [x] T034 [US3] Mount the new router in `backend/src/medminder/app.py` `create_app`. Depends on T033.
- [x] T035 [US3] Run `just generate-client`; confirm `frontend/src/api/v1.d.ts` carries the rule endpoints + `InteractionRuleCreate`/`InteractionRuleOut`; CI drift check passes. Depends on T034.
- [x] T036 [P] [US3] Create `frontend/src/hooks/useMedicationInteractions.ts` (list/create/delete following the `useToday`/`useTakeDose` conventions; invalidate `["today"]`/`["medications"]`/`["medication", id]` on settle). Depends on T035.
- [x] T037 [P] [US3] Extend `frontend/src/components/medications/medicationFormSchema.ts`: add a `conflicts` array field; Zod `.refine()` for positive integer cooldown, no self-pair, no in-form duplicate pair.
- [x] T038 [US3] Add the "Conflicts with" section to `frontend/src/components/medications/MedicationForm.tsx`, between `ScheduleInput` and the `serverError` block: an "Add interaction" button appends repeatable rows (medication selector = the user's own non-deleted meds excluding this med + already-paired; positive cooldown number input; remove button); existing rules preload as removable rows; a cooldown change is modelled as remove + re-add (no update path). Depends on T036, T037.
- [x] T039 [US3] Orchestrate persistence: in `frontend/src/routes/medications.$id.edit.tsx` diff rules → create added / delete removed; in `frontend/src/routes/medications.new.tsx` POST the medication, then POST each rule with the returned id, and on a rule POST failure surface a partial-success error (medication saved; list which rules failed) so the user retries from the edit form. Depends on T036, T038.

**Checkpoint**: All three user stories independently functional; Phase 6 demoable end-to-end with no admin/CLI step.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, gates, and end-to-end validation across stories.

- [x] T040 [P] Fill `docs/diagrams/sequence-drug-interaction-check.md` with a Mermaid sequence diagram of the warn → acknowledge → record (+ override row) flow; add it to `docs/diagrams/README.md`'s list (FR-023).
- [x] T041 [P] Reconcile the UC-4.3 wording in `docs/user_stories.md` with ADR-0008 (warn + explicit confirm, server never refuses an acknowledged dose; preserve the server-authoritative / not-silently-bypassable intent) per the spec Assumptions / FR-023.
- [x] T042 [P] Complete `specs/006-drug-interaction-cooldowns/checklists/security.md` (cross-user isolation, rule-input boundary validation, override-audit write path, the three new endpoints) and mark every item `[x]`/`[~]` for the merge gate, including the SC-008 PR-security-note line.
- [x] T043 [P] Update `specs/006-drug-interaction-cooldowns/checklists/requirements.md` Notes — the "single clarification" line is stale (three clarifications now); non-blocking housekeeping.
- [x] T044 Run the full gate: `just lint`, `just typecheck`, `just test`. The project ≥ 85 % gate is machine-enforced (`--cov-fail-under=85`); additionally **manually inspect** the coverage report and confirm `domain/interactions.py` ≥ 95 % and no module < 70 % (e.g. `just test 2>&1 | grep 'medminder/domain/interactions'`), per FR-021/FR-022/SC-009 — these are review targets, not a build-failing gate. Then `cd backend && python -m alembic check` (empty diff) and `just generate-client` (tree clean).
- [x] T045 [P] Create `frontend/e2e/drug-interaction.spec.ts` (Playwright): seed an A↔B rule → mark A → attempt B → warning + remaining cooldown → "take anyway" → recorded with audited override → indicator clears on elapse/void (SC-007). Reuse the existing E2E login helper.
- [x] T046 Execute `specs/006-drug-interaction-cooldowns/quickstart.md` end-to-end — SC-001/003/005/006 and the FR-005 direct-API bypass + FR-019 cross-user are covered by the green backend integration suite (`test_doses_interaction_conflict.py`, `test_interaction_state.py`, `test_medication_interactions_api.py`); the US1/US2/US3 happy path (SC-007) is verified in a real browser by the passing `drug-interaction.spec.ts` against the rebuilt live stack. (Phase A baseline gate, US3 rule authoring, US1 warn/override, US2 indicator, cross-user isolation) and confirm SC-001…SC-008.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — T001 first.
- **Foundational (Phase 2)**: after Setup — **blocks all user stories**.
- **US1 (Phase 3)**: after Foundational. MVP.
- **US2 (Phase 4)**: after Foundational **and US1's `detect_interaction_conflict` (T014)** — the spec sequences US2 second by design.
- **US3 (Phase 5)**: after Foundational. Independent of US1/US2 (CRUD on rules); demoable on its own.
- **Polish (Phase 6)**: after all targeted stories.

### Within Each User Story

- Tests are written and FAIL before implementation.
- Models/detector before services; services before endpoints; backend schema before `just generate-client`; generated client before the frontend that consumes it.

### Parallel Opportunities

- Setup: T002, T003 in parallel (T001 first).
- Foundational: T004, T006, T007, T009 in parallel; T005 after T004; T008 after T005+T006.
- US1 tests T010–T013 in parallel; T015 ∥ T014; FE T020/T023 ∥ backend.
- US2 tests T025/T026 in parallel.
- US3 tests T031/T032 in parallel; T036/T037 in parallel.
- Polish: T040–T043, T045 in parallel; T044/T046 are gates (serial, last).

## Parallel Example: User Story 1

```bash
# Tests for US1 together (write first, expect red):
Task: "backend/tests/domain/test_interactions.py"
Task: "backend/tests/db/test_dose_interaction_overrides.py"
Task: "backend/tests/domain/test_doses_interaction_guard.py"
Task: "backend/tests/api/test_doses_interaction_conflict.py"

# Then in parallel: detector logic and the new model
Task: "Implement detect_interaction_conflict in domain/interactions.py"
Task: "Create db/models/dose_interaction_overrides.py"
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 →
4. **STOP & VALIDATE** US1 independently (seeded rule; warn/override/audit;
direct-API bypass test green; ADR-0008 → Accepted) → 5. Demo.

### Incremental Delivery

Setup + Foundational → US1 (MVP, ADR-0008 Accepted) → US2 (legibility,
depends on US1 detector) → US3 (self-service rule authoring) → Polish
(diagram, UC-4.3 reconcile, gates, E2E, quickstart). Each story is a
shippable increment.

## Notes

- `[P]` = different files, no dependency on incomplete tasks.
- Phase 5 overdose 409s run first and stay non-overridable; the
  interaction acknowledgment never weakens them (FR-010) — covered by T012.
- `MedicationInteractionConflict` lives in `domain/doses.py` (alongside
  the `DoseError` hierarchy); the detector + value objects live in
  `domain/interactions.py` which never imports `doses` — this ordering
  prevents a circular import (data-model.md).
- Git is the user's domain — no branch/commit/PR is created by these
  tasks; the speckit `after_tasks` hook is optional and not auto-run.
