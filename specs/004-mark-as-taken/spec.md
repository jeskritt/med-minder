# Feature Specification: mark-as-taken

**Feature Branch**: `[004-mark-as-taken]`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "read @[specs/roadmap.md]and implement phase 4. make sure to include testion to keep coverage high"

## Overview

**The "Granny flow"**: The end-to-end user journey this phase delivers — log in → see today's medications → tap Taken → see the row marked taken with the time. Named in `specs/roadmap.md` as the Phase 4 acceptance demo. References to "Granny flow" in `plan.md` and `tasks.md` (T039) point to this scenario.

## Clarifications

### Session 2026-05-07
- Q: How should a "taken" dose be recorded in the database? → A: Insert into the existing `doses` table from Phase 1a (`user_id`, `medication_id`, `schedule_id`, `taken_at`, `quantity`). Phase 4 adds **no** columns to `doses`. (Supersedes the earlier draft answer that proposed a fresh table — that conflicted with Phase 1a decisions D4, D6, and D7.)
- Q: Once a medication is marked as "Taken" in the Today view, how should it be displayed? → A: Greyed out / checked off but remains in the list.
- Q: What happens if the network drops right as the user clicks "Taken" or the server responds with an error? → A: Optimistic update with rollback and error toast on failure.
- Q: How should "un-take" be recorded, given Phase 1a marks `doses` as append-only? → A: A new `dose_voids` table records the void as a compensating row; the original `doses` row is never updated or deleted. Readers join `dose_voids` to filter out voided doses.
- Q: A medication can be on multiple schedules with different times — how does the Today view distinguish "morning taken, evening pending"? → A: The Today view is keyed per scheduled slot, the `(schedule_id, medication_id)` pair. `POST /api/doses` carries the slot's `schedule_id` so each slot is tracked independently. Ad-hoc doses (no slot) are still allowed with `schedule_id = null`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mark Medication as Taken (Priority: P1)

Users need to mark a medication as taken so they can track their adherence and not accidentally double-dose.

**Why this priority**: This is the core functionality of Phase 4 and answers the primary need: "did I take it, and when?".

**Independent Test**: Can be tested independently by logging in, viewing a medication, clicking "Taken", and observing the status update.

**Acceptance Scenarios**:

1. **Given** a medication that has not been taken today, **When** the user clicks the "Taken" toggle, **Then** the medication is marked as taken and a timestamped record is saved against the specific scheduled slot.
2. **Given** a medication that was taken, **When** the user views the medication, **Then** it visibly shows as taken with the time it was taken.
3. **Given** a medication scheduled twice in one day (morning and evening), **When** the user marks the morning slot taken, **Then** the evening slot remains in its untaken state.

---

### User Story 2 - View Today's Medications (Priority: P1)

Users need a consolidated view of all medications scheduled for today so they know exactly what they need to take without looking through their entire medication history.

**Why this priority**: Users need a single place to see what they need to take today to manage their daily routine effectively.

**Independent Test**: Can be tested by adding medications with different schedules and verifying that only those scheduled for the current day appear in the "Today" view.

**Acceptance Scenarios**:

1. **Given** a user has medications scheduled for today, **When** they navigate to the "Today" view, **Then** they see a list of all and only those medications.
2. **Given** a user on the "Today" view, **When** they mark a medication as taken from this view, **Then** the medication status immediately updates in the list.
3. **Given** a medication has been marked as taken, **When** it is displayed in the "Today" view, **Then** it remains in the list but is visually distinguished as completed (e.g., greyed out or checked off).

---

### User Story 3 - Undo "Mark as Taken" (Priority: P2)

Users occasionally make mistakes and click "Taken" accidentally, so they need a way to undo this action safely.

**Why this priority**: Prevents accidental data entry that could mess up the user's adherence tracking, but is secondary to the primary flow of taking medication.

**Independent Test**: Can be tested by marking a medication as taken, then attempting to un-take it and verifying the confirmation modal.

**Acceptance Scenarios**:

1. **Given** a medication marked as taken, **When** the user clicks to un-take it, **Then** a confirmation modal appears with the text "This med has already been taken. Remove the 'taken' status?".
2. **Given** the confirmation modal is open, **When** the user confirms the action, **Then** the slot returns to its "untaken" appearance and a void record is appended (the original taken-event is preserved as audit history, never deleted).
3. **Given** the confirmation modal is open, **When** the user cancels the action, **Then** the medication remains marked as taken.

### Edge Cases

- **Timezone travel**: handled by FR-004's `?timezone=` override; the user's stored `users.timezone` is not auto-updated by travel. Behavior beyond the override (auto-detect, suggest update) is out of scope for Phase 4.
- **Rapid, repeated clicking of the "Taken" toggle**: The toggle MUST be disabled while a `POST /api/doses` mutation is in flight (`useMutation.isPending`). The optimistic update flips the row to "taken" on first click; subsequent clicks during the in-flight window are no-ops. Backend has no per-slot uniqueness constraint — the UI is the contract.
- Network failure during action: The system handles this via optimistic UI updates with automatic rollback and user notification (see FR-008).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a toggle or button to mark a specific scheduled medication slot as taken.
- **FR-002**: System MUST record the exact timestamp when a dose is marked as taken, attributed to the session user.
- **FR-003**: System MUST display a "Today" view showing one row per scheduled slot for the user's current day; a medication on multiple schedules appears once per applicable slot.
- **FR-004**: System MUST determine "today" based on the user's configured timezone preference, with an optional override accepted from the client.
- **FR-005**: System MUST present a confirmation modal before allowing a user to remove a "taken" status. The text is exactly "This med has already been taken. Remove the 'taken' status?".
- **FR-006**: System MUST include an end-to-end (E2E) smoke test covering the core flow: login, add medication, mark as taken, view in today's list.
- **FR-007**: System MUST include unit and integration tests for all new behaviors. Backend coverage gate (≥85% across `backend/src/`, no module < 70%) is enforced by the constitution. Frontend new files added in this phase (`TakenToggle.tsx`, `UntakeConfirmModal.tsx`, `useTakeDose.ts`, `useUntakeDose.ts`, `useToday.ts`, `routes/today.tsx`) MUST each carry at least one Vitest test.
- **FR-008**: System MUST use optimistic UI updates for both marking a dose as taken and un-taking it: instantly reflect the change in the Today view, roll back on server error, and emit an error toast on rollback.
- **FR-009**: System MUST preserve `doses` rows as append-only history. Un-taking MUST be recorded as a separate compensating event, not as an update or delete of the original record.
- **FR-010**: System MUST link a dose to the scheduled slot it satisfies (when one applies), so per-slot adherence can be reported by the Today view.
- **FR-011**: System MUST scope all reads and writes to the session user; cross-user access MUST return `403`.

### Key Entities

- **Dose**: An append-only record of a medication-taken event. Already defined by Phase 1a in the `doses` table; Phase 4 adds no columns. Carries `user_id` (denormalized), `medication_id`, an optional `schedule_id` linking it to the slot the user satisfied, `taken_at`, and `quantity`.
- **DoseVoid**: A compensating row recording that a particular `doses` row should be ignored by the Today view and adherence queries. Lives in a new `dose_voids` table with a UNIQUE constraint on `dose_id`.
- **Today's List**: A read-only view computed by joining `schedules`, `schedule_medications`, `medications`, `doses`, and `dose_voids`, bounded by the user's timezone-aware "today" window. One row per `(schedule_id, medication_id)` slot that fires today.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully mark a medication as taken with a single click from the "Today" view.
- **SC-002**: The end-to-end smoke test for the Granny flow runs in CI without human intervention.
- **SC-003**: An "un-take" never occurs without an explicit user confirmation: the un-take request fires only after the FR-005 modal's confirm button is clicked. Verified by `UntakeConfirmModal.test.tsx` (cancel keeps state) and the Playwright smoke (cancel branch in T039).
- **SC-004**: The "Today" view computes the day window from the user's IANA timezone (or the `?timezone=` override). DST transitions, midnight wrap, and day-of-week selection are covered by `tests/domain/test_timezone.py`; integration coverage is in `tests/api/test_schedules_today.py`.

## Assumptions

- Users have already been created and authenticated (Phase 2 is complete).
- Medications and Schedules CRUD functionality exists and is operational (Phase 3 is complete).
- The user's timezone is available from their preferences (Phase 1a defined `timezone` on `users`).
- The `doses` table from Phase 1a is in place with its current shape (`id`, `user_id`, `medication_id`, `schedule_id`, `taken_at`, `quantity`, `created_at`) and the cross-table invariant `doses.user_id == medications.user_id` is enforced by the database (Phase 1a).
- The `schedule_medications` M:M association from Phase 1a is populated by Phase 3's medication/schedule CRUD.
