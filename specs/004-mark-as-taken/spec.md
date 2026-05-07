# Feature Specification: mark-as-taken

**Feature Branch**: `[004-mark-as-taken]`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "read @[specs/roadmap.md]and implement phase 4. make sure to include testion to keep coverage high"

## Clarifications

### Session 2026-05-07
- Q: How should a "taken" dose be recorded in the database? → A: A new `doses` table (e.g., `id`, `medication_id`, `taken_at`)
- Q: Once a medication is marked as "Taken" in the Today view, how should it be displayed? → A: Greyed out / checked off but remains in the list
- Q: What happens if the network drops right as the user clicks "Taken" or the server responds with an error? → A: Optimistic update with rollback and error toast on failure

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mark Medication as Taken (Priority: P1)

Users need to mark a medication as taken so they can track their adherence and not accidentally double-dose.

**Why this priority**: This is the core functionality of Phase 4 and answers the primary need: "did I take it, and when?".

**Independent Test**: Can be tested independently by logging in, viewing a medication, clicking "Taken", and observing the status update.

**Acceptance Scenarios**:

1. **Given** a medication that has not been taken today, **When** the user clicks the "Taken" toggle, **Then** the medication is marked as taken and a timestamped record is saved.
2. **Given** a medication that was taken, **When** the user views the medication, **Then** it visibly shows as taken with the time it was taken.

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
2. **Given** the confirmation modal is open, **When** the user confirms the action, **Then** the medication's taken status is removed and the history is updated.
3. **Given** the confirmation modal is open, **When** the user cancels the action, **Then** the medication remains marked as taken.

### Edge Cases

- What happens when a user travels across timezones and the definition of "today" changes?
- How does the system handle rapid, repeated clicking of the "Taken" toggle?
- Network failure during action: The system handles this via optimistic UI updates with automatic rollback and user notification (see FR-008).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a toggle or button to mark a specific medication dose as taken.
- **FR-002**: System MUST record the exact timestamp when a dose is marked as taken.
- **FR-003**: System MUST display a "Today" view showing all medications scheduled for the user's current day.
- **FR-004**: System MUST determine "today" based on the user's configured timezone preference.
- **FR-005**: System MUST present a confirmation modal before allowing a user to remove a "taken" status.
- **FR-006**: System MUST include an end-to-end (E2E) smoke test covering the core flow: login, add medication, mark as taken, view in today's list.
- **FR-007**: System MUST maintain high testing coverage by including unit and integration tests for all new behaviors.
- **FR-008**: System MUST use optimistic UI updates when marking a dose as taken, instantly showing success and rolling back with an error notification if the server request fails.

### Key Entities

- **Dose**: Represents a specific instance of taking a medication, recorded in a separate `doses` table containing the `medication_id` and the `taken_at` timestamp.
- **Today's List**: A dynamic view or collection of medications scheduled for the current day, based on user timezone and schedules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully mark a medication as taken with a single click from the "Today" view.
- **SC-002**: The E2E Playwright test successfully executes the complete Granny flow without human intervention.
- **SC-003**: Accidentally un-taking a medication is prevented 100% of the time via the confirmation modal.
- **SC-004**: The "Today" view accurately reflects scheduled medications based on the user's timezone settings 100% of the time.

## Assumptions

- Users have already been created and authenticated (Phase 2 is complete).
- Medications and Schedules CRUD functionality exists and is operational (Phase 3 is complete).
- The user's timezone is available from their preferences (Phase 1a defined `timezone` on `users`).
