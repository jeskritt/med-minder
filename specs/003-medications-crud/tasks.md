---
description: "Task list for Medications CRUD implementation"
---

# Tasks: Medications CRUD

**Input**: Design documents from `/specs/003-medications-crud/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create component directories in `frontend/src/components/medications/` and `frontend/tests/components/medications/`
- [ ] T002 [P] Create backend route directories in `backend/src/medminder/api/routes/` (if missing) and ensure they are ready to be linked to `app.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Create `Medication` and `Schedule` SQLAlchemy models in `backend/src/medminder/db/models/medications.py`
- [ ] T004 Generate Alembic migration for medications and schedules using `just migrate-rev` and apply using `just migrate`
- [ ] T005 [P] Create Pydantic schemas and business logic validation (e.g. "end date before start date", untracked total_doses as NULL) in `backend/src/medminder/domain/medications.py` to ensure domain logic is testable without DB/HTTP
- [ ] T006 Register medications router in `backend/src/medminder/api/routes/medications.py` and mount in main app

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Add a Medication (Priority: P1) 🎯 MVP

**Goal**: A user can add a new medication to their profile with its required dosage and schedule information.

**Independent Test**: User can successfully submit a new medication form and see it appear in their list.

### Implementation for User Story 1

- [ ] T007 [US1] Implement `POST /api/v1/medications` endpoint in `backend/src/medminder/api/routes/medications.py` utilizing the domain logic functions
- [ ] T008 [US1] Regenerate frontend OpenAPI client definitions by running `just generate-client`
- [ ] T009 [P] [US1] Create `ScheduleInput` component for managing schedules inline in `frontend/src/components/medications/ScheduleInput.tsx`
- [ ] T010 [US1] Create `MedicationForm` component (Add mode) utilizing react-hook-form and zod in `frontend/src/components/medications/MedicationForm.tsx`. Ensure schema validation handles "end date before start date" and provides an "Untracked / As Needed" checkbox for 0 total doses
- [ ] T011 [US1] Create `frontend/src/routes/medications.new.tsx` to mount the `MedicationForm` and handle submission via TanStack Query

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - List Medications (Priority: P1)

**Goal**: A user can view a complete list of all their active medications.

**Independent Test**: User can view a list of medications that have been added to their profile.

### Implementation for User Story 2

- [ ] T012 [P] [US2] Implement `GET /api/v1/medications` endpoint in `backend/src/medminder/api/routes/medications.py`
- [ ] T013 [P] [US2] Create `MedicationList` component for rendering the list of medications in `frontend/src/components/medications/MedicationList.tsx`
- [ ] T014 [US2] Create `frontend/src/routes/medications.tsx` page to fetch data via TanStack Query and display `MedicationList`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Edit a Medication (Priority: P2)

**Goal**: A user can update the details of an existing medication.

**Independent Test**: User can edit an existing medication and see the updated details reflected in their list.

### Implementation for User Story 3

- [ ] T015 [P] [US3] Implement `PUT /api/v1/medications/{id}` endpoint in `backend/src/medminder/api/routes/medications.py`
- [ ] T016 [US3] Update `MedicationForm` to support editing mode with pre-filled default values in `frontend/src/components/medications/MedicationForm.tsx`
- [ ] T017 [US3] Create `frontend/src/routes/medications.$id.edit.tsx` page to fetch a single medication and mount the pre-filled form

**Checkpoint**: All core CRUD features for adding, listing, and editing are now functional.

---

## Phase 6: User Story 4 - Delete a Medication (Priority: P2)

**Goal**: A user can remove a medication from their profile.

**Independent Test**: User can delete an existing medication and verify it is removed from their list.

### Implementation for User Story 4

- [ ] T018 [P] [US4] Implement `DELETE /api/v1/medications/{id}` (soft-delete) endpoint in `backend/src/medminder/api/routes/medications.py`
- [ ] T019 [US4] Add a delete button to the `MedicationList` items that triggers a TanStack mutation and invalidates the list query in `frontend/src/components/medications/MedicationList.tsx`

---

## Phase 7: User Story 5 - Print Medication List (Priority: P3)

**Goal**: A user can print a clean, formatted list of their medications to share with their doctor.

**Independent Test**: User can trigger a print dialog on the medications page and see a print-optimized layout.

### Implementation for User Story 5

- [ ] T020 [P] [US5] Add a Print button and Tailwind print modifiers (`print:hidden`, `print:block`) to `MedicationList` and `medications.tsx` layout in `frontend/src/components/medications/MedicationList.tsx`

---

## Phase 8: User Story 6 - Schedule Count Warning (Priority: P3)

**Goal**: A user is warned if the number of scheduled times doesn't match the "times per day" they entered.

**Independent Test**: User sees a warning message when "times per day" is 3 but only 2 schedules are attached.

### Implementation for User Story 6

- [ ] T021 [P] [US6] Add reactive validation warning in `MedicationForm` when the `times_per_day` value differs from the number of elements in the `schedules` array in `frontend/src/components/medications/MedicationForm.tsx`

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T022 [P] Write backend API tests covering CRUD operations in `backend/tests/test_medications_api.py`
- [ ] T023 [P] Write backend domain unit tests in `backend/tests/domain/test_medications.py` to test validation logic (e.g., dates, doses) independently of HTTP/DB and maintain >=85% `pytest-cov` coverage
- [ ] T024 [P] Write frontend component tests for form logic in `frontend/tests/components/medications/MedicationForm.test.tsx`
- [ ] T025 Run `just typecheck` and `just lint` to ensure fully-typed correctness across the stack
- [ ] T026 Run `/speckit-checklist` to generate `checklists/requirements.md` to satisfy the Constitution Phase 2+ merge gate requirement
- [ ] T027 Draft PR description including the required explicit threat consideration for new API endpoints and database fields, per Constitution Principle I

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 (Phase 3) and US2 (Phase 4) can proceed in parallel
  - US3 (Phase 5) depends on US1's form and US2's list
  - US4 (Phase 6) depends on US2's list
  - US5 (Phase 7) depends on US2's list
  - US6 (Phase 8) depends on US1's form
- **Polish (Final Phase)**: Depends on all user stories being complete

### Parallel Opportunities

- Foundational tasks for Models (T003) and Schemas (T005) can be developed concurrently
- Backend Endpoints and Frontend Components can be built simultaneously for each user story once schemas and endpoints are defined
- Print Stylesheet (US5) and Schedule Count Warning (US6) can be implemented independently by separate developers

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3 & 4: User Story 1 & 2 (Add & List)
4. **STOP and VALIDATE**: Verify users can add medications and see them appear on the dashboard.

### Incremental Delivery

1. Foundation ready
2. Add Medication & List Medication (MVP)
3. Edit Medication (Refining the form)
4. Delete Medication (Final CRUD action)
5. Add UI/UX Polish: Print styles and warnings
