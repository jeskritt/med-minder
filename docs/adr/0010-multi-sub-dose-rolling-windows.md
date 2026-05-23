# ADR-0010: multi_sub_dose uses rolling per-dose windows

## Status

Accepted

Supersedes the `multi_sub_dose` window model described in
**ADR-0009 §3 / §5** and the original tiled-window design in
`docs/design/timer-modes.md`.

## Context

`multi_sub_dose` (Billy Bat's split-dose case) originally tiled doses
into a single, non-overlapping window: the first dose opened a window
`[start, start + window_duration)` that held up to `times_per_day`
doses; once it expired (or filled), the next dose opened a fresh tile
(`group_windows`).

Live testing showed this does **not** enforce the actual safety intent
("don't take more than N within `window_duration`"). Because tiles are
anchored to the first dose, a user could take N doses near the end of
one tile and N more at the start of the next — up to 2N in roughly one
`window_duration`. The card copy ("X of 3 this window · window ends
…") also implied a shared clock that doesn't match how a patient thinks
about staggered doses.

The product intent, confirmed with the user, is: **each dose has its
own window, and at most N may overlap at once** ("max N at a time").

## Decision

1. **Rolling per-dose windows.** Each non-voided dose is "active" for
   `window_duration_minutes` after its `taken_at`. A prospective dose
   at `T` is allowed iff fewer than `N` doses are active at `T` — i.e.
   `count(taken_at ∈ (T − window, T]) < N`. When at capacity, the next
   slot frees at the **oldest active dose's** `taken_at + window`.
2. **Reuse existing columns — no migration.** `times_per_day` is
   reinterpreted as the **max-concurrent cap** (`N`, surfaced as "Max
   doses at a time" in the form), and `window_duration_minutes` is the
   **per-dose** window length. `max_doses_per_day` is unchanged: a
   separate optional **daily** hard cap, still validated `>= N`.
3. **Single source of truth.** `domain.timers._active_at` computes the
   active set for both `compute_timer_state` and the
   `multi_sub_dose_window_full` overdose guard, so the read-side card
   and the write-side 409 can never disagree.
4. **Wire shape.** `MultiSubDosePayload` now carries `max_concurrent`,
   `active_sub_doses[{taken_at, expires_at}]`, `slots_used`,
   `slots_remaining`, and `next_available_at` (replacing
   `slots_total` / `active_window` / `previous_window_unused_slots`).
   The `window_full` 409 body's `window_end` became `next_available_at`
   (same `code`). `is_timer_active` for the mode is `slots_used > 0`.

This remains a non-overridable Phase-5 overdose guard (ADR-0008): a
drug-interaction acknowledgment never defeats the `window_full` 409.

## Consequences

### Positive

- The cap now means what users expect: never more than `N` doses in any
  rolling `window_duration`, regardless of timing.
- The card reads naturally — one row per active dose with its own
  "frees at" time, and a clear "next dose at HH:MM" when at capacity.
- No schema change; `alembic check` stays clean.

### Negative

- A wire-contract change consumers must handle (`MultiSubDosePayload`
  reshape; `window_full` body field rename). Single-tenant, no external
  consumers, but every test asserting the old fields was rewritten.
- `times_per_day` carries a mode-dependent meaning (daily count for
  non-`multi_sub_dose`; max-concurrent for `multi_sub_dose`). The form
  relabels it per mode to keep this legible.

### Neutral

- The "previous window unused slots" passive banner (FR-008b) is gone —
  it was an artifact of the tiled model and has no rolling-window
  analogue.
- Existing `multi_sub_dose` medications need no data migration; their
  history is reinterpreted under the rolling rule on next read.
