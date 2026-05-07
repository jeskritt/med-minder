# Feature Specification: Medications CRUD

**Feature Branch**: 2027-medications-crud  
**Created**: 2026-05-06  
**Status**: Draft  
**Input**: User description: "look in specs/roadmap.md and specify phase 3"

## Clarifications

### Session 2026-05-06

- Q: How should Schedule entries be managed when adding or editing a Medication? → A: Inline: Manage schedules directly within the Add/Edit Medication form (saved together).
- Q: If a user enters an end date that is before the start date, what should the system do? → A: Prevent saving and show a form validation error.
- Q: How should the system handle a medication with 0 total doses? → A: UI provides an "Untracked / As Needed" checkbox. Backend uses `NULL` as a sentinel value; manual entry of `0` is prevented.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add a Medication (Priority: P1)

A user can add a new medication to their profile with its required dosage and schedule information.

**Why this priority**: Adding medications is the fundamental action required to track them.

**Independent Test**: User can successfully submit a new medication form and see it appear in their list.

**Acceptance Scenarios**:

1. **Given** the user is logged in, **When** they fill out the "Add Medication" form with name, dosage, unit, times per day, start date, and end date, **Then** the medication is saved to their profile and appears in their list.

---

### User Story 2 - List Medications (Priority: P1)

A user can view a complete list of all their active medications.

**Why this priority**: Users need to see what medications they are currently tracking to manage them.

**Independent Test**: User can view a list of medications that have been added to their profile.

**Acceptance Scenarios**:

1. **Given** the user has added medications, **When** they visit the medications page, **Then** they see a complete list of their medications with name, dosage, and frequency.

---

### User Story 3 - Edit a Medication (Priority: P2)

A user can update the details of an existing medication.

**Why this priority**: Medication dosages and schedules change frequently, so users must be able to update their records.

**Independent Test**: User can edit an existing medication and see the updated details reflected in their list.

**Acceptance Scenarios**:

1. **Given** the user has an existing medication, **When** they edit the medication and change the dosage, **Then** the updated dosage is saved and displayed in the medication list.

---

### User Story 4 - Delete a Medication (Priority: P2)

A user can remove a medication from their profile.

**Why this priority**: Users need a way to clean up their list if they stop taking a medication entirely or made a mistake.

**Independent Test**: User can delete an existing medication and verify it is removed from their list.

**Acceptance Scenarios**:

1. **Given** the user has an existing medication, **When** they confirm deletion of the medication, **Then** it is removed from their active list.

---

### User Story 5 - Print Medication List (Priority: P3)

A user can print a clean, formatted list of their medications to share with their doctor.

**Why this priority**: Older users often prefer physical copies of their medication lists for doctor visits.

**Independent Test**: User can trigger a print dialog on the medications page and see a print-optimized layout.

**Acceptance Scenarios**:

1. **Given** the user is on the medications list page, **When** they choose to print the page, **Then** the print preview shows a clean layout removing navigation and optimizing for paper.

---

### User Story 6 - Schedule Count Warning (Priority: P3)

A user is warned if the number of scheduled times doesn't match the "times per day" they entered.

**Why this priority**: Prevents data entry errors that could lead to missed or extra doses.

**Independent Test**: User sees a warning message when "times per day" is 3 but only 2 schedules are attached.

**Acceptance Scenarios**:

1. **Given** a user is editing a medication with "times per day" set to 3, **When** they have only 2 schedule slots defined, **Then** a clear warning is displayed indicating the mismatch.

### Edge Cases

- **End date before start date**: The system prevents saving and shows a form validation error.
- **0 Total Doses / Untracked**: The UI provides an "Untracked / As Needed" checkbox instead of allowing `0` doses. The backend stores `NULL` (not `0`) for `total_doses` when untracked.
- **Deleting taken medications**: The system uses a "soft-delete" approach to preserve historical data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to list all their medications.
- **FR-002**: System MUST allow users to add new medications with fields: name, dosage, unit, times_per_day, start date, end date, total_doses, and refill inventory fields. Schedules MUST be managed and saved inline within the same form.
- **FR-003**: System MUST allow users to edit existing medication details.
- **FR-004**: System MUST allow users to safely remove (soft-delete) medications.
- **FR-005**: System MUST display a warning when the count of attached schedules differs from the specified `times_per_day`.
- **FR-006**: System MUST provide a print stylesheet that formats the medication list cleanly for physical printing.

### Key Entities

- **Medication**: Represents a drug the user is taking. Key attributes: Name, Dosage, Unit, Times Per Day, Start Date, End Date, Total Doses, Refill Inventory.
- **Schedule**: Represents the specific time(s) of day a medication should be taken.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully add, edit, list, and delete medications without encountering errors.
- **SC-002**: The medication list page prints cleanly on standard letter/A4 paper without cutting off critical information or printing unnecessary UI elements.
- **SC-003**: The UI clearly displays a warning within 1 second of a mismatch between the `times_per_day` value and the number of schedules attached.

## Assumptions

- Deleting a medication will use a "soft-delete" approach to preserve historical data, as defined in Phase 1a.
- The UI will follow the established design language and use the components created in earlier phases.
- Refill inventory fields include at minimum: current count and threshold for refill warning.
