# ADR-0012: Self-service quiet hours

## Status

Accepted

## Context

Phase 7 (Reminders + Snooze, ADR-0002) made quiet hours — the per-user window during
which due reminders are deferred to the window end instead of being pushed — but left
them **admin-CLI-only** (`medminder-admin user update --quiet-hours-start/--quiet-hours-end`).
Phase 7's spec recorded this explicitly ("no in-app quiet-hours editor in Phase 7").

For a single-tenant medication PWA whose whole purpose is reminders, the person receiving
the reminders should decide when to be left alone without involving an admin. This ADR
records the follow-on decision to expose quiet hours as a self-service control. The data
model (`users.quiet_hours_start` / `_end`, nullable `time`), the deferral logic
(`domain.reminders.defer_for_quiet_hours`, which only acts when **both** bounds are set),
and the shared `domain.users.update_user` helper already exist and are unchanged.

## Decision

1. **Editor placement: a "Quiet hours" section on the `/reminders` page**, beside the
   existing `EnableNotifications` control — not in the profile modal (ADR-0011). Quiet
   hours are a notification-delivery preference, so they live with the other
   notification-behavior controls, where a user goes to manage when they get notified.

2. **A dedicated endpoint `PUT /me/quiet-hours`** on the existing `me` router, rather than
   extending `PATCH /me`. `PATCH /me` requires `name`; a quiet-hours-only save should not
   have to send a name, and keeping the two concerns separate avoids coupling the editor
   to the profile form. Body `QuietHoursUpdate {start, end}` (`extra="forbid"`):
   - both `HH:MM` → set the window (Pydantic coerces the strings to `time`);
   - both `null` → clear it (quiet hours off).
   Returns the updated `Me` so the client refreshes its `["me"]` cache.

3. **Both-or-neither, and reject equal bounds.** Deferral only applies when both columns
   are set, and a zero-length `[start, start)` window would never fire, so a one-sided
   window or `start == end` is **422** (caught by a model validator). The client form
   blocks both cases too; the 422 is a backstop.

4. **`GET /me` now also exposes `timezone` (read-only) + `quiet_hours_start/end`.** The UI
   pre-fills from these and labels the inputs with the timezone so the user understands the
   hours are local. `timezone` stays **non-editable** in-app (admin/CLI-managed, as before);
   exposing it read-only does not change that.

5. **The admin CLI path stays.** `user update --quiet-hours-start/--quiet-hours-end` remains
   the admin override and the recovery path; both routes write the same two columns via
   `update_user`. No schema change — `alembic check` stays clean.

## Consequences

### Positive

- Users own their quiet hours without an admin round-trip.
- Reuses `update_user(..., new_quiet_hours_start/_end, clear_quiet_hours)` and the existing
  deferral logic — no new domain code, no migration.
- The dedicated endpoint keeps `PATCH /me` (name) and quiet hours independently saveable and
  works regardless of where the editor is surfaced.

### Negative

- A second write path to the same columns (CLI + API). They share one domain helper, so the
  invariants (both-or-neither) are enforced in one place, but the both-or-neither/equal
  validation now lives in two surfaces (the API model and the CLI), each mapping to its own
  error style (422 vs. CLI abort).

### Neutral

- `timezone` is now visible on `GET /me`; it remains read-only in-app. A future feature could
  add self-service timezone editing (out of scope here).
- Supersedes the "no in-app editor" stance from ADR-0002 / the Phase 7 spec; that text now
  carries a pointer to this ADR.
