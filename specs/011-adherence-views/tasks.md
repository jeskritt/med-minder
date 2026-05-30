---
description: "Task list for Long-term adherence views (Phase 9)"
---

# Tasks: Long-term adherence views

**Input**: Design documents from `/specs/011-adherence-views/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/adherence.openapi.yaml, quickstart.md

**Tests**: INCLUDED — the constitution (Principle II/V) and roadmap exit criteria require unit + integration tests for new behavior (coverage ≥ 85%). Per-story tests are written before their implementation.

**Organization**: Tasks grouped by user story. The shared backend read (domain classification + the per-medication adherence endpoint) is Foundational because both the calendar (US1) and the trend (US3) render from one payload.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 (Setup, Foundational, Polish carry no story label)
- Exact file paths are included in each task.

## Path Conventions

Web app: `backend/src/medminder/`, `backend/tests/`, `frontend/src/`. No new tables, no migration (adherence is derived — see data-model.md / research.md D1).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the module homes and wire the router so later tasks have somewhere to land.

- [x] T001 [P] Create skeleton `backend/src/medminder/domain/adherence.py` — module docstring, `DayStatus` enum (`taken|partial|missed|future|inactive`), and the frozen dataclasses (`DayAdherence`, `MedicationAdherence`, `CourseProgress`) from data-model.md, with `__all__`. No logic yet.
- [x] T002 Create skeleton `backend/src/medminder/api/adherence.py` — `APIRouter(prefix="/api/v1/adherence", tags=["adherence"])` and register it via `app.include_router(adherence_api.router)` in `backend/src/medminder/app.py`.

**Checkpoint**: Empty adherence module + mounted router; `just typecheck` stays green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared, derived read consumed by both the calendar (US1) and the trend (US3): pure day-status classification, the date-range DB orchestration, and the per-medication adherence endpoint (full `MedicationAdherence` shape with `course=None` placeholder). Plus the regenerated TS client.

**⚠️ CRITICAL**: No user-story frontend work can begin until T008 (client regeneration) completes.

### Tests (write first, ensure they fail)

- [x] T003 [P] Domain classification matrix in `backend/tests/domain/test_adherence.py`: taken/partial/missed/future/inactive; the 4h missed tolerance (FR-004); `days_of_week` honored so a Mon–Fri med is inactive (not missed) on weekends (research D3); PRN/unscheduled never "missed" (FR-006); voided doses excluded (FR-005/D4); current-TZ day bucketing incl. a DST/midnight-wrap case (FR-013/D5); `adherence_pct` excludes inactive + future days (FR-014/FR-017) and is `None` for PRN.
- [x] T004 [P] Endpoint tests in `backend/tests/api/test_adherence_api.py`: anonymous → 401; another user's medication id → 404 (own-data-only, FR-015); inverted range (`to` < `from`) and span > 366 days → 422 (FR-018); unknown `timezone` → 400; `adherence_pct` present (0–100, one decimal) for a scheduled med and `null` for a PRN med; `course` is `null` at this phase.

### Implementation

- [x] T005 [US-shared] Implement the pure classifiers in `backend/src/medminder/domain/adherence.py`: `classify_day(expected_slots, taken_slot_keys, now, tolerance=timedelta(hours=4))` → `DayStatus`, and `window_adherence_pct(days)` returning `(taken ÷ expected) × 100` as a **0–100** float rounded to one decimal (excluding inactive/future days), or `None` when nothing is expected (PRN). No DB imports (testable in isolation, Principle III).
- [x] T006 Implement `compute_medication_adherence(session, *, user, medication_id, from_date, to_date, timezone_override)` in `backend/src/medminder/domain/adherence.py`: load the med (own-data filter), its linked active schedules + non-voided doses across the range, bucket `taken_at` into local days per day via `resolve_today_bounds`, build expected slots per day honoring `days_of_week`, and assemble `days[]` + `adherence_pct`. Reuse the `not_(voided_exists)` pattern from `domain/doses.py`. Return `course=None` (filled in US2).
- [x] T007 Implement `GET /api/v1/adherence/medications/{medication_id}` in `backend/src/medminder/api/adherence.py`: strict Pydantic response models (`extra="forbid"`) matching `contracts/adherence.openapi.yaml`. The `from`/`to` query params and the response field are **aliased** (`from`/`to` are the wire names; declare `from_: date = Query(alias="from")` etc. with `populate_by_name=True`, since `from` is a Python keyword) so the regenerated client keeps `from`/`to`. Validate the range — inverted (`to` < `from`) or span > **366 days** → 422 (FR-018); unknown `timezone` → 400; 404 when the med is not owned. Delegates to `compute_medication_adherence`.
- [x] T008 Regenerate the typed client: run `just generate-client` and commit the updated `frontend/src/api/v1.d.ts` (the `MedicationAdherence` shape — `days`, `adherence_pct`, nullable `course` — must be present so the frontend compiles).

**Checkpoint**: `GET /adherence/medications/{id}` returns correct per-day statuses + percentage against real Postgres; client types regenerated. Calendar/trend frontends can now be built.

---

## Phase 3: User Story 1 - "Did I take it yesterday?" calendar view (Priority: P1) 🎯 MVP

**Goal**: A per-medication month calendar where each day is color-coded **and** icon-coded (taken/partial/missed/future/inactive), with month navigation and the window adherence %.

**Independent Test**: Open a scheduled medication's detail page; verify each past day shows the correct state with both color and a non-color icon, future days are gray, inactive days neutral, and paging months works (acceptance scenarios US1.1–US1.6, SC-002/SC-005).

### Tests (write first)

- [x] T009 [P] [US1] `frontend/src/__tests__/AdherenceCalendar.test.tsx`: each `DayStatus` renders the right color class **and** the right non-color icon (check/dash/cross/neutral); a tooltip exposes taken-of-expected counts.

### Implementation

- [x] T010 [P] [US1] `frontend/src/lib/adherence.ts`: a React-Query hook `useMedicationAdherence(medicationId, { from, to, timezone })` calling the typed `openapi-fetch` client.
- [x] T011 [US1] `frontend/src/components/adherence/AdherenceCalendar.tsx`: month grid; map each `DayStatus` to `mm-*` design tokens (never hardcoded colors) plus a check/dash/cross/neutral icon and accessible label; per-cell tooltip with counts.
- [x] T012 [US1] `frontend/src/components/adherence/AdherenceView.tsx`: month navigation (prev/current), drives the hook's `from`/`to`, shows the numeric `adherence_pct` readout (hidden when `null`), renders `<AdherenceCalendar>`.
- [x] T013 [US1] Embed `<AdherenceView medicationId=…>` in `frontend/src/routes/medications.$medicationId.tsx`.

**Checkpoint**: MVP — a user can answer "did I take it on day X?" at a glance for any scheduled medication.

---

## Phase 4: User Story 2 - Course progress & completion (Priority: P2)

**Goal**: For meds with a course size, show "N of M" and a clear "complete" state; voids decrease the count; no indicator when there's no course size. Display-only (no side effects).

**Independent Test**: Create a med with a course size, record doses, see "9 of 14" then "complete" at the total; void a dose and watch it drop; a med with no course size shows nothing (US2.1–US2.4).

### Tests (write first)

- [x] T014 [P] [US2] Extend `backend/tests/domain/test_adherence.py` (or `test_adherence_course.py`): `compute_course_progress` gives N-of-M, `complete` at/after total, decrements on void, and `None` when `total_doses` is NULL; assert reaching completion has **no** side effects on reminders/schedule/med record (FR-008).
- [x] T015 [P] [US2] `frontend/src/__tests__/CourseProgress.test.tsx`: renders "9 of 14", shows the complete state at the total, and is hidden when `course` is `null`.

### Implementation

- [x] T016 [US2] Implement `compute_course_progress(session, *, user, medication)` in `backend/src/medminder/domain/adherence.py` (non-voided count vs `total_doses`, `complete` flag) and populate the `course` block in `compute_medication_adherence` / the endpoint response. No schema change; `course` field already exists in the contract (no client regen needed).
- [x] T017 [P] [US2] `frontend/src/components/adherence/CourseProgress.tsx`: "N of M" + a "course complete" state (display-only).
- [x] T018 [US2] Render `<CourseProgress>` in `frontend/src/components/adherence/AdherenceView.tsx` when `course` is present.

**Checkpoint**: Course meds show progress and completion; US1 still works.

---

## Phase 5: User Story 3 - Trend view (stacked bars) (Priority: P3)

**Goal**: A denser per-day stacked-bar trend over a week/month window, rendered from the same payload, switchable with the calendar.

**Independent Test**: On a scheduled med, toggle to the trend view; each day is a bar whose height reflects expected doses and whose segments reflect taken/missed; switch week ⇄ month (US3.1–US3.2).

### Tests (write first)

- [x] T019 [P] [US3] `frontend/src/__tests__/AdherenceTrend.test.tsx`: bar height reflects `expected`, segments reflect `taken` vs missed for the window.

### Implementation

- [x] T020 [P] [US3] `frontend/src/components/adherence/AdherenceTrend.tsx`: per-day stacked bars from the same `days[]` array, using `mm-*` tokens for taken/missed segments.
- [x] T021 [US3] Add a calendar⇄trend toggle and a week/month window control to `frontend/src/components/adherence/AdherenceView.tsx` (window selection drives the existing `from`/`to`).

**Checkpoint**: Both views switchable; US1 and US2 unaffected. No backend change (served by Foundational).

---

## Phase 6: User Story 4 - CSV export of dose history (Priority: P3)

**Goal**: Export the user's full non-voided dose history as a downloadable CSV; soft-deleted meds marked "(removed)".

**Independent Test**: Trigger Export with history across meds (incl. one soft-deleted); the CSV has one row per non-voided dose with the documented columns and the removed marking (US4.1–US4.3, UC-6.3).

### Tests (write first)

- [x] T022 [P] [US4] `backend/tests/api/test_adherence_export.py`: columns + order (`medication_name, taken_at, quantity, unit, schedule_label, soft_deleted`); soft-deleted med name suffixed " (removed)" with `soft_deleted=true`; voided doses absent; `Content-Type: text/csv` + `Content-Disposition: attachment`; anonymous → 401; only the caller's own doses appear.

### Implementation

- [x] T023 [US4] Implement `iter_export_rows(session, *, user, timezone_override)` in `backend/src/medminder/domain/adherence.py`: non-voided doses across all the user's meds, `taken_at` in the user's current TZ, "(removed)" marking via `medications.deleted_at`.
- [x] T024 [US4] Implement `GET /api/v1/adherence/export.csv` in `backend/src/medminder/api/adherence.py`: build rows with the stdlib `csv` module and stream a `StreamingResponse` (`media_type="text/csv"`, `Content-Disposition: attachment; filename="medminder-doses.csv"`).
- [x] T025 [US4] Regenerate the client (`just generate-client`) to register the new route in `frontend/src/api/v1.d.ts`.
- [x] T026 [US4] `frontend/src/lib/adherence.ts` CSV-download helper (fetch blob → anchor click) and an **Export** action in the medications-list header (`frontend/src/routes/medications.index.tsx` / the list component).

**Checkpoint**: All four stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation deliverables (Principle IV) and the final gate. Doc tasks are parallel (different files).

- [x] T027 [P] Write `docs/adr/0016-adherence-derivation.md` (next free number): adherence derived & never stored (D1); "missed" = scheduled-and-untaken past a 4h tolerance, honoring `days_of_week` (D2/D3); current-TZ bucketing (D5); voids excluded (D4); course-completion display-only; security (own-data-only, PHI CSV not cached) + perf (future composite index) notes.
- [x] T028 [P] Resolve the "Open questions" in `docs/design/adherence-tracking.md` (voids excluded; user's current TZ).
- [x] T029 [P] Add a one-line "Phase 9 adds no tables (adherence derived)" note to `docs/diagrams/er.md`.
- [x] T030 [P] Update `docs/glossary.md`: "adherence %" (0–100, taken ÷ expected over the window), "missed", "course complete", and a note that **"expected" = scheduled doses honoring the schedule's days-of-week** (the canonical term used in code; "scheduled" is the user-facing synonym).
- [x] T031 [P] Confirm/refine `docs/user_stories.md` UC-6 against shipped behavior (calendar/trend/percentage/CSV).
- [x] T032 [P] Add a Phase 9 "surprises" note to `CLAUDE.md` (derived adherence; `days_of_week`-honoring divergence from `today_view`; CSV PHI handling).
- [x] T033 Run `quickstart.md` verification end-to-end; ensure `just lint`, `just typecheck`, and `just test` are green with coverage ≥ 85%.
- [x] T034 Write the PR "Security considerations" section (constitution Principle I + roadmap exit criteria): enumerate the new surface (2 read endpoints), the own-data-only scoping (FR-015), no-new-data-field justification, and the PHI-CSV handling (owner-only, unlogged, not cached). Reference ADR-0016.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. **Blocks all user stories** (US1/US3 render its payload; US2/US4 extend its module).
- **US1 (Phase 3)**: depends on Foundational (esp. T008 client regen). MVP.
- **US2 (Phase 4)**: depends on Foundational; touches the shared `AdherenceView.tsx` (sequence after US1's T012 to avoid a same-file conflict).
- **US3 (Phase 5)**: depends on Foundational; also touches `AdherenceView.tsx` (sequence after US1's T012).
- **US4 (Phase 6)**: depends on Foundational only; otherwise independent (separate endpoint + list header).
- **Polish (Phase 7)**: after the stories you intend to ship.

### Within Each Story

- Tests written first and failing → implementation.
- Domain (pure) before orchestration before endpoint; backend before the frontend that consumes it.
- `AdherenceView.tsx` is shared by US1/US2/US3 — those edits are sequential, not `[P]`, to avoid file conflicts.

### Parallel Opportunities

- Foundational tests T003 + T004 in parallel.
- US4 (T022–T026) can be built in parallel with US1/US2/US3 once Foundational is done (separate files).
- All Polish doc tasks T027–T032 in parallel.

---

## Parallel Example: Foundational tests

```bash
# Write the two failing test suites together:
Task: "Domain classification matrix in backend/tests/domain/test_adherence.py"
Task: "Endpoint tests in backend/tests/api/test_adherence_api.py"
```

## Parallel Example: Polish docs

```bash
Task: "Write docs/adr/0016-adherence-derivation.md"
Task: "Resolve open questions in docs/design/adherence-tracking.md"
Task: "Note 'no tables' in docs/diagrams/er.md"
Task: "Update docs/glossary.md"
Task: "Refine docs/user_stories.md UC-6"
Task: "Add Phase 9 surprises note to CLAUDE.md"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (the shared read + client regen) → 3. Phase 3 US1 (calendar).
4. **STOP and validate**: the calendar answers "did I take it?" for a scheduled med. This is the smallest shippable slice.

### Incremental Delivery

Foundational → **US1 (MVP, calendar)** → US2 (course progress) → US3 (trend toggle) → US4 (CSV export) → Polish (docs + gates). Each story is independently testable and adds value without breaking the previous ones.

---

## Notes

- No new tables/migrations — adherence is derived (data-model.md). The only generated-artifact step is `just generate-client` (T008, re-run at T025).
- `[P]` = different files, no incomplete dependencies. `AdherenceView.tsx` edits across US1/US2/US3 are intentionally **not** `[P]`.
- Style the calendar/trend with `mm-*` design tokens; every cell/segment needs a non-color signal (SC-005).
- FR-016 ("derivable without manual marking") has no dedicated task — it is satisfied structurally by the derived, no-schema design (research D1; realized in T005/T006). No "mark missed/skipped" action is built, by design.
- Git is the user's domain — commit at your own checkpoints; this plan does not auto-commit.
