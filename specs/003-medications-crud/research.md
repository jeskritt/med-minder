*# Research: Medications CRUD (Phase 3)

## 1. Timezone Handling for Dates and Schedules
- **Decision**: Store `start_date` and `end_date` as standard `date` objects in the database. `Schedule.time_of_day` will be stored as `time` without timezone (local wall-clock time).
- **Rationale**: A user taking meds at "8:00 AM" usually means 8:00 AM local time, even if they travel across timezones. Start/End dates are typically dates without times.
- **Alternatives considered**: Storing UTC timestamps for schedules. Rejected because travel would shift the displayed time unexpectedly for daily medications.

## 2. Soft-Delete Cascade Behavior
- **Decision**: `Schedule` records do not need their own `is_deleted` flag. They are implicitly ignored if their parent `Medication` is soft-deleted. When explicitly editing and deleting schedules, we can hard-delete the `Schedule` rows or rely on a complete replacement strategy during `PUT`.
- **Rationale**: Minimal data footprint. `PUT` operations for medication can simply delete old schedules and insert new ones for the medication, maintaining the correct state.
- **Alternatives considered**: Adding `is_deleted` to `Schedule`. Rejected as redundant state that can get out of sync.

## 3. Print Stylesheet Approach
- **Decision**: Use standard Tailwind CSS print modifiers (`print:hidden`, `print:block`, `print:text-black`, etc.) directly on the React components for the Medications List.
- **Rationale**: Tailwind natively supports `@media print` via the `print:` prefix, which integrates seamlessly into the existing Shadcn/UI component structure without requiring a separate CSS file.
- **Alternatives considered**: Creating a dedicated `print.css` file. Rejected because it violates the "single source of truth for styling" convention established by Tailwind.
