---

description: "Phase 5 — Timer Modes: actionable, dependency-ordered tasks"
---

# Tasks: Phase 5 — Timer Modes

**Input**: Design documents in `specs/005-timer-modes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/timers.openapi.yaml, quickstart.md

**Tests**: Test tasks **are** included for this feature. Both the user (`/speckit-specify` input "make sure to keep coverage high") and `research.md` D7 prescribe the test layout, and FR-016 / SC-005 set explicit numeric coverage gates (project ≥ 85 %, `domain/timers.py` ≥ 95 %, per-module floor 70 %).

**Organization**: Tasks are grouped by user story. Each user story is independently testable per its `Independent Test` block in `spec.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]** — task is parallelizable (different files, no dependency on incomplete tasks)
- **[Story]** — `[US1]`, `[US2]`, `[US3]` mapping to `spec.md` user stories. Setup / Foundational / Polish phases carry no story label.
- File paths are absolute repo-relative.

## Path Conventions (from `plan.md` Project Structure)

- Backend: `backend/src/medminder/`, tests under `backend/tests/`
- Frontend: `frontend/src/`, tests under `frontend/src/__tests__/`, E2E under `frontend/e2e/`
- Shared cross-language fixture: `backend/tests/domain/fixtures/timer_cases.json` (consumed by both pytest and vitest)
- Diagrams: `docs/diagrams/`
- ADR: `docs/adr/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pre-flight sanity and skeleton files used by every story. Phase 5 introduces no new runtime deps and no migrations, so this phase is intentionally thin.

- [x] T001 Verify working branch is `2028-timer-modes`, then run `just migrate` and confirm `alembic check` reports an empty diff (Phase 5 ships zero schema changes — `data-model.md` "Migration impact: NONE").
- [x] T002 [P] Create empty shared fixture file `backend/tests/domain/fixtures/timer_cases.json` with `{ "count_up": [], "count_down": [], "multi_sub_dose": [] }` shape so each story can append its cases.
- [x] T003 [P] Create three empty Mermaid placeholder files: `docs/diagrams/timer-count-up.md`, `docs/diagrams/timer-count-down.md`, `docs/diagrams/timer-multi-sub-dose.md` (filled per-story per FR-012).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain skeleton, wire schemas, exception infra, and FE helper skeleton. Every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 [P] Create `backend/src/medminder/domain/timers.py` skeleton: `TimerState` dataclass (with `mode`, `as_of`, `last_dose_at`), per-mode payload dataclasses (`CountUpPayload`, `CountDownPayload`, `MultiSubDosePayload`, `ActiveWindow`), `MinIntervalNotElapsedError` exception (attrs `medication_id: UUID`, `next_allowed_at: datetime`, `remaining_seconds: int`), and a top-level `compute_timer_state(med, doses, now) -> TimerState | None` that returns `None` for `timer_preference == 'none'` and raises `NotImplementedError` for the three real modes (filled per-story). No `sqlalchemy` / `fastapi` imports at runtime; use `if TYPE_CHECKING:` for model type hints.
- [x] T005 [P] Create `backend/src/medminder/api/schemas/timers.py` with Pydantic v2 strict models `TimerStateOut`, `CountUpPayload`, `CountDownPayload`, `MultiSubDosePayload`, `ActiveWindow` matching `contracts/timers.openapi.yaml` exactly.
- [x] T006 [P] Create `backend/src/medminder/api/schemas/errors.py` with `MinIntervalViolation` Pydantic model: `code: Literal["min_interval_not_elapsed"]`, `medication_id: UUID`, `next_allowed_at: datetime`, `remaining_seconds: int`.
- [x] T007 [P] Implement domain→wire conversion `to_timer_state_out(state: TimerState | None) -> TimerStateOut | None` in `backend/src/medminder/api/schemas/timers.py` (keeps `domain/timers.py` free of pydantic imports).
- [x] T008 Register FastAPI exception handler for `MinIntervalNotElapsedError` in `backend/src/medminder/app.py` (`create_app`): map to HTTP 409 with the `MinIntervalViolation` body. Depends on T004 + T006.
- [x] T009 [P] Create `backend/tests/domain/test_timers_no_db_imports.py`: import `medminder.domain.timers` then `assert "sqlalchemy" not in sys.modules and "fastapi" not in sys.modules` (Constitution Principle III enforcement). Implementation uses a subprocess so a sibling test's prior import of sqlalchemy cannot mask the violation.
- [x] T010 Add `timer_state: TimerStateOut | None` field (default `None`) to `MedicationOut` in `backend/src/medminder/api/schemas/medications.py` and to `TodayItem` in `backend/src/medminder/api/schemas/today.py`. Depends on T005. Also extracted `MedicationOut` / `MedicationBody` / `MedicationListOut` / `ScheduleOut` from inline `api/medications.py` into the new `api/schemas/medications.py`, and added the contract-required `timer_preference`, `min_interval_minutes`, `window_duration_minutes` fields to `MedicationOut`.
- [x] T011 Wire `compute_timer_state` + `to_timer_state_out` into `backend/src/medminder/api/medications.py` list handler and `backend/src/medminder/api/schedules.py` today handler. Both handlers must filter on `user_id` and exclude soft-deleted (`deleted_at IS NULL`) and voided doses when computing state. Depends on T004, T007, T010. New helper `load_non_voided_history_for_meds` added to `domain/doses.py`.
- [x] T012 [P] Create `frontend/src/lib/timers.ts` skeleton exporting `tickFrom(state, monotonicMs)`, `formatElapsed(seconds, locale?)`, `formatRemaining(seconds)`, `windowProgress(state)`. Stub bodies (return placeholders) so per-story tasks fill them. Types reference `components.schemas.TimerStateOut` from `frontend/src/api/v1.d.ts`.
- [x] T013 Run `just generate-client` to regenerate `frontend/src/api/v1.d.ts` so it carries the new `timer_state` fields and the future `MinIntervalViolation` shape (the OpenAPI is now driven by T005 + T006 + T010). Depends on T005, T006, T010. To surface `MinIntervalViolation` in the generated client now (rather than waiting on T035), `POST /api/doses` declares a `responses={409: {"model": MinIntervalViolation}}` entry.

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Migraine Molly: count-up since last dose (Priority: P1) 🎯 MVP

**Goal**: Server-authoritative count-up timer that ticks in the client and survives a page reload. ADR-0004 graduates `Proposed → Accepted` on this story's PR.

**Independent Test** (from `spec.md`): Add a `count_up` medication, mark a single dose, return to today view and medication list, observe an elapsed-time string that increases in real time and survives a page reload.

### Tests for User Story 1 ⚠️

> Write these tests FIRST and confirm they fail before T020 implementation.

- [ ] T014 [P] [US1] Append `count_up` cases to `backend/tests/domain/fixtures/timer_cases.json`: (a) no doses, (b) 3-min-old dose, (c) most-recent dose voided (next-most-recent surfaces), (d) elapsed > 24h (server still emits full `elapsed_seconds`), (e) ±5s wall-clock parity case.
- [ ] T015 [P] [US1] Create `backend/tests/domain/test_timers.py` with a `pytest.mark.parametrize` block over the `count_up` cases loaded from `fixtures/timer_cases.json`, asserting `compute_timer_state` returns the expected `TimerState` shape.
- [ ] T016 [P] [US1] Create `backend/tests/api/test_today_timer_state.py::test_count_up_in_today_response` (real Postgres + AsyncClient): asserts `TodayResponse.items[*].timer_state.count_up.elapsed_seconds` populates correctly, soft-deleted meds are absent, and a second user's medication does NOT leak (FR-014 cross-user isolation).
- [ ] T017 [P] [US1] Create `frontend/src/__tests__/timers.test.ts` parametrized over the same `count_up` JSON fixture: assert `tickFrom` advances `elapsed_seconds` correctly and `formatElapsed` produces the expected display string including the "over 24h ago" cap (FR-003).
- [ ] T018 [P] [US1] Create `frontend/src/__tests__/CountUpDisplay.test.tsx`: (a) no-dose state shows "no doses recorded yet", (b) 3-min state shows "3m ago" and re-renders ≥ once per minute under fake timers, (c) > 24h shows "over 24h ago".

### Implementation for User Story 1

- [ ] T019 [US1] Implement the `count_up` branch of `compute_timer_state` in `backend/src/medminder/domain/timers.py`: walk `doses` newest-first filtering voided, compute `elapsed_seconds = int((now - last.taken_at).total_seconds())`; emit `last_dose_at = None` and `elapsed_seconds = None` when no non-voided dose exists. Depends on T004.
- [ ] T020 [US1] Implement `tickFrom` and `formatElapsed` bodies in `frontend/src/lib/timers.ts`. `formatElapsed` returns `"Xm ago"` / `"Xh Ym ago"` and caps at `"over 24h ago"` for `seconds > 86400`. Depends on T012.
- [ ] T021 [P] [US1] Create `frontend/src/components/timers/CountUpDisplay.tsx`: seeds a monotonic clock from server `as_of`, advances via `setInterval(1000)` while the tab is focused, displays the formatted elapsed string, and re-syncs to server `elapsed_seconds` on each TanStack Query refetch.
- [ ] T022 [US1] Render `CountUpDisplay` in `frontend/src/routes/today.tsx` (per `item.timer_state.mode === 'count_up'`) and per-row in `frontend/src/routes/medications.index.tsx`.
- [ ] T023 [US1] Wire focus-driven refetch on the today + medication list TanStack queries (`refetchOnWindowFocus: true`); ensure NO periodic polling timer is added (FR-009).
- [ ] T024 [US1] Author `docs/diagrams/timer-count-up.md` with a Mermaid state diagram covering: `no_doses → first_dose → ticking → (most_recent_voided → ticking_from_prior | no_doses)` (FR-012).
- [ ] T025 [US1] Promote `docs/adr/0004-timer-state-machines.md` from `Status: Proposed` to `Status: Accepted` and ensure the US1 PR description references the promotion (FR-013).

**Checkpoint**: Run the US1 quickstart recipe (`Sumatriptan` create → mark dose → today view shows `elapsed_seconds`). User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 — Headache Harry: count-down with min-interval guard (Priority: P2)

**Goal**: Server-authoritative count-down with a 409 guard that holds against direct API calls (FR-006), surfaced cleanly in the UI.

**Independent Test** (from `spec.md`): Configure a `count_down` med with `min_interval_minutes = 120`. Mark a dose; verify "1h 59m" remaining ticks down. With cooldown active, issue a direct mark-as-taken request bypassing the UI; server rejects with structured 409 body and non-zero `remaining_seconds`.

### Tests for User Story 2 ⚠️

> Write these tests FIRST and confirm they fail before T035–T036 implementation.

- [ ] T026 [P] [US2] Append `count_down` cases to `backend/tests/domain/fixtures/timer_cases.json`: (a) no doses (ready, remaining=0), (b) 10m elapsed of 60m interval (remaining=3000s), (c) on-the-boundary at zero, (d) negative-clamped (last dose well past interval), (e) most-recent voided.
- [ ] T027 [P] [US2] Extend `backend/tests/domain/test_timers.py` with a `count_down` parametrize block over the new fixture cases.
- [ ] T028 [P] [US2] Create `backend/tests/domain/test_doses_count_down_guard.py` (uses async session fixture): happy-path dose creation, guard rejection raising `MinIntervalNotElapsedError`, voided previous dose does not block.
- [ ] T029 [P] [US2] Create `backend/tests/api/test_doses_count_down_guard.py`: hit `POST /api/doses` directly via `httpx.AsyncClient`; assert HTTP 409 + body matches `MinIntervalViolation` exactly (`code`, `medication_id`, `next_allowed_at`, `remaining_seconds ≥ 1`); confirm body echoes nothing not in the request (security checklist).
- [ ] T030 [P] [US2] Extend `backend/tests/api/test_today_timer_state.py` with `test_count_down_in_today_response` covering `remaining_seconds` clamp at zero and `next_allowed_at` correctness.
- [ ] T031 [P] [US2] Extend `frontend/src/__tests__/timers.test.ts` with `count_down` cases asserting `formatRemaining` outputs (`"1h 59m"`, `"50m"`, `"ready"` at zero).
- [ ] T032 [P] [US2] Create `frontend/src/__tests__/CountDownButton.test.tsx`: disabled while `remaining_seconds > 0`; calls `take.mutate` exactly at zero; surfaces 409 `MinIntervalViolation` body when API rejects.
- [ ] T033 [P] [US2] Create `frontend/e2e/timer-modes.spec.ts` with the SC-006 zero-boundary scenario (Playwright): client and server agree on enable/disable transition, no flicker, no double-take. Reuse `e2e/granny-smoke.spec.ts` login helper.

### Implementation for User Story 2

- [ ] T034 [US2] Implement the `count_down` branch of `compute_timer_state` in `backend/src/medminder/domain/timers.py`: emit `min_interval_seconds`, `next_allowed_at = last.taken_at + timedelta(minutes=med.min_interval_minutes)` (or `None` when no doses), `remaining_seconds = max(0, int((next_allowed_at - now).total_seconds()))`. Depends on T004, T019.
- [ ] T035 [US2] Implement the min-interval guard in `backend/src/medminder/domain/doses.py::create_dose` per research D3: after the existing ownership/schedule validation block, before the `Dose(...)` construction. When `med.timer_preference == "count_down"` and a non-voided previous dose exists with `taken_at + min_interval_minutes > taken_at_input`, raise `MinIntervalNotElapsedError`. Reuses helpers from `domain/timers.py`.
- [ ] T036 [US2] Implement `formatRemaining` body in `frontend/src/lib/timers.ts` (`"50m"`, `"1h 59m"`, `"ready"` at 0).
- [ ] T037 [P] [US2] Create `frontend/src/components/timers/CountDownButton.tsx`: monotonic-clock-driven ticking remaining time; disabled while `remaining_seconds > 0`; on click invokes `take.mutate`; on 409 surfaces the `MinIntervalViolation` body via toast / inline error.
- [ ] T038 [US2] Modify `frontend/src/components/TakenToggle.tsx` to recognise the 409 `MinIntervalViolation` body shape and surface its `remaining_seconds` (used by routes that embed `TakenToggle` outside the timers folder).
- [ ] T039 [US2] Render `CountDownButton` in `frontend/src/routes/today.tsx` and `frontend/src/routes/medications.index.tsx` for `mode === 'count_down'`.
- [ ] T040 [US2] Trigger a single short `navigator.vibrate(200)` on the today view when `remaining_seconds` transitions to `0`, only while `document.visibilityState === 'visible'`; degrade silently when `navigator.vibrate` is unavailable (FR-010).
- [ ] T041 [US2] Author `docs/diagrams/timer-count-down.md` Mermaid state diagram: `idle (no doses, ready) → cooldown (remaining > 0) → ready (remaining == 0) → cooldown` plus the `MinIntervalNotElapsedError` arrow on a forced API call.

**Checkpoint**: Run the US2 quickstart recipe — direct `curl` POST returns the documented 409 body; UI button enabled state matches the server's verdict at the boundary.

---

## Phase 5: User Story 3 — Billy Bat: multi-sub-dose window (Priority: P3)

**Goal**: Window arithmetic, "Dose available" CTA logic, FR-008b passive banner, and the new `GET /api/v1/medications/{id}` endpoint hosting the detail view.

**Independent Test** (from `spec.md`): Configure a `multi_sub_dose` med with `times_per_day = 3`, `window_duration_minutes = 360`. Mark sub-dose 1 → "1 of 3"; mark 2 → "2 of 3"; mark 3 → "3 of 3" and control disabled until window ends.

### Tests for User Story 3 ⚠️

> Write these tests FIRST and confirm they fail before T048–T049 implementation.

- [ ] T042 [P] [US3] Append `multi_sub_dose` cases to `backend/tests/domain/fixtures/timer_cases.json`: (a) no doses, (b) 1 of 3 mid-window, (c) 3 of 3 full-window-disabled, (d) window expired with 2 unused slots → `previous_window_unused_slots == 2`, (e) most-recent voided, (f) two back-to-back windows (the second still active, banner from first cleared per invariant 6).
- [ ] T043 [P] [US3] Extend `backend/tests/domain/test_timers.py` with `multi_sub_dose` parametrize block exercising `data-model.md` invariants 1–6 (window length, active iff `now ∈ [start, end)`, slots_used count, control disabled iff full, banner only when no new window started since expiry).
- [ ] T044 [P] [US3] Create `backend/tests/api/test_medication_detail.py`: 200 happy path on own med; 404 on other-user med; 404 on soft-deleted; 404 on unknown id. Assert all three 404 responses are observably indistinguishable (same body shape, same fields, no timing leak — FR-014, security checklist).
- [ ] T045 [P] [US3] Extend `backend/tests/api/test_today_timer_state.py` with `test_multi_sub_dose_in_today_response` covering active-window payload and `previous_window_unused_slots`.
- [ ] T046 [P] [US3] Extend `frontend/src/__tests__/timers.test.ts` with `multi_sub_dose` cases asserting `windowProgress` returns `{used, total, expired_unused}` correctly.
- [ ] T047 [P] [US3] Create `frontend/src/__tests__/MultiSubDoseCard.test.tsx`: "Dose available" CTA when window inactive or has unused slots; control disabled only when full; passive banner appears with `previous_window_unused_slots > 0`; banner clears when a new dose is recorded.

### Implementation for User Story 3

- [ ] T048 [US3] Implement the `multi_sub_dose` branch of `compute_timer_state` in `backend/src/medminder/domain/timers.py` per `data-model.md` invariants 1–6 and `research.md` D5. Walk doses newest-first to identify the active window's chain; compute `active_window` (or `None`); compute `previous_window_unused_slots` from the most-recently-expired-window-with-no-new-window-since rule.
- [ ] T049 [US3] Implement `windowProgress` body in `frontend/src/lib/timers.ts`.
- [ ] T050 [US3] Add `GET /api/v1/medications/{medication_id}` handler to `backend/src/medminder/api/medications.py` returning `MedicationDetailOut`. Respond with HTTP 404 (NOT 403) for: medication not found, medication owned by another user, medication soft-deleted. The three cases MUST be observably indistinguishable (same body, no timing differential). Include `timer_state` populated via `to_timer_state_out`.
- [ ] T051 [US3] Add `MedicationDetailOut` schema to `backend/src/medminder/api/schemas/medications.py` (initially equals `MedicationOut` per research D2; kept distinct for Phase 6 divergence).
- [ ] T052 [P] [US3] Create `frontend/src/hooks/useMedicationDetail.ts` consuming the new endpoint via the `openapi-fetch` client; cache key `["medication", id]`; `refetchOnWindowFocus: true`.
- [ ] T053 [P] [US3] Create `frontend/src/components/timers/MultiSubDoseCard.tsx` showing `slots_used`/`slots_total`, the window-end time (formatted in user TZ), the per-sub-dose timestamps, the "Dose available" CTA logic (FR-008a), and the FR-008b passive banner.
- [ ] T054 [US3] Create `frontend/src/routes/medications.$medicationId.tsx` detail route hosting `MultiSubDoseCard`. Note (project memory): a sibling layout `medications.tsx` with `<Outlet />` is required by TanStack dotted-file routing — verify it exists or create it.
- [ ] T055 [US3] Render `MultiSubDoseCard` in `frontend/src/routes/today.tsx` and `frontend/src/routes/medications.index.tsx` for `mode === 'multi_sub_dose'`.
- [ ] T056 [US3] Re-run `just generate-client` to surface `/api/v1/medications/{id}` and `MedicationDetailOut` in `frontend/src/api/v1.d.ts`.
- [ ] T057 [US3] Author `docs/diagrams/timer-multi-sub-dose.md` Mermaid state diagram: `inactive → first_dose_in_window (window opens) → partial → full (CTA disabled) → window_expired_unused_or_used → inactive (with banner if unused)`.
- [ ] T058 [US3] Add a Playwright scenario (or vitest with backdated fixture) to `frontend/e2e/timer-modes.spec.ts` exercising the FR-008b banner: backdate a dose 7h, GET detail, confirm banner reads "Last window ended with 2 of 3 slots unused — tap when ready"; tap; banner clears.

**Checkpoint**: Run the US3 quickstart recipe — sub-dose counts increment 1→2→3, fourth attempt 409s, the backdated-dose path produces the banner.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hit the SC-005 / SC-006 / SC-007 numeric gates and walk the security checklist.

- [ ] T059 [P] Run `just test` and confirm: project line coverage ≥ 85 %, `medminder/domain/timers.py` line coverage ≥ 95 %, no module < 70 % (FR-016 / SC-005). Coverage XML lives at `backend/coverage.xml`.
- [ ] T060 [P] Run `just lint` (ruff + eslint + prettier --check) and `just typecheck` (`mypy --strict` + `tsc --noEmit --strict`); both must pass.
- [ ] T061 Bring up the stack via `just dev`; execute the three `quickstart.md` recipes (Molly, Harry, Billy) end-to-end against a deployed-style build, including the backdated-dose banner path (SC-004).
- [ ] T062 Confirm `just migrate && alembic check` reports an empty diff (no autogen migration drift introduced by the phase).
- [ ] T063 [P] Walk `specs/005-timer-modes/checklists/security.md` and tick every box; per-PR threat-model paragraph included in US1 / US2 / US3 PR descriptions (constitution Principle I + SC-007).
- [ ] T064 Confirm the Phase 4 granny-flow Playwright smoke test (`mode === 'none'`) is still green — no regression introduced by the timer dispatch wiring.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup completion. Blocks all user stories.
- **Phase 3 / Phase 4 / Phase 5 (US1 / US2 / US3)**: each depends on Foundational. After Foundational lands they can proceed in parallel (with merge-conflict awareness on shared files — see "Within Each User Story" below).
- **Polish (Phase 6)**: depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: independent of US2 and US3. Adds `count_up` math + display; no write-side surface; no new endpoint.
- **US2 (P2)**: independent of US1 and US3. Adds the `count_down` math + the server-side guard (only path that creates a dose). Uses the same `MinIntervalNotElapsedError` infra (T006 + T008) that Foundational delivered.
- **US3 (P3)**: independent of US1 and US2. Adds the `multi_sub_dose` math + the new detail endpoint + the detail route.

Each story is independently testable per its `Independent Test` recipe. Stories share two files (`backend/tests/domain/fixtures/timer_cases.json`, `backend/tests/domain/test_timers.py`, `backend/tests/api/test_today_timer_state.py`, `frontend/src/__tests__/timers.test.ts`, `frontend/src/lib/timers.ts`, `backend/src/medminder/domain/timers.py`); merging them in series is straightforward (each story appends a parametrize block / branch).

### Within Each User Story

- Tests (T014–T018, T026–T033, T042–T047) MUST be written and FAIL before the corresponding implementation tasks.
- Domain math before frontend helper before component before route wiring.
- Diagram + ADR promotion (US1 only) ride alongside the story PR.

### Parallel Opportunities

- T002, T003 inside Setup.
- T004, T005, T006, T007, T009, T012 inside Foundational (different files; T008 sequences after T004 + T006; T010 sequences after T005; T011 sequences after T004 + T007 + T010; T013 sequences after T005 + T006 + T010).
- All tests within a single story marked [P] (different files).
- US1, US2, US3 can be staffed to three developers once Foundational is complete (with light merge coordination on the shared files listed above).

---

## Parallel Example: User Story 1

```bash
# Once Foundational is green, write all US1 tests in parallel:
Task: "Append count_up cases to backend/tests/domain/fixtures/timer_cases.json"
Task: "Create backend/tests/domain/test_timers.py count_up parametrize block"
Task: "Create backend/tests/api/test_today_timer_state.py::test_count_up_in_today_response"
Task: "Create frontend/src/__tests__/timers.test.ts count_up cases"
Task: "Create frontend/src/__tests__/CountUpDisplay.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational).
2. Phase 3 (US1: Migraine Molly count-up).
3. **STOP and VALIDATE**: run the US1 quickstart recipe against a deployed-style build.
4. Promote ADR-0004 to `Accepted` alongside the US1 PR (FR-013).
5. Demo / deploy the count-up MVP — Phase 5's foundational architecture is now validated.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → demo (count-up MVP, ADR-0004 accepted).
3. US2 → demo (server-side overdose guard verified by direct-API test).
4. US3 → demo (multi-sub-dose detail page + banner).
5. Phase 6 polish → coverage / typecheck / security-checklist green → ship.

### Parallel Team Strategy

After Foundational lands:

- Developer A → US1 (Molly / count-up).
- Developer B → US2 (Harry / count-down + guard).
- Developer C → US3 (Billy / multi-sub-dose + detail endpoint).

Coordinate merges on the six shared files listed above; conflicts are mechanical (each story appends a parametrize block / branch).

---

## Notes

- `[P]` = different files, no dependency on incomplete tasks.
- `[Story]` label maps each task to its user story for traceability against `spec.md`.
- Each user story is independently completable and testable per its `Independent Test`.
- Verify tests fail before implementing — particularly the cross-user isolation tests (T016, T029, T044), which are the security gates required by FR-014 and the security checklist.
- Commit after each task or logical group; `/speckit-git-commit` is wired as an optional `after_tasks` hook.
- Do not introduce a `.sh` / `.ps1` script pair, do not add new runtime dependencies, do not generate an Alembic revision — all three would violate Phase 5 invariants documented in `plan.md` and the security checklist.
