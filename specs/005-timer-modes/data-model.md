# Phase 1 Data Model — Phase 5: Timer Modes

Phase 5 introduces **no new persistent tables and no new columns**.
The schema fields it consumes were shipped in Phase 1
(`medications.timer_preference`, `min_interval_minutes`,
`window_duration_minutes`) and Phase 4 (`doses`, `dose_voids`).

This document records:
1. Which existing columns each user story reads.
2. The new server-computed value objects (TimerState + payloads).
3. The new error type and its wire shape.
4. The window invariants for `multi_sub_dose`.

---

## Existing entities Phase 5 reads

### Entity: `Medication`

**Table**: `medications`
(`backend/src/medminder/db/models/medications.py`)

**Columns Phase 5 reads** (all already shipped):

| Column | Type | Phase 5 use |
|---|---|---|
| `id` | UUID PK | Identifies the medication. |
| `user_id` | UUID FK → users.id | Cross-user isolation guard on every endpoint that returns timer state. |
| `name` | text | Human-readable name in display strings. |
| `times_per_day` | int (`SmallInteger`) | `slots_total` for `multi_sub_dose`. |
| `timer_preference` | enum `none / count_up / count_down / multi_sub_dose` | Branch selector; `none` returns `timer_state = null`. |
| `min_interval_minutes` | int \| null | Used by `count_down` mode and the guard in `create_dose()`. CHECK constraint already enforces `> 0` when `timer_preference = 'count_down'`. |
| `window_duration_minutes` | int \| null | Used by `multi_sub_dose` mode. CHECK constraint already enforces `> 0` when `timer_preference = 'multi_sub_dose'`. |
| `deleted_at` | timestamptz \| null | Soft-deleted medications MUST NOT appear in any timer-state response. |

**Columns Phase 5 does not touch**: `quantity_per_dose`, `unit`,
`start_date`, `end_date`, `total_doses`, `total_doses_filled`,
`doses_remaining`, `refill_count`, `refill_threshold`,
`created_at`, `updated_at`.

**Migration impact**: NONE.

### Entity: `Dose`

**Table**: `doses`
(`backend/src/medminder/db/models/doses.py`)

**Columns Phase 5 reads**:

| Column | Type | Phase 5 use |
|---|---|---|
| `id` | UUID PK | Identifies a dose for voiding lookups. |
| `medication_id` | UUID FK | Joins to medication for timer-state computation. |
| `user_id` | UUID FK | Cross-user isolation. |
| `taken_at` | timestamptz | The single fact every timer mode reads — time elapsed (count_up), interval comparison (count_down), window arithmetic (multi_sub_dose). |

**Columns Phase 5 does not write**: nothing — Phase 5 only adds a
read-side derivation and a write-side guard. The write path itself
(creating a `doses` row) is unchanged from Phase 4.

**Migration impact**: NONE.

### Entity: `DoseVoid`

**Table**: `dose_voids`
(`backend/src/medminder/db/models/dose_voids.py`)

**Columns Phase 5 reads**: `dose_id` — used to filter out voided
doses from `_latest_non_voided_dose` and from the input list passed
to `compute_timer_state`. Phase 4 invariant: a dose is "voided" iff
a non-deleted `dose_voids` row references its `dose_id`.

**Migration impact**: NONE.

---

## New server-computed value objects (not persisted)

These are the in-memory shapes returned from `domain/timers.py`. They
are converted to Pydantic wire models (`TimerStateOut`) at the API
boundary.

### `TimerState`

A discriminated-union value class. The discriminator is `mode`.

| Field | Type | Notes |
|---|---|---|
| `mode` | `Literal["count_up", "count_down", "multi_sub_dose"]` | Discriminator. (Mode `none` is represented at the API boundary by `timer_state = null`; the domain function returns `None` rather than a `TimerState` for `none`.) |
| `as_of` | `datetime` (UTC) | The `now` value the state was computed at. Used by the client's `tickFrom()` helper. |
| `last_dose_at` | `datetime` \| `None` (UTC) | Most recent non-voided dose; `None` if none has ever been recorded. |
| *mode-specific payload* | (see below) | One of `CountUpPayload`, `CountDownPayload`, `MultiSubDosePayload`. |

#### `CountUpPayload`

| Field | Type | Notes |
|---|---|---|
| `elapsed_seconds` | `int \| None` | `int(now - last_dose_at)` in seconds, or `None` when no dose has been recorded. **Never capped on the wire** — see FR-003; the cap is a display concern. |

#### `CountDownPayload`

| Field | Type | Notes |
|---|---|---|
| `min_interval_seconds` | `int` | The medication's interval in seconds (constant). |
| `next_allowed_at` | `datetime` (UTC) \| `None` | `last_dose_at + min_interval_minutes` when a dose exists; `None` otherwise (immediate). |
| `remaining_seconds` | `int` | `max(0, int(next_allowed_at - now))` — clamped at zero. |

**Validation invariants**:
- `remaining_seconds == 0 ⇔ next_allowed_at is None or next_allowed_at ≤ now`.
- `remaining_seconds ≤ min_interval_seconds` always.

#### `MultiSubDosePayload`

| Field | Type | Notes |
|---|---|---|
| `window_duration_seconds` | `int` | Constant for the medication. |
| `slots_total` | `int` | `medication.times_per_day`. |
| `active_window` | `ActiveWindow \| None` | Present iff a window is currently active (see invariants below). |
| `previous_window_unused_slots` | `int` | When the most recently expired window ended with one or more unused slots and no new window has started since, this is the count of unused slots in that previous window. Otherwise `0`. Drives the FR-008b banner. |

`ActiveWindow`:

| Field | Type | Notes |
|---|---|---|
| `window_start` | `datetime` (UTC) | First dose's `taken_at` for this window. |
| `window_end` | `datetime` (UTC) | `window_start + window_duration_minutes`. |
| `doses_in_window` | `list[datetime]` | Per-sub-dose taken-at timestamps, oldest-first. |
| `slots_used` | `int` | `len(doses_in_window)`. |
| `slots_remaining` | `int` | `slots_total - slots_used`, never negative. |

---

## New error type

### `MinIntervalNotElapsedError` (domain exception)

Defined in `domain/timers.py`. Plain Python exception.

| Attribute | Type | Notes |
|---|---|---|
| `medication_id` | `UUID` | The medication whose interval was violated. |
| `next_allowed_at` | `datetime` (UTC) | When a new dose becomes permitted. |
| `remaining_seconds` | `int` (≥ 1) | At the time of the violation. |

Raised inside `domain/doses.create_dose()` when a `count_down` med's
interval has not elapsed.

### `MinIntervalViolation` (wire-format model)

Pydantic model in `backend/src/medminder/api/schemas/errors.py`.

| Field | Type | Notes |
|---|---|---|
| `code` | `Literal["min_interval_not_elapsed"]` | Stable error identifier. |
| `medication_id` | `UUID` | From the domain exception. |
| `next_allowed_at` | `datetime` (UTC, RFC 3339) | From the domain exception. |
| `remaining_seconds` | `int` | From the domain exception. |

The FastAPI exception handler registered in `app.py` returns this body
with HTTP **409 Conflict** when `MinIntervalNotElapsedError` is
raised.

---

## Window invariants (`multi_sub_dose`)

Repeated here for quick reference; D5 in `research.md` carries the
prose rationale.

1. A window has fixed length `window_duration_minutes`.
2. `window_start = first_dose.taken_at` for the dose that opened the
   window. A dose opens a window iff, at its `taken_at`, no window
   was active.
3. A window is active iff `window_start ≤ now < window_end` AND there
   exists at least one non-voided dose with `taken_at ∈ [window_start,
   window_end)`.
4. `slots_used = |{ d ∈ non_voided_doses : window_start ≤ d.taken_at <
   window_end }|`.
5. The mark-as-taken control is disabled iff a window is active AND
   `slots_used ≥ slots_total`.
6. `previous_window_unused_slots` is computed from the most-recently
   expired window ONLY IF no new window has been started since that
   one expired. A new dose creates a new window AND clears the banner
   simultaneously.

These invariants are tested directly in
`backend/tests/domain/test_timers.py` via the shared JSON fixture
plus a handful of property-style cases that exercise the window
boundaries (start, end-exclusive, full slots, expired-with-unused).

---

## Migration impact (overall)

**NONE.** No Alembic revision is generated by Phase 5. The CI gate
`alembic upgrade head && alembic check` continues to pass with an
empty diff after Phase 5's PRs land.
