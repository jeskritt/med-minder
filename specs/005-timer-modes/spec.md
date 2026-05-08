# Feature Specification: Phase 5 — Timer Modes

**Feature Branch**: `2028-timer-modes`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "look at @specs/roadmap.md and implement phase 5. make sure to ket coverage high"

## Clarifications

### Session 2026-05-08

- Q: count_up display cap — should the displayed value cap at "over 24h ago"
  beyond 24 hours? → A: Yes; cap the display string at "over 24h ago" while
  the server payload still carries the full `elapsed_seconds` so downstream
  consumers (Phase 6 drug-interaction logic) retain the precision.
- Q: multi_sub_dose — what happens when a window expires with unused slots?
  → A: Present the mark-as-taken control as a "Dose available" button
  whenever no window is active or the active window has open slots; the
  next dose taken when no window is active starts a fresh window. When a
  window expires unused, show a passive banner ("Last window ended with N
  of M slots unused — tap when ready") that does not require
  acknowledgment, does not block any action, and clears when the next dose
  is taken. No missed-slot persistence record is created; the window
  exists solely to prevent overdose.
- Q: count_down — should haptic feedback fire when the timer reaches zero?
  → A: Yes; a single short vibration on the today view, only while the app
  is in the foreground. Devices without haptic capability degrade silently.
- Q: client refresh cadence — should the client poll on a timer for
  long-open tabs? → A: No; refetch only on focus and after mark-as-taken.
  The local monotonic counter keeps ticking between events.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Migraine Molly: count-up since last dose (Priority: P1)

Molly takes a migraine medication and needs to know, at a glance, how long ago
she last took it so she can decide whether other interacting medications (e.g.
Tylenol after a 2-hour cooldown) are safe to take. The app shows a
human-readable elapsed time ("Last dose 1h 47m ago") that advances in real
time without requiring her to refresh.

**Why this priority**: Smallest end-to-end timer slice and the foundation for
the entire timer architecture. ADR-0004 (timer state machines) graduates from
*Proposed* to *Accepted* on this story's PR. The count-up timer is also a
prerequisite for Phase 6's drug-interaction blocking, so it must land first.

**Independent Test**: Add a `count_up` medication, mark a single dose, return
to the today view and the medication list, observe an elapsed-time string
that increases in real time and survives a page reload (server-authoritative).

**Acceptance Scenarios**:

1. **Given** a `count_up` medication with no recorded doses, **When** the user
   opens the today view, **Then** the medication shows a "no doses recorded
   yet" indicator instead of an elapsed-time counter.
2. **Given** a `count_up` medication where the last non-voided dose was taken
   3 minutes ago, **When** the user opens the today view, **Then** the timer
   reads "3m ago" and increments at least once per visible minute without a
   page refresh.
3. **Given** a `count_up` medication that was last dosed 1h 12m ago,
   **When** the user reloads the page, **Then** the displayed elapsed time
   continues from 1h 12m within ±5 seconds of wall-clock truth (the server
   is authoritative; a skewed local clock cannot lie about the value).
4. **Given** a `count_up` medication whose most recent dose was voided
   (Phase 4 un-take), **When** the user views it, **Then** the timer ignores
   the voided dose and reflects the next-most-recent non-voided dose, or
   shows "no doses recorded yet" if none remain.

---

### User Story 2 — Headache Harry: count-down with min-interval guard (Priority: P2)

Harry takes ibuprofen as needed and is forgetful. He needs the app to tell
him whether he is allowed to take another dose right now, and how long until
the next one is permitted. The mark-as-taken action must be impossible until
the configured minimum interval has passed — both in the UI and at the
server, so a determined user (or buggy client) cannot overdose by issuing a
direct API call.

**Why this priority**: Adds server-side write enforcement on top of the
read-only display from US1, which is the riskier surface. Lands second so
the hybrid architecture from ADR-0004 has already been validated by US1.

**Independent Test**: Configure a `count_down` medication with
`min_interval_minutes = 120`. Mark a dose; verify the displayed remaining
time reads "1h 59m" and ticks down. With the cooldown still active, issue a
direct mark-as-taken request bypassing the UI: verify the server rejects
the request with a structured error and a non-zero remaining-seconds value.

**Acceptance Scenarios**:

1. **Given** a `count_down` medication with `min_interval_minutes = 60` and
   no doses, **When** the user views it, **Then** the mark-as-taken control
   is enabled and the displayed status reads "ready" (remaining = 0).
2. **Given** a `count_down` medication where the last dose was 10 minutes
   ago and the interval is 60 minutes, **When** the user views it,
   **Then** the displayed remaining time reads "50m" (or equivalent) and
   the mark-as-taken control is disabled.
3. **Given** the conditions in scenario 2, **When** a client issues a
   mark-as-taken request directly to the server, **Then** the server
   responds with a 4xx error whose body identifies the medication, the
   error code, the next-allowed timestamp, and the remaining seconds.
4. **Given** a `count_down` medication whose remaining time has reached
   zero, **When** the user clicks mark-as-taken, **Then** a new dose row
   is recorded and the counter resets to the full interval.
5. **Given** a `count_down` medication just on the boundary of zero,
   **When** the client and server independently evaluate the timer,
   **Then** they agree on whether the action is permitted (no flicker,
   no double-tap race).

---

### User Story 3 — Billy Bat: multi-sub-dose window (Priority: P3)

Billy is recovering from surgery and is prescribed a medication that allows
up to 3 sub-doses inside a rolling 6-hour window, ideally spaced evenly.
He needs to see, at any moment, how many sub-doses he has used inside the
current window and how many remain.

**Why this priority**: Most complex visual and state shape, smallest user
population. Lands last so the team can build on the patterns established
by US1 and US2.

**Independent Test**: Configure a `multi_sub_dose` medication with
`times_per_day = 3`, `window_duration_minutes = 360`. Mark one sub-dose and
verify the display shows "1 of 3 in this window" with the window's end
time visible. Mark a second; verify "2 of 3". Mark a third; verify "3 of
3" and that the mark-as-taken action becomes unavailable for the remainder
of the window.

**Acceptance Scenarios**:

1. **Given** a `multi_sub_dose` medication with no doses in the current
   window, **When** the user views it, **Then** the display reads "0 of N
   in this window" and the mark-as-taken control is enabled.
2. **Given** a partially-filled window (1 of 3 used, 4 hours remaining),
   **When** the user views it, **Then** the display shows the count, the
   timestamp of each used sub-dose, and the window-end time.
3. **Given** a fully-consumed window (3 of 3), **When** the user views it,
   **Then** the mark-as-taken control is disabled until the window ends
   and a new one begins.
4. **Given** a window that expired with sub-doses unused, **When** the
   user opens the medication, **Then** the mark-as-taken control reads
   "Dose available" and a passive banner identifies the count of
   unused slots from the previous window (per FR-008b); tapping the
   control starts a fresh window per FR-008 and clears the banner.

---

### Edge Cases

- **Mode `none` (Granny) is out of scope** for Phase 5. Granny's flow is
  unchanged from Phase 4 and stays that way.
- **Daylight-saving transitions** during a count-down or active sub-dose
  window. All timer arithmetic SHALL use UTC; user-facing strings honour
  the user's `timezone` field.
- **Soft-deleted medications** SHALL never appear in any timer-state
  response, even if their dose history is queryable.
- **Voided doses** (Phase 4 `dose_voids` rows) SHALL NOT count as the
  "last dose" for any of the three modes.
- **Cross-user isolation**: A user requesting timer state SHALL only see
  state for their own medications.
- **Clock skew**: Client wall-clock skew or manipulation SHALL NOT affect
  whether a dose is permitted; the server is authoritative.
- **Long-open tabs**: A tab left open for hours shows a counter that
  ticks locally but is not refetched until focus or a mark-as-taken
  event; brief visual flicker may occur on refocus when a `count_down`
  has just crossed zero.

## Requirements *(mandatory)*

### Functional Requirements

#### Shared

- **FR-001**: System MUST expose the current timer state for every
  non-deleted medication belonging to the logged-in user, on every
  endpoint that returns medication summaries (today view, medication
  list, single medication detail).
- **FR-002**: Timer state MUST be derived from the medication's
  configuration plus its non-voided dose history; voided doses MUST be
  excluded from "last dose" calculations.
- **FR-009**: The visible counter on the client MUST advance using a
  local monotonic clock seeded from the server-supplied state; the
  client MUST refetch on focus and after any mark-as-taken action.
  The client MUST NOT poll the server on a periodic timer between
  those events; staleness in a long-open tab is acceptable because
  the local counter continues to advance and refetches occur when
  the user returns focus.
- **FR-011**: The medication list view and today view MUST display
  each medication's timer state in human-readable form (e.g. "1h 12m
  ago", "in 47m", "2 of 3 in this window").
- **FR-012**: A state diagram for each of the three new modes MUST be
  added under `docs/diagrams/`, satisfying the per-phase exit criterion
  in `specs/roadmap.md`.
- **FR-013**: ADR-0004 (timer state machines) MUST move from `Proposed`
  to `Accepted`, authored alongside User Story 1.
- **FR-014** (security): Authorisation checks MUST prevent any
  timer-state query from leaking another user's medications or doses.
  This MUST be exercised in the test suite by a cross-user negative
  test.
- **FR-015** (typing): All new domain code MUST satisfy `mypy --strict`
  and the new client-side counter helper MUST satisfy `tsc --strict
  --noEmit`.
- **FR-016** (coverage): Project test coverage MUST remain at or above
  the existing 85% gate. The new timer-domain module MUST reach at
  least 95% line coverage given its pure-function nature; no module
  shall fall below the constitution's 70% per-module floor.

#### Mode `count_up` (User Story 1)

- **FR-003**: System MUST report time elapsed since the most recent
  non-voided dose, expressed in seconds, on every timer-state response
  for `count_up` medications. The human-readable display string MUST
  cap at "over 24h ago" once the elapsed time exceeds 24 hours; the
  underlying `elapsed_seconds` field MUST continue to advance with
  full precision so downstream consumers (Phase 6 drug-interaction
  logic) retain the data.

#### Mode `count_down` (User Story 2)

- **FR-004**: System MUST report time remaining until
  `last_dose_taken_at + min_interval_minutes`, clamped at zero.
- **FR-005**: The mark-as-taken endpoint MUST reject requests for
  `count_down` medications while the remaining time is greater than
  zero. The error response MUST include: a stable error code, the
  medication identifier, the next-allowed timestamp, and the remaining
  seconds.
- **FR-006**: The rejection in FR-005 MUST hold against direct API
  calls that bypass UI guarding. This MUST be exercised by an
  integration test that calls the API without going through the
  frontend.

#### Mode `multi_sub_dose` (User Story 3)

- **FR-007**: For each `multi_sub_dose` medication, system MUST report
  whether a window is active, and — when active — that window's start
  time, end time, the per-sub-dose taken-at timestamps inside it, the
  configured slot count (`times_per_day`), and the count of slots used.
- **FR-008**: A window is active when a non-voided dose's `taken_at`
  falls in `[window_start, window_start + window_duration_minutes)` and
  `now` is also within that interval. When no window is active, the
  next mark-as-taken action starts a new window with `window_start =
  taken_at`. No missed-slot record is persisted when a window expires
  with unused slots — the window exists solely to prevent overdose.
- **FR-008a**: The mark-as-taken control for a `multi_sub_dose`
  medication MUST be presented as "Dose available" whenever no window
  is active or the active window has unused slots, and MUST be
  disabled only when the active window is full
  (`slots_used >= times_per_day`).
- **FR-008b**: When the most recently expired window for a
  `multi_sub_dose` medication ended with one or more unused slots and
  no new dose has been taken since, the medication's detail and today
  views MUST display a passive informational banner identifying the
  count of unused slots (e.g. "Last window ended with 1 of 3 slots
  unused — tap when ready"). This banner MUST NOT require user
  acknowledgment, MUST NOT block any action, and MUST clear
  automatically once the next dose is recorded.

#### Cross-cutting UX

- **FR-010** (UX): Mobile devices MUST fire a single short haptic
  vibration when a `count_down` timer reaches zero, **only while the
  today view is in the foreground**. Devices without haptic capability
  MUST degrade silently.

### Key Entities

- **TimerState** *(value object, server-computed, not persisted)*:
  the current timer status for a medication. Fields:
  - `mode` — one of `none | count_up | count_down | multi_sub_dose`.
  - `as_of` — the server-side timestamp at which the state was
    computed.
  - `last_dose_at` — timestamp of the most recent non-voided dose,
    or null.
  - mode-specific payload:
    - `count_up`: `elapsed_seconds`.
    - `count_down`: `remaining_seconds`, `next_allowed_at`.
    - `multi_sub_dose`: `window_start`, `window_end`,
      `doses_in_window` (list of dose timestamps inside the window),
      `slots_total`, `slots_used`.
- **MinIntervalViolation** *(error response shape for FR-005 / FR-006)*:
  - `code` — stable string identifier (e.g. `"min_interval_not_elapsed"`).
  - `medication_id` — the medication whose interval was violated.
  - `next_allowed_at` — the timestamp at which a new dose becomes
    permitted.
  - `remaining_seconds` — non-negative integer.

No new persistent tables or columns are required: `medications` already
declares `timer_preference`, `min_interval_minutes`, and
`window_duration_minutes`; `doses` and `dose_voids` already store the
history needed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Molly sees a count-up timer for her migraine medication
  within 2 seconds of opening the today view; the displayed elapsed
  time matches wall-clock truth within 5 seconds across a 10-minute
  observation window.
- **SC-002**: Harry cannot record a second dose of a `count_down`
  medication before the configured interval has elapsed, even when
  issuing the request directly to the API. The block is verified by an
  integration test.
- **SC-003**: Billy can see at a glance how many sub-doses remain in
  the current window; sub-dose progress updates within 1 second of
  marking a dose.
- **SC-004**: Each persona's primary flow (Molly, Harry, Billy) passes
  on a deployed build before the phase is considered complete, per the
  definition of done in `specs/mission.md`.
- **SC-005**: Project test coverage stays at or above 85%; the new
  timer-domain module reaches at least 95% line coverage; the
  constitution's per-module 70% floor is preserved across the
  backend.
- **SC-006**: The client and server agree on whether a `count_down`
  has reached zero in 100% of observed cases (no flicker, no
  double-take). Verified by an end-to-end test that watches the
  enable/disable boundary of the mark-as-taken control.
- **SC-007**: All Phase 5 exit criteria from `specs/roadmap.md` are
  satisfied: state diagrams committed under `docs/diagrams/`, ADR-0004
  promoted to `Accepted`, and a security review note is present in the
  PR description for each user story.

## Assumptions

- Mode `none` (Granny) and the Phase 4 mark-as-taken loop are
  unchanged by this phase.
- Drug-interaction enforcement (UC-4.3 in `docs/user_stories.md`) is
  Phase 6, not Phase 5. Molly's count-up timer here is informational
  only; the cross-medication blocking that consumes it lands later.
- A client-side counter helper does not yet exist and will be authored
  during Phase 5. Whether it is generated from a declarative state-
  machine description or hand-ported from the Python source is decided
  during `/speckit-plan`, per ADR-0004's "Neutral" consequence.
- No new database tables or columns are required; the schema shipped
  in Phase 1 already carries `timer_preference`,
  `min_interval_minutes`, and `window_duration_minutes`, with CHECK
  constraints enforcing the mode-specific requirements.
- The `--cov-fail-under=85` gate in `backend/pyproject.toml` remains
  the project-wide floor. The user's "keep coverage high" direction is
  satisfied by treating 85% as a floor and 95% as a target on the new
  pure-function timer module, both verified in CI.
