# ADR-0013: Self-service timezone

## Status

Accepted

## Context

A user's `users.timezone` (an IANA zone such as `America/Edmonton`) drives quiet-hours
deferral, "today" bounds, daily-cap windows, and reminder generation. Until now it could
only be set by the admin CLI at **user creation** (`user add --timezone`, default `UTC`) —
there was no `update --timezone` and no in-app editor, so a user in the wrong zone got
reminders at the wrong local times with no way to fix it themselves. ADR-0012 (self-service
quiet hours) exposed `timezone` read-only on `GET /me` and named self-service editing as the
explicit follow-up; this ADR is that follow-up.

Constraints from the user:
- Edit it from the **profile editor** (`ProfileDialog`).
- A **searchable** control — typing `Edmo` should surface `America/Edmonton`.
- It must be **impossible to store an invalid value**.

The validation primitive already existed: `domain/timezone.py` resolves a name via
`zoneinfo.ZoneInfo`, raising `InvalidTimezoneError` for unknown zones (used by the Today view).

## Decision

1. **Dedicated endpoint `PUT /me/timezone`** `{timezone}` → `200 Me`, on the existing `me`
   router — mirroring `PUT /me/quiet-hours` (ADR-0012) rather than overloading `PATCH /me`'s
   `name`. The body model validates the zone via a new public
   `domain.timezone.normalize_timezone(name)` (wraps the same `ZoneInfo` check); an unknown
   or malformed name is **422**. The handler calls the shared `update_user(...,
   new_timezone=...)`. `timezone` stays CLI-settable as well (admin override / recovery).

2. **Validate at the API boundary, store in the domain.** `update_user` gains a
   `new_timezone` parameter that simply assigns the column (consistent with how it treats
   name/role); the zone-validity check lives in the request model so an invalid value is
   rejected before it reaches the mutator — the column can never hold a string the
   deferral / today-bounds math can't resolve.

3. **A custom, dependency-free combobox** (`TimezoneCombobox`) over
   `Intl.supportedValuesOf("timeZone")`, filtered by case-insensitive **substring**. A native
   `<datalist>` was rejected: Firefox matches options by *prefix*, so `Edmo` would not surface
   `America/Edmonton` (it starts `America/`), and a datalist input can hold free-typed invalid
   text. The custom control commits **only** a value drawn from the valid list — selecting an
   option, or blurring on an exact (case-insensitive) match; any other free text reverts to the
   last committed value — so the UI cannot submit an invalid zone. The server's `zoneinfo`
   check remains the authority (defense-in-depth).

4. **No schema change.** `users.timezone` already exists (`alembic check` stays clean). The
   new value takes effect immediately for all consumers, which read `user.timezone` fresh.

## Consequences

### Positive

- A user can correct their own timezone; reminder times, quiet-hours deferral, and the Today
  view follow without admin involvement.
- Reuses `zoneinfo` validation, `update_user`, and the `PUT /me/*` pattern — minimal new
  surface, no migration, no new frontend dependency.

### Negative

- The full IANA list (~400 zones) is materialized client-side via `Intl.supportedValuesOf`;
  the combobox caps the rendered matches (50) to stay cheap. On a runtime without
  `Intl.supportedValuesOf` the picker degrades to just the current value (it can still be
  displayed, only not searched) — acceptable for the modern-browser PWA target.

### Neutral

- Display uses the raw IANA id (searchable, unambiguous); a friendlier label with the current
  UTC offset could come later.
- The admin CLI still only exposes `--timezone` on `user add`, not `user update`; the domain
  `update_user` now supports it, so wiring an `update --timezone` flag later is trivial if
  wanted. Supersedes the "timezone read-only in-app" note in ADR-0012.
