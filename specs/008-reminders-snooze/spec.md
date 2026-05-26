# Feature Specification: Reminders + Snooze

**Feature Branch**: `008-reminders-snooze`
**Created**: 2026-05-23
**Status**: Draft
**Input**: User description: "roadmap phase 7"

## Clarifications

### Session 2026-05-23

- Q: Which field is the authoritative live "on hand" count that decrements on take and
  restores on void, and that triggers the refill warning? → A: **`refill_count`**, warning
  when it reaches **`refill_threshold`**. This matches the existing medication form and
  list UI. The glossary and UC-5.4 (which say `doses_remaining`) are doc drift and MUST be
  corrected in the doc sweep. `doses_remaining`/`total_doses_filled` remain unused.
- Q: How much of the push enablement UI is in Phase 7 vs Phase 8? → A: **Minimal** — Phase
  7 ships Web Push delivery (VAPID), a subscription-registration endpoint, a minimal
  service worker that displays notifications, and a basic "Enable notifications" control,
  enough to verify the loop end-to-end. The polished permission/onboarding UX stays in
  Phase 8 (PWA polish).
- Q: Are dose reminders per-medication or per-schedule? → A: **Per-schedule**, as the
  `reminders` table CHECK constraint already requires (`type='dose'` ⇒ `schedule_id` set,
  `medication_id` null). One reminder per schedule slot; the notification names the
  medication(s) attached to that schedule.
- Q: What is the snooze duration and can a reminder be re-snoozed? → A: **One hour** (fixed,
  per UC-5.2). Re-snoozing is allowed (no hard cap in v1).
- Q: Do refill warnings apply a default threshold when none is set? → A: **No** — refill
  warnings are opt-in: they fire only for medications that have `refill_threshold` set
  (consistent with `refill_count`/`refill_threshold` being optional in the form).
- Q: Where do reminders run, given the deployment? → A: **In-process APScheduler**
  (`AsyncIOScheduler`), single instance, per ADR-0002 (promoted Proposed → Accepted this
  phase). **Durable reminder state is the Alembic-managed `reminders` table**, scanned by a
  single recurring dispatch tick using the **default in-memory job store** — *not* a
  `SQLAlchemyJobStore` (the DML-only runtime role can't run its `CREATE TABLE` and it would
  fight `alembic check`). Refined in plan research **D1**.
- Q: What happens to a pending dose reminder when the dose is taken, and is there a manual
  dismiss? → A: **Auto-resolve + manual dismiss.** Recording a dose marks today's
  pending/snoozed reminder for that schedule slot as `dismissed` (resolved), and the user
  can also manually dismiss any reminder from the in-app list. This exercises the existing
  `dismissed` status and keeps the in-app list from accumulating stale rows.
- Q: What happens to a reminder whose fire time passed while the app was down (misfire)? →
  A: **Bounded grace + coalesce.** A missed reminder is delivered (pushed) once only if
  recovery is within a short grace window; coalescing ensures a slot never double-pushes;
  misses older than the grace window do NOT push but remain visible/overdue in the in-app
  pending list until taken or dismissed. (The exact grace duration is a `/speckit-plan`
  detail; ADR-0002's non-sleeping instance keeps misfires rare and short.)
- Q: Can a user snooze/dismiss from the push notification, or only in-app? → A: **In-app
  only** for Phase 7. Tapping the notification opens the app, where snooze/dismiss live.
  Notification-action buttons (acting while the app is closed) are deferred to Phase 8's
  polished push UX — consistent with the minimal-service-worker scope. This narrows
  UC-5.2's "on the notification or in the app" to in-app for this phase.
- Q: How are repeat refill warnings deduplicated and re-armed? → A: **One open warning per
  medication.** Do not create another refill warning while an unresolved one exists for the
  med; it re-arms (a future threshold crossing can warn again) only after `refill_count` is
  raised back above `refill_threshold` via a medication edit — at which point any open
  refill warning is resolved. No new column is needed (an unresolved refill reminder for the
  med is the "already warned" signal).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Get a push reminder when a scheduled dose is due (Priority: P1)

A signed-in user who has enabled notifications on a device receives a Web Push
notification at each scheduled dose time, naming the medication(s) due for that schedule
slot. This is the smallest end-to-end slice of the phase: a scheduling engine, a
registered push subscription, and delivery.

**Why this priority**: Scheduled reminders are the entire reason for the phase and the
core need of every persona (Granny, Diabetic Dan, Harry). Nothing else (snooze, quiet
hours, refill) has meaning without a reminder firing first. It is independently shippable
and demonstrable.

**Independent Test**: Enable notifications on a device (register a subscription), have a
schedule whose time is "now", advance to that time → a push notification is delivered to
the device naming the due medication(s), and the reminder is recorded as sent.

**Acceptance Scenarios**:

1. **Given** a user with an enabled push subscription and a medication attached to a
   schedule slot, **When** the slot's time arrives, **Then** a push notification is
   delivered to the subscribed device(s) identifying the schedule and its medication(s),
   and the corresponding reminder is marked sent.
2. **Given** a user with no push subscription, **When** a slot's time arrives, **Then** no
   delivery is attempted and the system does not error.
3. **Given** two users each with their own schedules and subscriptions, **When** reminders
   fire, **Then** each user receives only their own reminders (no cross-user delivery).
4. **Given** the app process restarts, **When** it comes back up, **Then** pending
   reminders are not lost and still fire at their scheduled times.

---

### User Story 2 — Snooze a reminder for an hour (Priority: P2)

A user who receives a reminder but cannot take the dose right now snoozes it; it
re-fires one hour later.

**Why this priority**: Directly serves Harry (PRN mid-task) and Diabetic Dan. Builds on
US1 delivery; valuable but not the MVP.

**Independent Test**: Trigger a reminder, snooze it → the original reminder shows as
snoozed, and a new reminder fires ~one hour later.

**Acceptance Scenarios**:

1. **Given** a delivered/visible reminder, **When** the user snoozes it, **Then** the
   original reminder is marked snoozed and a new reminder is scheduled for one hour later.
2. **Given** a snoozed reminder, **When** the one-hour mark arrives, **Then** the new
   reminder fires (delivered like any dose reminder).
3. **Given** a snoozed reminder that fires again, **When** the user snoozes again, **Then**
   it is re-snoozed for another hour (no hard cap in v1).
4. **Given** a reminder, **When** a user attempts to snooze a reminder that is not theirs,
   **Then** the action is rejected and nothing changes.

---

### User Story 3 — Respect quiet hours (Priority: P2)

Reminders that would fire inside the user's configured quiet-hours window are deferred to
the end of that window instead of interrupting the user.

**Why this priority**: A quality-of-life guard that prevents night-time interruptions;
depends on US1 delivery.

**Independent Test**: Set quiet hours that contain a slot time, advance to the slot time →
no notification fires during quiet hours; one fires at the window's end.

**Acceptance Scenarios**:

1. **Given** a user with quiet hours set and a reminder due inside that window, **When**
   the due time arrives, **Then** the reminder is deferred and delivered at the end of the
   quiet-hours window.
2. **Given** quiet hours that wrap midnight (e.g., 22:00 → 07:00), **When** a reminder is
   due at 02:00, **Then** it is deferred to 07:00 (correct wrap handling).
3. **Given** a user with no quiet hours set, **When** a reminder is due, **Then** it is
   delivered immediately with no deferral.

---

### User Story 4 — Reminders follow schedule edits (Priority: P2)

When a shared schedule is created, edited (time/label/days), or deleted, the reminders for
every medication attached to it are regenerated or cancelled to match — making good on the
"your reminders will shift" promise the schedule confirm modals (ADR-0009) already show.

**Why this priority**: Without this, edited/deleted schedules leave stale or missing
reminders, breaking trust in the feature. Tightly coupled to US1.

**Independent Test**: Attach a med to a schedule (reminders exist), change the schedule's
time → old reminders for that slot are cancelled and new ones generated at the new time;
delete the schedule → its reminders are cancelled.

**Acceptance Scenarios**:

1. **Given** a schedule with attached medications, **When** its time or days are changed,
   **Then** the affected dose reminders are regenerated to the new time/days and the stale
   ones are cancelled.
2. **Given** a schedule with attached medications, **When** the schedule is deleted, **Then**
   its dose reminders are cancelled.
3. **Given** a medication newly attached to a schedule, **When** the attachment is saved,
   **Then** dose reminders for that slot begin to be generated.
4. **Given** any schedule mutation, **When** it completes, **Then** no reminders remain for
   slots that no longer exist and none are missing for slots that do.

---

### User Story 5 — Refill warning on live supply (Priority: P2)

Taking a dose decrements the medication's on-hand count and voiding a dose restores it;
when the count reaches the medication's refill threshold, the user gets a refill warning
naming the medication and the number remaining.

**Why this priority**: Serves the "running low" need and is the headline supply feature of
the phase. It is independent of dose-time reminders (different reminder type) but reuses the
same delivery path.

**Independent Test**: Set a med's on-hand count just above its threshold, take doses until
it reaches the threshold → a refill reminder is generated naming the med and remaining
count; void a dose → the on-hand count goes back up.

**Acceptance Scenarios**:

1. **Given** a medication with an on-hand count, **When** a dose is recorded, **Then** the
   on-hand count decreases by one (never below zero).
2. **Given** a dose that decremented the count, **When** that dose is voided, **Then** the
   on-hand count is restored by one.
3. **Given** a medication with a refill threshold set, **When** taking a dose brings the
   on-hand count to or below the threshold, **Then** a refill warning is generated that
   identifies the medication and the number remaining.
4. **Given** a medication with no refill threshold set, **When** doses are taken, **Then**
   no refill warning is generated (warnings are opt-in).
5. **Given** the on-hand count is already at zero, **When** a dose is recorded, **Then** the
   dose still succeeds and the count stays at zero (supply tracking never blocks a take).
6. **Given** a medication that already has an open refill warning, **When** another dose is
   taken while still at/below threshold, **Then** no duplicate refill warning is created.
7. **Given** a medication with an open refill warning, **When** the user raises `refill_count`
   back above `refill_threshold` (records a refill via a med edit), **Then** the open refill
   warning is resolved and a future threshold crossing can warn again.

---

### User Story 6 — Resilient delivery (Priority: P3)

Push delivery failures and denied browser permission are handled gracefully: a failed send
is recorded and retried within bounded attempts, an expired/invalid subscription is cleaned
up, and a user who denies permission still sees reminders in the app.

**Why this priority**: Hardens the feature against real-world push flakiness. Important but
the loop works without it; sequenced last.

**Independent Test**: Simulate a push send failure for an invalid subscription → the
subscription is marked/removed and the reminder is not stuck; deny permission in the browser
→ the in-app reminder list still shows due reminders.

**Acceptance Scenarios**:

1. **Given** a push send fails transiently, **When** delivery is attempted, **Then** it is
   retried up to the configurable maximum (`reminder_send_max_attempts`, default 3) before giving up.
2. **Given** a subscription endpoint is permanently invalid/expired, **When** a send to it
   fails as gone, **Then** that subscription is removed and not retried.
3. **Given** a user has denied browser push permission, **When** reminders are due, **Then**
   they still appear in an in-app reminders view (push is best-effort, not the only channel).

### Edge Cases

- **No subscription / permission denied** → reminders are still generated and visible
  in-app; push delivery is skipped without error.
- **Quiet hours wrapping midnight** → correct deferral to the window end (22:00→07:00).
- **Reminder due exactly at the quiet-hours boundary** → fires (boundary is not "inside").
- **Schedule deleted while a reminder is pending** → the pending reminder is cancelled.
- **Med detached from a schedule** → dose reminders for that (schedule, med) stop.
- **Soft-deleted medication or schedule** → no new reminders generated for it.
- **On-hand count at zero** → taking still succeeds; count floors at zero; no negative.
- **Voiding a dose that did not decrement** (e.g., med had no count) → no negative/over-restore.
- **Process restart** → persisted reminder rows survive (no lost or duplicated reminders); the scheduler re-registers its single tick on startup.
- **Re-snooze** → allowed repeatedly; each snooze re-arms one hour out.
- **Dose taken for a slot with a pending/snoozed reminder** → that reminder is auto-resolved
  (`dismissed`) and leaves the in-app pending list; manual dismiss does the same on demand.
- **Manually dismissing an already-resolved/sent reminder** → idempotent; no error, no
  duplicate state change.
- **Cross-user** → no reminder, snooze, or subscription action can touch another user's data.
- **Raw push keys / VAPID private key** MUST never be logged or returned in any response.

## Requirements *(mandatory)*

### Functional Requirements

#### Push subscription & enablement (US1, minimal per clarification)

- **FR-001**: An authenticated user MUST be able to register a device's push subscription
  (endpoint + keys) and to remove it; registration MUST be idempotent per (user, endpoint)
  and scoped to the logged-in user.
- **FR-002**: The app MUST expose the server's public VAPID key to the client so the browser
  can create a subscription; the VAPID private key MUST be configuration/secret only and
  MUST NEVER be sent to the client, logged, or returned in any response.
- **FR-003**: The frontend MUST provide a minimal "Enable notifications" control that requests
  browser permission and registers the resulting subscription, plus a minimal service worker
  that displays delivered notifications. Polished permission/onboarding UX is explicitly out
  of scope (Phase 8).

#### Reminder scheduling engine (US1)

- **FR-004**: The system MUST schedule and fire reminders in-process using APScheduler
  (`AsyncIOScheduler`) started/stopped with the app lifecycle. **Durable reminder state MUST
  live in the Alembic-managed `reminders` table** (so a restart does not lose pending
  reminders); a single recurring dispatch tick scans that table using the default in-memory
  job store — **not** a `SQLAlchemyJobStore` (ADR-0002 / plan research D1; the DML-only
  runtime role cannot run the jobstore's DDL). The dispatch function MUST be
  transport-agnostic (callable independent of how it was triggered).
- **FR-005**: Dose reminders MUST be generated per schedule slot for every non-deleted
  medication attached to a non-deleted schedule, at the schedule's time on its active days,
  in the owning user's timezone. A dose reminder references the **schedule** (not an
  individual medication) per the data model; its notification MUST name the medication(s)
  attached to that slot.
- **FR-006**: Each reminder MUST carry a status lifecycle of `pending` → `sent`, with
  `snoozed` (the original of a snooze) and `dismissed` (resolved) as terminal states. A
  fired reminder MUST be recorded as `sent`; a resolved reminder MUST be recorded as
  `dismissed` (see FR-021/FR-022).
- **FR-006a**: A reminder whose fire time passed while the scheduler was unavailable
  (misfire) MUST be delivered at most once and only within a bounded grace window;
  misfires MUST be coalesced so a single slot never pushes more than once; misses older
  than the grace window MUST NOT push but MUST remain visible as overdue in the in-app
  pending list until taken or dismissed.

#### Delivery (US1, US6)

- **FR-007**: When a reminder fires, the system MUST deliver a Web Push notification to each
  of the user's registered subscriptions, identifying the medication(s)/reason; delivery
  MUST be best-effort and non-blocking to the scheduler.
- **FR-008**: Reminders MUST also be readable in-app (a list of the user's pending/snoozed
  reminders), so a user without push still sees what is due.

#### Reminder resolution (US1)

- **FR-021**: Recording a dose MUST resolve (mark `dismissed`) today's pending/snoozed dose
  reminder(s) for the schedule slot the dose was taken against, so a taken medication stops
  nagging and drops out of the in-app pending list.
- **FR-022**: A user MUST be able to manually dismiss one of their own reminders from the
  in-app list (marking it `dismissed`); the action MUST be scoped to the logged-in user and
  MUST NOT affect another user's reminders.

#### Snooze (US2)

- **FR-009**: A user MUST be able to snooze one of their own reminders from the in-app
  reminder UI; snoozing MUST mark the original reminder `snoozed` and schedule a new
  reminder exactly one hour later. In Phase 7 the snooze/dismiss controls are **in-app
  only**; the notification simply opens the app. Notification-action buttons (acting while
  the app is closed) are out of scope for this phase (Phase 8).
- **FR-010**: Re-snoozing a fired snoozed reminder MUST be allowed (no hard cap in v1); the
  snooze action MUST be scoped to the logged-in user.

#### Quiet hours (US3)

- **FR-011**: A reminder whose fire time falls inside the user's quiet-hours window MUST be
  deferred to the end of that window rather than delivered during it; the computation MUST
  handle windows that wrap midnight; users with no quiet hours set MUST be unaffected.

#### Schedule-mutation rescheduling (US4)

- **FR-012**: Creating, editing (time/label/days), or deleting a shared schedule, and
  attaching/detaching a medication to/from a schedule, MUST (re)generate or cancel the
  affected dose reminders so that reminders always match the current schedule state. This
  realizes the "your reminders will shift" promise the schedule confirm modals already make.

#### Live supply & refill warnings (US5)

- **FR-013**: Recording a dose MUST decrement the medication's `refill_count` by one when it
  is set, never below zero; voiding a dose MUST restore `refill_count` by one **only when
  `refill_count` is set** — a void never restores into an untracked/NULL med, so "voiding a
  dose that did not decrement (med had no count)" cannot over-restore. Supply tracking MUST
  NEVER block a take or void (it is a counter, not a guard). *Known limitation*: because
  individual doses do not record whether they decremented supply, voiding a dose that was
  taken while the med was untracked and only later given a count may over-count by one —
  accepted and user-correctable via a med edit; not a guard failure.
- **FR-014**: When recording a dose brings a medication's `refill_count` to or below its
  `refill_threshold` (only when a threshold is set), the system MUST generate a refill
  reminder that identifies the medication and the number remaining — **unless an
  unresolved refill reminder already exists for that medication**, in which case no new one
  is created (at most one open refill warning per medication).
- **FR-014a**: A refill warning MUST re-arm only when `refill_count` is raised back above
  `refill_threshold` (e.g., the user records a refill by editing the medication); on that
  transition any open refill reminder for the medication MUST be resolved (`dismissed`), so
  a subsequent threshold crossing can warn again. No "already warned" column is added — an
  unresolved refill reminder is the dedup signal.
- **FR-015**: `refill_count` is the authoritative on-hand count and `refill_threshold` the
  warn-at level; the legacy `doses_remaining`/`total_doses_filled` columns are not used by
  this feature.

#### Delivery resilience (US6)

- **FR-016**: A failed push send MUST be retried within a bounded number of attempts — a
  configurable maximum (`reminder_send_max_attempts`, **default 3**) — before giving up; a
  permanently-invalid/expired subscription (server reports it gone, HTTP 404/410) MUST be
  removed and not retried; failures MUST NOT crash the scheduler or the app.

#### Cross-cutting (security, typing, coverage, docs)

- **FR-017** (security): Every reminder, snooze, and subscription operation MUST be scoped
  to the logged-in user with no parameter/path that can affect another user; inputs MUST be
  validated at the boundary; the VAPID private key and raw subscription secrets MUST never be
  logged or returned.
- **FR-018** (typing): New backend code MUST satisfy `mypy --strict`; new frontend code MUST
  satisfy `tsc --noEmit` strict.
- **FR-019** (coverage): Project coverage MUST stay ≥85% with no module below the 70% floor.
- **FR-020** (docs): ADR-0002 MUST move from Proposed to **Accepted** documenting the chosen
  in-process APScheduler approach. A documentation sweep MUST update all affected docs — at
  minimum `docs/glossary.md` and `docs/user_stories.md` UC-5.4 to say the refill warning
  fires on **`refill_count` ≤ `refill_threshold`** (correcting the current `doses_remaining`
  wording), the OpenAPI contracts / generated client for new endpoints, the ER/relevant
  diagrams if reminder lifecycle is depicted, and `CLAUDE.md`'s behavior notes. A new
  sequence diagram for the reminder fire/deliver/snooze flow SHOULD be added under
  `docs/diagrams/`.

### Key Entities

- **Reminder** *(existing table)*: `type` (dose|refill), `status`
  (pending|sent|snoozed|dismissed), `scheduled_for`; a dose reminder references a
  **schedule**, a refill reminder references a **medication** (enforced by existing CHECK).
  This feature gives the table its behavior; no new columns anticipated.
- **PushSubscription** *(existing table)*: a device endpoint + keys, unique per
  (user, endpoint); created on enable, removed on disable or when reported gone.
- **User** *(existing)*: `quiet_hours_start`/`_end` drive deferral; `timezone` drives
  local scheduling.
- **Medication** *(existing)*: `refill_count` (live on-hand, mutated by take/void) and
  `refill_threshold` (warn-at). No new columns.
- **No new persistence**: there is no APScheduler job-store table. The scheduler keeps only a
  single recurring tick in the default in-memory store; the `reminders` table is the durable
  source of truth that survives restart (plan research D1).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with an enabled subscription receives a push notification for a due
  scheduled dose, naming the correct medication(s), 100% of the time the device is reachable.
- **SC-002**: Pending reminders survive an app restart — none are lost and none fire twice.
  A reminder missed during downtime pushes at most once (only within the grace window) and
  otherwise remains visible as overdue in-app.
- **SC-003**: A snoozed reminder re-fires one hour (±1 minute) after the snooze action.
- **SC-004**: Reminders due inside a user's quiet hours are delivered at the window's end,
  not during it, including windows that wrap midnight.
- **SC-005**: After any schedule create/edit/delete or med attach/detach, the set of pending
  dose reminders matches the current schedule state with zero stale or missing reminders.
- **SC-006**: Taking a dose decreases on-hand count by exactly one (floored at zero) and
  voiding restores exactly one, verified across take/void cycles.
- **SC-007**: A refill warning is generated the first time on-hand count reaches/passes the
  threshold for meds that have a threshold set, and never for meds without one. While the
  count stays at/below threshold no duplicate warning is created; the warning re-arms only
  after the count is raised back above the threshold.
- **SC-008**: A user receives only their own reminders; no cross-user delivery or mutation is
  possible (verified by test).
- **SC-009**: The VAPID private key and raw subscription secrets never appear in any log line
  or API response (verified by review/test).

## Assumptions

- The existing `reminders`, `push_subscriptions`, and `users.quiet_hours_*` schema from
  Phase 1 is reused as-is; the only schema change is **indexes** on `reminders` (migration
  `0006`). There is **no APScheduler job-store table** — durable reminder state is the
  `reminders` table itself (plan research D1).
- **Quiet hours are admin-managed** (like `timezone`): set via the admin CLI
  (`medminder-admin user update --quiet-hours-start/--quiet-hours-end`), which this phase
  extends. There is **no in-app quiet-hours editor** in Phase 7; tests may also set the
  columns directly via a fixture. *(Superseded on this branch: a self-service editor —
  `PUT /me/quiet-hours`, surfaced on `/reminders` — was added as a follow-on; see
  ADR-0012.)*
- Dose reminders are per-schedule (the data model enforces it); a single notification per
  slot names all medications attached to that schedule.
- Snooze is a fixed one hour and may be repeated; there is no maximum-snooze cap in v1.
- Refill warnings are opt-in: only medications with `refill_threshold` set produce them.
  `refill_count` is the live count; `doses_remaining`/`total_doses_filled` stay unused.
- Quiet-hours deferral pushes a reminder to the end of the window; boundary times are not
  "inside" the window. Deferral applies to all push deliveries, including refill warnings
  generated during quiet hours (the warning is still recorded immediately and visible
  in-app; only its push is deferred).
- v1 runs a single app instance (ADR-0002); horizontal scaling is explicitly out of scope and
  would require revisiting the ADR.
- Web Push uses VAPID; keys are environment/secret only. The polished permission/onboarding
  UX and full PWA/service-worker offline shell are Phase 8; Phase 7 ships only the minimal
  enable-and-register flow needed to test delivery.
- The exact transport library (web-push sender), the reminder-generation strategy (e.g.,
  rolling daily generation vs. per-slot cron jobs), retry/backoff specifics, and the precise
  endpoint/job shapes are `/speckit-plan` decisions, not fixed here.
- No new audit/event table for reminder actions in v1.

## Dependencies

- Phase 1 — data model: `reminders`, `push_subscriptions`, `users.quiet_hours_*`,
  medication supply columns.
- Phase 2 — auth: `get_current_user`, session cookies, `/me` (subscription + reminder
  endpoints are user-scoped).
- Phase 3/UX-enhancements — shared schedules CRUD (`api/schedules_crud.py`) where reminder
  (re)generation hooks in; ADR-0009 confirm modals that promise reminders shift.
- Phase 4/5 — the dose write paths `domain/doses.py` `create_dose`/`void_dose` where
  `refill_count` decrement/restore lands.
- ADR-0002 — in-process APScheduler; promoted to Accepted by this phase.
- New runtime dependencies (pinned, reviewed per constitution): an APScheduler package and a
  Web Push sender library; new VAPID settings in `settings.py`.
