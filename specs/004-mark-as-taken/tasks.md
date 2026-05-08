---
description: "Task list for mark-as-taken (Phase 4)"
---

# Tasks: mark-as-taken

**Input**: Design documents from `/specs/004-mark-as-taken/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Tests are REQUIRED for this feature (FR-006 E2E smoke, FR-007 unit/integration coverage, 85% backend coverage gate from plan.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 maps to spec.md user stories

## Path Conventions

Web app split: `backend/src/medminder/`, `backend/tests/`, `frontend/src/`, `frontend/e2e/` per `plan.md` §Project Structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bring Playwright into the repo (first E2E framework here).

- [ ] T001 Add `@playwright/test` as devDependency and a `test:e2e` script in `frontend/package.json`; install Chromium binaries via `pnpm dlx playwright install chromium`
- [ ] T002 [P] Create `frontend/playwright.config.ts` with a `webServer` array: entry 1 runs `pnpm dev` (frontend, port 5173); entry 2 starts the backend (`docker compose up -d backend` locally, no-op in CI where the service container is already up — env-gated). Both entries health-check before tests run. Chromium only.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `dose_voids` schema and ORM model — every story reads or writes through them.

**⚠️ CRITICAL**: No story phase begins until Phase 2 is complete.

- [ ] T003 Create Alembic migration `backend/alembic/versions/0002_add_dose_voids.py` adding the `dose_voids` table (`id UUID PK`, `dose_id UUID NOT NULL UNIQUE FK→doses.id ON DELETE RESTRICT`, `voided_by_user_id UUID NOT NULL FK→users.id ON DELETE RESTRICT`, `voided_at TIMESTAMPTZ NOT NULL`, `created_at TIMESTAMPTZ NOT NULL`)
- [ ] T004 [P] Create `DoseVoid` SQLAlchemy model in `backend/src/medminder/db/models/dose_voids.py` using `uuid_pk()` and `created_at_col()` from `backend/src/medminder/db/types.py`; export from `backend/src/medminder/db/models/__init__.py`
- [ ] T005 [P] Add `dose_factory` and `dose_void_factory` helpers to `backend/tests/db/factories.py`
- [ ] T006 [P] DB constraint test in `backend/tests/db/test_dose_voids.py` covering UNIQUE on `dose_id`, RESTRICT FKs, and round-trip insert
- [ ] T007 Run `just migrate` to apply the new migration to the local Postgres service container

**Checkpoint**: Schema in place, model and factories ready; user stories can begin.

---

## Phase 3: User Story 1 — Mark Medication as Taken (Priority: P1) 🎯 MVP

**Goal**: A user can mark a specific scheduled slot as taken; an append-only `doses` row is recorded with `schedule_id` set.

**Independent Test**: Log in (Phase 2 cookie) → `POST /api/doses` with a valid `medication_id` + `schedule_id` → assert `201` and a row in `doses` with the session user as owner; `403` when the medication belongs to a different user; `422` when the schedule isn't linked to the medication.

### Tests for User Story 1 ⚠️

- [ ] T008 [P] [US1] Domain unit test `backend/tests/domain/test_doses.py::test_create_dose_*` covering: happy path, ownership check (403), schedule-linkage check (422), `quantity` default from `medications.quantity_per_dose`, soft-deleted medication rejected (422)
- [ ] T009 [P] [US1] API contract test `backend/tests/api/test_doses_create.py` covering `POST /api/doses` returning `201` (with response shape per `contracts/api.md`), `403` cross-user, `422` invalid linkage, `401` unauthenticated
- [ ] T010 [P] [US1] Vitest test `frontend/src/__tests__/TakenToggle.test.tsx` for optimistic update + rollback-on-error + error toast (mock TanStack Query mutation); **and** assert the rendered toggle is `disabled` while the mutation is pending (asserts no second `POST /api/doses` fires on rapid double-click)

### Implementation for User Story 1

- [ ] T011 [P] [US1] Pydantic request/response schemas `DoseCreate` and `DoseRead` in `backend/src/medminder/api/schemas/doses.py`
- [ ] T012 [US1] `create_dose(session_user, payload)` in `backend/src/medminder/domain/doses.py`: derives `user_id` from session; validates medication ownership; validates `schedule_id` is linked to medication via `schedule_medications` when provided; defaults `quantity` to `medications.quantity_per_dose`; inserts and returns the `Dose`
- [ ] T013 [US1] FastAPI router `POST /api/doses` in `backend/src/medminder/api/doses.py` calling `create_dose`; map domain errors → `403` / `422`
- [ ] T014 [US1] Register the doses router in `backend/src/medminder/app.py`
- [ ] T015 [US1] Run `just generate-client` to refresh `frontend/src/api/v1.d.ts`
- [ ] T016 [US1] `useTakeDose` mutation hook in `frontend/src/hooks/useTakeDose.ts` using TanStack Query `useMutation` with `onMutate` (cancel + snapshot + optimistic write to the today query cache), `onError` (restore snapshot + emit toast), `onSettled` (invalidate today query)
- [ ] T017 [US1] `TakenToggle` component in `frontend/src/components/TakenToggle.tsx` consuming `useTakeDose`, accepting `{ scheduleId, medicationId, dose }` props; the toggle MUST be `disabled` while `useTakeDose.isPending` is `true`

**Checkpoint**: `POST /api/doses` is contract-tested; the toggle component renders and round-trips against a mocked Today cache. Toggle is wired into the UI in US2.

---

## Phase 4: User Story 2 — View Today's Medications (Priority: P1)

**Goal**: A user can open `/today` and see one row per scheduled slot for today (in their timezone), each row showing whether the slot has been taken.

**Independent Test**: Seed two schedules with `time_of_day` 08:00 and 20:00 attached to the same medication, plus an unrelated user's medication → `GET /api/schedules/today?timezone=America/Los_Angeles` returns exactly two items in the right order, neither leaks the other user's data; `400` for an unknown IANA zone.

### Tests for User Story 2 ⚠️

- [ ] T018 [P] [US2] Timezone helper unit test `backend/tests/domain/test_timezone.py` covering DST boundaries, midnight wrap, dow-bit calculation
- [ ] T019 [P] [US2] Domain unit test `backend/tests/domain/test_today_view.py` covering: per-slot keying for a multi-schedule medication, voided dose excluded, soft-deleted medication/schedule excluded, only session user's data returned; **timezone override changes the day window** — same fixture, two `?timezone=` values that fall on different local dates, returns different item sets
- [ ] T020 [P] [US2] API contract test `backend/tests/api/test_schedules_today.py` covering response shape per `contracts/api.md`, `?timezone=` override, `?date=` debug aid, `400` invalid zone
- [ ] T021 [P] [US2] Vitest test `frontend/src/__tests__/today.test.tsx` for slot list rendering, greyed-out completed state, ordering by scheduled time, then medication name; **and that rows with `dose !== null` render the localized taken-time string**

### Implementation for User Story 2

- [ ] T022 [P] [US2] `resolve_today_bounds(user_tz, override_tz, date)` in `backend/src/medminder/domain/timezone.py` returning `(start_utc, end_utc, dow_bit)` using `zoneinfo`
- [ ] T023 [P] [US2] `TodayResponse` and `TodayItem` Pydantic schemas in `backend/src/medminder/api/schemas/today.py`
- [ ] T024 [US2] `today_view(session_user, timezone, date)` in `backend/src/medminder/domain/doses.py`: joins `schedules ⨝ schedule_medications ⨝ medications` filtered by `days_of_week` bit and ownership, `LEFT JOIN doses` on `(schedule_id, medication_id)` within `[start_utc, end_utc)`, `LEFT JOIN dose_voids` filtering `dv.id IS NULL`; orders by `time_of_day, medications.name`
- [ ] T025 [US2] FastAPI router `GET /api/schedules/today` in `backend/src/medminder/api/schedules.py` calling `today_view`; map invalid IANA zone → `400`
- [ ] T026 [US2] Register the schedules router in `backend/src/medminder/app.py`
- [ ] T027 [US2] Run `just generate-client` (idempotent if already run in T015 — re-run after the new endpoint lands)
- [ ] T028 [US2] `useToday` query hook in `frontend/src/hooks/useToday.ts` returning typed `TodayItem[]`; key includes the timezone the client passes (or `undefined` to use server-side default)
- [ ] T029 [US2] `frontend/src/routes/today.tsx` Today route: renders the slot list, uses `(schedule_id, medication_id)` as the React `key`, renders `TakenToggle` (from US1) per row; for items where `dose !== null`, greys the row out **and renders `dose.taken_at` formatted in the user's timezone (e.g., "Taken 8:14 AM")** next to the medication name; add a nav link from `__root.tsx` (or `index.tsx`) to `/today`

**Checkpoint**: MVP complete — Granny can log in, view her day, and tap "Taken." Phase 5 adds undo.

---

## Phase 5: User Story 3 — Undo "Mark as Taken" (Priority: P2)

**Goal**: A user can un-take a slot through a confirmation modal; the original `doses` row is preserved and a `dose_voids` row is appended.

**Independent Test**: Insert a dose for the session user → `POST /api/doses/{id}/void` returns `204` and inserts a `dose_voids` row; second call returns `409`; cross-user dose returns `403`; nonexistent id returns `404`.

### Tests for User Story 3 ⚠️

- [ ] T030 [P] [US3] Domain unit test additions in `backend/tests/domain/test_doses.py::test_void_dose_*` covering happy path, double-void (409 mapped from `IntegrityError`), cross-user (403), missing dose (404)
- [ ] T031 [P] [US3] API contract test `backend/tests/api/test_doses_void.py` covering `204`, `403`, `404`, `409`, `401` unauthenticated
- [ ] T032 [P] [US3] Vitest test `frontend/src/__tests__/UntakeConfirmModal.test.tsx`: modal text matches FR-005 exactly, cancel keeps state, confirm fires the mutation

### Implementation for User Story 3

- [ ] T033 [US3] `void_dose(session_user, dose_id)` in `backend/src/medminder/domain/doses.py`: load dose; if missing → `NotFound`; if `dose.user_id != session_user.id` → `Forbidden`; insert `dose_voids` row; on `IntegrityError` for the UNIQUE → `Conflict`
- [ ] T034 [US3] FastAPI router `POST /api/doses/{dose_id}/void` in `backend/src/medminder/api/doses.py` returning `204`; map domain errors → `403` / `404` / `409`
- [ ] T035 [US3] Run `just generate-client` to expose the void endpoint to the typed client
- [ ] T036 [US3] `useUntakeDose` mutation hook in `frontend/src/hooks/useUntakeDose.ts` mirroring the optimistic pattern from `useTakeDose` (snapshot today cache, optimistic clear of `dose`, restore on error with toast, invalidate on settle)
- [ ] T037 [US3] `UntakeConfirmModal` component in `frontend/src/components/UntakeConfirmModal.tsx` using shadcn/ui `Dialog`; body text MUST be exactly: `This med has already been taken. Remove the 'taken' status?` (FR-005)
- [ ] T038 [US3] Wire `UntakeConfirmModal` into `TakenToggle.tsx`: clicking a row whose `dose !== null` opens the modal; confirm calls `useUntakeDose`; cancel closes without mutation

**Checkpoint**: All three stories independently testable; full Granny flow available.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T039 Playwright smoke `frontend/e2e/granny-smoke.spec.ts` covering FR-006: log in → create medication with one schedule → open `/today` → click Taken → assert greyed-out → open confirm modal → cancel → confirm un-take → assert untaken
- [ ] T040 [P] Update ER diagram `docs/diagrams/er.md` to include `dose_voids` and its relationships
- [ ] T041 [P] Run `quickstart.md` manual verification on a clean dev DB
- [ ] T042 Verify gates: `just test-backend` ≥ 85% coverage; `pnpm test` (Vitest) green; `pnpm test:e2e` (Playwright Chromium) green; ensure CI runs the smoke without `continue-on-error`; verify Vitest reports a test for each new frontend file listed in FR-007

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** — independent; can start immediately.
- **Foundational (Phase 2)** — depends on Setup; **blocks all user stories** (the model and migration are read by every story).
- **US1, US2, US3 (Phase 3, 4, 5)** — all depend on Phase 2. US1 and US2 can be developed in parallel; US3 can also be developed in parallel but its frontend component (`UntakeConfirmModal`) is wired into `TakenToggle` in T038, so T038 depends on T017 landing.
- **Polish (Phase 6)** — depends on US1+US2 (for the smoke) and on US3 (for the un-take leg of the smoke).

### Within Each User Story

- Tests are written first (each story's `T0##` test tasks come before its implementation tasks per the order above).
- Pydantic schemas → domain function → FastAPI router → app.py registration → typed-client regen → frontend hook → frontend component / route.
- `just generate-client` is re-run after each backend story merges new endpoints — idempotent if endpoints haven't changed.

### Parallel Opportunities

- T002 in parallel with T001's install step.
- Within Phase 2: T004 / T005 / T006 are `[P]` (different files; T006 doesn't run against a real DB until T007 applies the migration — keep them written together, run T006 after T007).
- Within US1: T008 / T009 / T010 / T011 in parallel; T012 starts after T011.
- Within US2: T018–T023 all `[P]`; T024 starts after T022 + T023.
- Within US3: T030 / T031 / T032 in parallel.
- US1 and US2 can be staffed to two devs in parallel after Phase 2.

---

## Implementation Strategy

### MVP first (P1 only)

1. Phase 1 → Phase 2.
2. US1 → contract green.
3. US2 → Today view live, MVP demo.
4. **STOP, validate**, ship.

### Incremental delivery

- MVP (US1 + US2) → demo.
- Add US3 (undo) → demo.
- Polish (E2E smoke + diagram update + coverage gate) → ship.

### Notes

- All backend writes derive `user_id` from the session — never accept it from the request body (plan §Constitution Check I).
- `doses` is append-only; un-take flows through `dose_voids` (Phase 1a D6).
- The Today response is the only place the dose state surfaces; the cache key
  for `useToday` is the single source of truth the optimistic mutations
  manipulate.
