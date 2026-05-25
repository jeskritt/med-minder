# MedMinder — User Stories & Use Cases

This document defines **what** the app must do for its users. Design
exploration ("how should the timer feel?", "what does adherence
visualization look like?") lives in `docs/design/`. Architectural
decisions live in `docs/adr/`.

---

## Personas

The personas below define the v1 product surface. Each persona has a
**primary flow** that must work end-to-end against a deployed build
(per `specs/mission.md` success criteria) and a set of acceptance
criteria captured in the use cases below.

### Granny Smith — fixed-schedule daily medications
Older user taking medication 3 times a day (morning / afternoon /
evening). Wants an unmistakable "taken / not taken" indicator with a
timestamp, scheduled reminders, and a printable medication list for
medical paperwork.

**Primary flow:** log in → see today's three doses → mark each as
taken → confirm timestamp is visible.

### Billy Bat — short-term acute pain meds with sub-doses
Recovering from ACL surgery, prescribed T3. May have at most 3 doses
active at a time, each "lasting" 6 hours (no more than 3 in any rolling
6-hour span), but wants a steady level — takes 1 every 2 hours. Needs
reminders that can be snoozed mid-task.

**Primary flow:** receive reminder → snooze for an hour → mark next
sub-dose taken → see how many doses are still active and, when at the
max-at-a-time cap, when the next dose is allowed. (Rolling per-dose
windows — see ADR-0010.)

### Migraine Molly — drug-interaction-aware scheduling
Gets migraines and takes a migraine medication that conflicts with
ibuprofen and requires a 2-hour cooldown before Tylenol.

**Primary flow:** mark migraine medication as taken → attempt to mark
ibuprofen → see a clear warning blocking the action → see a
count-up timer until the interaction window closes.

### Headache Harry — PRN with min-interval
Takes regular advil as needed. Forgetful; needs to look at the app
and instantly know whether he's already dosed and when. Has a
minimum interval before the next dose is permitted.

**Primary flow:** open app → see "last taken N minutes ago" and a
countdown to the next allowed dose → mark a new dose only after the
countdown reaches zero.

### Diabetic Dan — recurring meds at flexible times, snoozeable
Takes diabetes medication at specific times of day, but the times
flex. Wants reminders he can snooze for an hour.

**Primary flow:** receive reminder → snooze → take dose later → see
the dose recorded against the right scheduled slot.

---

## Use cases

Each use case is a checklist of behavior the app must support. Use
cases group naturally into sections: account management, data CRUD,
the daily-use loop, reminders, and reporting.

### UC-1 — Account management (no self-service)

There is no user-facing registration. All account management happens
through the admin CLI (`medminder-admin`).

#### UC-1.1 Admin adds a user
- [ ] CLI accepts email, name, role (`admin` | `user`), and password
      (read from stdin).
- [ ] Password shorter than 12 characters is rejected.
- [ ] Duplicate email (case-insensitive) is rejected.
- [ ] Successful add prints the new user's ID.

#### UC-1.2 Admin updates a user
- [ ] CLI can change any of: password, email, name, role.
- [ ] At least one mutating flag is required.
- [ ] Email change collisions are rejected (case-insensitive).

#### UC-1.3 Admin deletes a user
- [ ] CLI sets `deleted_at` (soft delete); does not hard-delete.
- [ ] Subsequent login attempts for that email fail.
- [ ] The user's historical doses remain queryable for adherence.

#### UC-1.4 Admin lists users
- [ ] CLI prints a table: id, email, name, role, created_at, deleted_at.
- [ ] `--role` filters by role.
- [ ] `--include-deleted` shows soft-deleted rows.

### UC-2 — Login / logout

#### UC-2.1 Successful login
- [ ] User enters email and password on the login page.
- [ ] On success, server creates a session row and sets a signed
      HTTP-only cookie.
- [ ] User is redirected to the medication list page.

#### UC-2.2 Failed login
- [ ] Wrong password and unknown email both produce the *same*
      generic error message and the same response time (no user
      enumeration via timing).
- [ ] No session cookie is set.

#### UC-2.3 Locked / soft-deleted account
- [ ] A login attempt against a soft-deleted user produces the same
      generic error as UC-2.2.

#### UC-2.4 Logout
- [ ] User clicks logout.
- [ ] Server deletes the session row; cookie is cleared.
- [ ] User is redirected to the login page.

#### UC-2.5 Forced logout
- [ ] When the admin updates a user's password or soft-deletes them,
      all of that user's session rows are deleted server-side.
- [ ] Existing browser tabs receive a 401 on their next request and
      redirect to login.

### UC-3 — Medication CRUD

#### UC-3.1 Add medication
- [ ] User enters: name, quantity per dose, unit, times per day,
      timer mode (`none | count_up | count_down | multi_sub_dose`),
      and any timer-mode-specific fields:
      - `count_down`: minimum interval (minutes).
      - `multi_sub_dose`: window duration (minutes).
- [ ] Optional: start date, end date, total doses (course size),
      total doses filled, doses remaining.
- [ ] User attaches the medication to zero or more schedules.
- [ ] If schedule count ≠ `times_per_day`, the form shows a warning
      but does not block save.
- [ ] On save, user is redirected to the medication list.

#### UC-3.2 Edit medication
- [ ] All fields from UC-3.1 are editable.
- [ ] Editing does not retroactively rewrite historical doses.

#### UC-3.3 Delete medication
- [ ] Soft delete (sets `deleted_at`).
- [ ] Medication disappears from the list view but historical doses
      remain queryable for adherence reporting.
- [ ] Confirmation modal explains "this hides the medication; your
      history is preserved."

#### UC-3.4 List medications
- [ ] List shows all non-deleted medications for the logged-in user.
- [ ] Each row shows current timer state where applicable (e.g.,
      "next dose in 1h 12m").

#### UC-3.5 Print medication summary
- [ ] A "Print" action produces a clean printable view: name,
      dosage, unit, schedule labels, start/end dates.
- [ ] No app chrome (nav, buttons) prints.
- [ ] CSS print stylesheet is in place; verified in Chrome and
      Firefox print previews.

### UC-4 — Mark a dose as taken

#### UC-4.1 Mark taken
- [ ] User taps "taken" on a medication.
- [ ] Server records a `doses` row with the current timestamp and
      the medication's configured quantity.
- [ ] If the medication is associated with a current scheduled slot
      (within a tolerance window), the dose is linked to that slot.
- [ ] UI updates immediately to show the taken state and timestamp.

#### UC-4.2 Un-take a dose (correct a mistake)
- [ ] Tapping a medication that's already shown as taken opens a
      confirmation modal: "This med has already been taken. Remove
      the 'taken' status?"
- [ ] On confirm, the most recent `doses` row for that medication
      (within the current scheduled slot or PRN window) is voided
      via a compensating row, never deleted.
- [ ] UI returns to the not-taken state.

#### UC-4.3 Mark taken when an interaction cooldown is active
> **Reconciled with ADR-0008 (Phase 6).** A drug-interaction cooldown
> is **warn + explicit confirm**, *not* a hard block — it is advisory
> and always overridable (unlike the non-overridable Phase 5
> `count_down` / `multi_sub_dose` overdose guards). The server never
> refuses a dose the user has explicitly confirmed; it records the
> override attributably for audit.
- [ ] If a drug-interaction rule says the conflicting medication was
      taken too recently, an unacknowledged taken action is **refused
      server-side** with a structured, **always-overridable** 409
      (`interaction_cooldown_active`) naming the conflicting
      medication(s) and the remaining cooldown — surfaced as a "take
      anyway" confirm, never a dead-end.
- [ ] Detection is server-authoritative and holds against a direct API
      call that bypasses the UI: without acknowledgment the conflict
      response is returned and no dose row is written; with explicit
      acknowledgment the dose is recorded **and** the override is
      durably, attributably persisted (re-tested with a direct API
      call in the integration suite).

#### UC-4.4 Mark taken when blocked by min-interval (PRN)
- [ ] For `count_down` medications, taken is blocked until the
      configured minimum interval has elapsed since the last dose.
- [ ] The UI shows the remaining cooldown.

### UC-5 — Reminders

#### UC-5.1 Receive a scheduled reminder
- [ ] User has granted push permission and registered a push
      subscription.
- [ ] At the scheduled time, the server sends a Web Push message.
- [ ] Tapping the notification opens the medication's "today" view.

#### UC-5.2 Snooze a reminder
- [ ] User taps "snooze" in the app's reminders list (Phase 7). Snooze
      from the notification itself, while the app is closed, is Phase 8.
- [ ] The reminder is rescheduled for one hour later.
- [ ] Snoozed reminders appear in the UI as "snoozed".

#### UC-5.3 Quiet hours
- [ ] Reminders that fall inside the user's `quiet_hours_start` /
      `quiet_hours_end` are deferred to the end of the quiet
      window.
- [ ] Quiet hours wrap around midnight correctly (e.g., 22:00 → 07:00).

#### UC-5.4 Refill warning
- [ ] When taking a dose brings the live on-hand count `refill_count`
      down to/below the medication's `refill_threshold` (opt-in — set
      per medication), a `refill` reminder is created.
- [ ] At most one open refill warning per medication; it re-arms once
      `refill_count` is raised back above the threshold (a refill recorded
      via the medication editor).
- [ ] The refill reminder text identifies the medication and the
      number remaining.

#### UC-5.5 Push delivery failure
- [ ] If a push send fails (subscription invalid, network error),
      the reminder row is marked appropriately and retried within
      a bounded number of attempts.
- [ ] Permanently invalid subscriptions are removed from
      `push_subscriptions`.

#### UC-5.6 Push permission denied
- [ ] When the browser denies push permission, the app falls back to
      in-app banners on next visit (no broken UI, no infinite spinner).

### UC-6 — Adherence reporting

#### UC-6.1 Calendar view
- [ ] User selects a medication.
- [ ] A calendar grid shows each day color-coded:
      taken / partial / missed / scheduled-future.
- [ ] User can navigate by month.

#### UC-6.2 Stacked-bar view
- [ ] Per-medication adherence over a configurable window
      (week / month) shown as stacked bars.

#### UC-6.3 CSV export
- [ ] User exports their dose history as CSV (one row per dose:
      medication, taken_at, quantity, schedule_label).
- [ ] Soft-deleted medications still appear (suffixed "(removed)")
      so historical exports remain coherent.

### UC-7 — PWA / offline behavior

#### UC-7.1 Install
- [ ] Verified installable on iOS Safari and Android Chrome.
- [ ] App icon and theme color match the manifest.

#### UC-7.2 Offline app shell
- [ ] Opening the app with no network shows the shell (nav,
      placeholder list) with a clear "offline" indicator.
- [ ] Mark-as-taken while offline queues the action and syncs on
      reconnect.

---

## See also

- `docs/design/timer-modes.md` — design exploration for the four
  timer modes (which arose from "Thoughts on Timers" in earlier
  drafts of this document).
- `docs/design/adherence-tracking.md` — design exploration for the
  long-term adherence views.
- `docs/glossary.md` — definitions for PRN, snooze, interaction
  window, etc.
- `docs/adr/` — architectural decisions (sessions vs JWTs, in-process
  scheduler, etc.).

