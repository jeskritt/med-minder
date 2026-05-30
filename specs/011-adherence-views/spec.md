# Feature Specification: Long-term adherence views

**Feature Branch**: `011-adherence-views`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "@specs/roadmap.md phase 9"

## Clarifications

### Session 2026-05-30

- Q: The roadmap lists "taken / missed / skipped" — should an explicit "skipped" state be added, or is a scheduled-but-untaken day simply "missed"? → A: No skip action; a scheduled dose untaken past the tolerance window is "missed". No schema change (matches `docs/design/adherence-tracking.md`).
- Q: Should the views present a numeric adherence rate, or only the calendar colors / trend bars? → A: Yes — show a per-medication adherence percentage (taken ÷ scheduled, excluding inactive and future days) for the visible window.
- Q: When a course is complete, does anything happen beyond showing the state (e.g., stop reminders, prompt to archive)? → A: Display-only — no side effects on reminders, schedules, or the medication record.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "Did I take it yesterday?" calendar view (Priority: P1)

A user with a long-running prescription (Granny, Diabetic Dan) wants to glance at
a month at a time and instantly see, per day, whether their medication was taken.
They select one of their medications and see a calendar grid where each day is
color-coded — all doses taken, some taken, none taken, not-yet-due, or the med
wasn't active that day — with a non-color signal (icon) on each cell. They can
page back to previous months to spot a streak of misses.

**Why this priority**: This is the core question the whole phase exists to answer
("did I take my blood pressure medication yesterday? last week?"). It is the
single most valuable slice and delivers a usable MVP on its own.

**Independent Test**: With a medication that has a daily schedule and a history of
recorded doses, open the medication's adherence calendar; verify each day shows
the correct taken/partial/missed/future/inactive state with both color and icon,
and that month navigation moves through history.

**Acceptance Scenarios**:

1. **Given** a medication scheduled twice a day and both doses recorded yesterday,
   **When** the user opens the calendar, **Then** yesterday's cell shows the
   "all taken" state (green + check icon).
2. **Given** a medication scheduled twice a day with only one dose recorded on a
   past day, **When** the user views that day, **Then** the cell shows the
   "partial" state (yellow + dash icon).
3. **Given** a scheduled day in the past with no doses recorded and the tolerance
   window elapsed, **When** the user views that day, **Then** the cell shows the
   "missed" state (red + cross icon).
4. **Given** a day before the medication's start date or after its end date,
   **When** the user views that day, **Then** the cell shows the "inactive"
   (not-active) state and is excluded from any adherence percentage.
5. **Given** a scheduled day in the future, **When** the user views it, **Then**
   the cell shows the "future/not-yet-due" state (gray).
6. **Given** the calendar is open on the current month, **When** the user pages
   back, **Then** prior months render with the same per-day coloring.

---

### User Story 2 - Course progress & completion (Priority: P2)

A user on a fixed-course medication (e.g. a 14-dose antibiotic course) wants to
see how far through the course they are — "9 of 14" — and be told clearly when
the course is complete, so they know to stop.

**Why this priority**: This is the feature that finally gives `total_doses`
(course size, captured since Phase 3) its meaning. It is distinct from refill /
supply tracking (Phase 7) and high-value for acute-course personas, but the
calendar (P1) is the more universal need.

**Independent Test**: Create a medication with a course size set, record several
doses, and verify the medication's view shows a doses-taken-of-total indicator
that increments with each non-voided dose and surfaces a "complete" state when
the total is reached.

**Acceptance Scenarios**:

1. **Given** a medication with a course size of 14 and 9 non-voided doses
   recorded, **When** the user views it, **Then** they see "9 of 14".
2. **Given** the same medication reaches 14 recorded doses, **When** the user
   views it, **Then** a clear "course complete" state is shown.
3. **Given** a dose is voided (un-taken), **When** the user views the medication,
   **Then** the count decreases accordingly (voided doses do not count toward
   the course).
4. **Given** a medication with no course size set, **When** the user views it,
   **Then** no course-progress indicator is shown.

---

### User Story 3 - Trend view (stacked bars) (Priority: P3)

A user wants to see how they are doing over a window of time (a week or a month)
as a denser trend view — one bar per day, segmented by taken / partial / missed —
to spot patterns over time rather than answer the single-day question.

**Why this priority**: Answers a different ("how am I doing this month?") question
than the calendar and is cheap to add once adherence is well-modeled, but it is
additive rather than essential.

**Independent Test**: For a medication with dose history, switch to the trend view
and verify each day in the selected window renders a bar whose height reflects the
scheduled dose count and whose segments reflect taken vs missed, over a
configurable week/month window.

**Acceptance Scenarios**:

1. **Given** a medication scheduled three times a day, **When** the user views the
   trend for a past week, **Then** each day's bar height reflects three scheduled
   doses with taken/missed segments colored.
2. **Given** the trend view, **When** the user switches the window between week and
   month, **Then** the bars re-render for the selected range.

---

### User Story 4 - CSV export of dose history (Priority: P3)

A user (or a caregiver helping with medical paperwork) wants to export their dose
history as a CSV file — one row per recorded dose — so it can be shared with a
doctor or kept for records.

**Why this priority**: Explicitly required (UC-6.3) and valuable for medical
paperwork, but it is a one-off action rather than the everyday glance the calendar
provides.

**Independent Test**: With recorded doses across one or more medications (including
at least one soft-deleted medication), trigger the export and verify the CSV
contains one row per non-voided dose with the documented columns and that
soft-deleted medications are clearly marked.

**Acceptance Scenarios**:

1. **Given** a user with recorded doses, **When** they export, **Then** they
   receive a CSV with one row per non-voided dose containing the medication name,
   the time taken, the quantity, the unit, and the schedule label.
2. **Given** a dose belonging to a soft-deleted medication, **When** the user
   exports, **Then** that dose still appears and its medication name is marked as
   removed, so the historical record stays coherent.
3. **Given** a voided (un-taken) dose, **When** the user exports, **Then** that
   dose is not counted as a taken dose in the export.

---

### Edge Cases

- **PRN / unscheduled medications**: A medication with no schedule (timer mode
  `none` or `count_down` used as-needed) has no concept of a "missed" day. Such
  days are shown as taken (when a dose exists) or neutral/not-due, never red —
  "not taken today" is not a failure for PRN.
- **Voided doses**: A dose corrected via the un-take (compensating-void) flow is
  excluded from adherence counts, calendar coloring, course progress, and the
  taken-count in CSV.
- **Days outside the active window**: Days before `start_date` or after `end_date`
  are "inactive" (white) and excluded from any adherence percentage.
- **Multiple doses on one day**: A day where some but not all scheduled doses were
  taken is "partial", not "taken" or "missed".
- **Tolerance window straddling midnight / late doses**: A scheduled dose taken
  within the tolerance window but after midnight still counts toward the scheduled
  day it belongs to.
- **Time zone**: Dose times are interpreted in the user's *current* time zone for
  day-bucketing, consistent with the rest of the app, even if the dose was
  recorded while the user was in a different zone.
- **Course over-completion**: Recording more doses than the course size (e.g. 15
  of 14) still shows a sensible state rather than breaking; completion is reached
  at or beyond the total.
- **Empty history**: A medication with no recorded doses and no past scheduled
  days renders an empty/neutral calendar without errors.
- **Schedule changed mid-history**: When a medication's attached schedules changed
  over time, the calendar reflects what was expected per day as best the current
  data allows (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to view a per-medication monthly calendar where
  each day is classified as one of: all-doses-taken, partial, missed,
  future/not-yet-due, or inactive (medication not active that day).
- **FR-002**: Each calendar day's status MUST be conveyed by both color and a
  non-color signal (an icon and/or accessible text), so the view does not rely on
  color alone.
- **FR-003**: Users MUST be able to navigate the calendar to previous (and the
  current) months to review historical adherence.
- **FR-004**: A scheduled dose MUST be classified as "missed" only after a
  tolerance window past its scheduled time has elapsed with no matching recorded
  dose; before that window elapses it is not counted as missed.
- **FR-005**: Voided (un-taken) doses MUST be excluded from all adherence
  classification, course progress, and exported taken-dose counts.
- **FR-006**: For medications with no schedule (as-needed/PRN), the system MUST NOT
  classify any day as "missed"; such days show only taken or neutral states.
- **FR-007**: For medications with a course size (`total_doses`) set, users MUST be
  able to see a doses-taken-of-total progress indicator (e.g. "9 of 14") based on
  non-voided doses.
- **FR-008**: The system MUST surface a clear "course complete" state when a
  course medication reaches its total dose count. This is display-only — reaching
  completion MUST NOT alter the medication's reminders, schedules, or record.
- **FR-009**: Medications without a course size MUST NOT show a course-progress
  indicator.
- **FR-010**: Users MUST be able to view a per-medication stacked-bar trend over a
  configurable window (week or month), with one bar per day showing taken vs
  missed segments scaled to that day's scheduled dose count.
- **FR-011**: Users MUST be able to export their dose history as a CSV file with
  one row per non-voided dose, including medication name, time taken, quantity,
  unit, and schedule label.
- **FR-012**: The CSV export MUST include doses belonging to soft-deleted
  medications, with the medication name clearly marked as removed.
- **FR-013**: Day-bucketing for calendar, trend, and export MUST use the user's
  current time zone.
- **FR-014**: Inactive days (outside a medication's start/end window) MUST be
  excluded from any adherence percentage or rate the views present.
- **FR-015**: Adherence views MUST only expose the requesting user's own
  medications and dose history (no cross-user data access).
- **FR-016**: All adherence views and the export MUST be derivable from existing
  recorded data (doses, voids, medications, schedules) without requiring the user
  to manually mark days as missed or skipped.
- **FR-017**: For scheduled medications, the views MUST present a numeric adherence
  percentage (a 0–100 value, rounded to one decimal place) for the visible window,
  computed as (taken scheduled doses ÷ expected scheduled doses) × 100, excluding
  inactive and future days. PRN/unscheduled medications (which have no "missed") show
  no percentage.
- **FR-018**: The per-medication adherence window MUST be bounded: a requested range
  wider than 366 days, or with an end earlier than its start, is rejected rather than
  served.

### Key Entities *(include if feature involves data)*

- **Day adherence status**: A derived, per-medication, per-day classification
  (taken / partial / missed / future / inactive) computed from the medication's
  schedules and recorded (non-voided) doses for that day. Not separately stored.
- **Course progress**: A derived per-medication value — count of non-voided doses
  versus the medication's course size — and a completion flag. Not separately
  stored.
- **Export row**: One non-voided dose rendered as medication name (marked if the
  medication is removed), time taken, quantity, unit, and schedule label.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can determine whether a specific medication was taken on a
  specific past day in under 10 seconds from opening the app.
- **SC-002**: For any past day, the calendar's per-day status matches the user's
  actual recorded dose history (no false "missed" for days that were fully taken,
  and no "taken" for days with no qualifying dose) in 100% of cases.
- **SC-003**: A user on a fixed-course medication can see their exact progress
  ("N of M") and know when the course is complete without counting doses manually.
- **SC-004**: A user can export their full dose history to a file and open it in a
  spreadsheet, with every non-voided dose represented exactly once.
- **SC-005**: Every per-day status is distinguishable without relying on color
  (verified by the presence of an icon/text signal on every cell).

## Assumptions

- **No explicit "skipped" state exists or is being added.** The roadmap lists
  "taken / missed / skipped", but the data model has no user action that marks a
  dose as deliberately skipped (doses are append-only takes; corrections are
  compensating voids). This spec therefore models day status as taken / partial /
  missed / future / inactive (per `docs/design/adherence-tracking.md`); a
  scheduled day with no qualifying dose is "missed". Introducing a distinct
  user-facing "skip" action is out of scope for this phase.
- **Missed tolerance window is a fixed 4 hours in v1** (per the adherence design
  doc working assumption); making it per-medication configurable is deferred.
- **Voided doses are excluded** from adherence and counts (the honest answer is
  "they were corrected"); they are not separately reported in v1.
- **Time zone is the user's current zone**, consistent with the rest of the app,
  rather than the zone in effect when each dose was recorded.
- **Adherence is derived, not stored.** No new persisted entity is required; all
  views compute from existing `doses`, dose-void, `medications`, and `schedules`
  data. (Per-day expectation uses the medication's currently-attached schedules;
  precise reconstruction of historical schedule changes is out of scope for v1.)
- **CSV export covers the user's full dose history** across all their medications
  (a date-range filter is a possible later enhancement, not required here).
- **The adherence window is capped at 366 days** to bound work; the UI requests at most
  a month/window at a time, so the cap is a guard, not a normal-use limit. Inverted or
  over-cap ranges are rejected (FR-018).
- **"Expected" doses means scheduled doses honoring the schedule's days-of-week** — a
  slot only counts as expected (and so can be "missed") on the weekdays its schedule
  covers. "Expected" and "scheduled" refer to the same thing throughout.
- **These views are read-only reporting.** They do not let the user record,
  edit, or void doses; that remains the today/mark-as-taken surface.
- **Both calendar and trend views are in scope** (switchable), since the trend
  view's marginal cost is low once adherence is well-modeled.
