# ADR-0009: UX-enhancements batch — schedules, pill model, Today behavior

## Status

Accepted

## Context

After Phase 6 shipped, manual testing surfaced a cluster of usability
gaps that warranted a focused, non-roadmap batch (branch
`ux_enhancments`) before Phase 7. The changes are individually small
but together shift a few load-bearing concepts, so they are recorded
here as one decision rather than scattered across commits:

- Schedules were effectively per-medication (each med save created its
  own `schedules` rows), so a user's "8:00 AM" appeared many times and
  couldn't be curated.
- Dosing was entered as a raw `quantity_per_dose`, which is awkward for
  the common "2 × 200 mg tablets" case.
- `multi_sub_dose` enforced only a per-window slot cap, with no way to
  bound total doses across a day.
- `/today` hid any med not scheduled for *today* (day-of-week filter),
  and hid unscheduled timer/PRN meds entirely — so the screen wasn't a
  complete picture and a "no take button" surprise was common.

## Decision

1. **Schedules are shared user-level resources.** A med save now
   attaches existing schedules by id; schedule lifecycle is its own
   CRUD (`GET/POST/DELETE /api/v1/schedules`). The `schedule_medications`
   join already modelled the M:N link, so no schema change was needed —
   only the create/update semantics changed.
2. **Pill-based dosage is a parallel, optional model.** Nullable
   `pill_strength` + `pills_per_dose` (paired by CHECK); when set, the
   med is "pill-based" and `quantity_per_dose` is derived server-side
   (`pill_strength * pills_per_dose`). Timer, inventory, and display
   code stay unchanged because the derived value lands in the existing
   column.
3. **`multi_sub_dose` two-cap.** New nullable `max_doses_per_day` adds a
   per-day cap enforced beside the per-window slot cap; exceeding it
   raises `daily_cap_reached` (409). Per ADR-0008 this is a
   non-overridable overdose guard.
4. **`/today` always shows the take button + out-of-schedule confirm.**
   The day-of-week filter is dropped server-side; rows carry
   `days_of_week` / `scheduled_today` so the frontend mutes (visual
   only) rows not normally scheduled today. Taking an out-of-schedule
   dose (off-day, or > ±2h from the slot) is allowed but gated by a
   confirm modal — per-row, and once-per-group for "Take all" (cancel
   aborts the whole Take-all).
5. **Unscheduled timer meds appear on `/today` while their timer is
   running** (`domain.timers.is_timer_active`): `count_down` while
   counting, `multi_sub_dose` while the window is open, `count_up`
   within 24h of the last dose. Such rows carry `schedule_id = null`,
   group under "As needed", and are never muted or out-of-schedule.
   The 24h count_up horizon resolves the long-standing open question in
   `docs/design/timer-modes.md`.
6. **Lenient color thresholds are visual only** — they drive per-row
   color coding on `/today` and never block a take. Hard blocks remain
   the ADR-0008 overdose guards (count_down min-interval,
   multi_sub_dose window-full, daily_cap_reached).

## Consequences

### Positive

- One curated schedule list per user; one screen shows scheduled slots
  and active PRN/timer cycles together.
- Pill entry matches how users think; derivation keeps downstream code
  untouched.
- A real per-day ceiling for split-dose meds without weakening the
  per-window cap.

### Negative

- `TodayItem.schedule_id` / `scheduled_time` are now nullable — a wire
  contract change consumers must handle.
- An unscheduled `count_up` med stays on `/today` for up to 24h after
  each dose; with many such meds this can add rows (accepted; revisit
  if noisy).

### Neutral

- Existing duplicate per-med `schedules` rows remain until the user
  dedupes them via the new schedule UI; no data backfill was run.
- No new Alembic migration beyond `0005` (pill model + daily cap); the
  Today and schedule changes are query/compute + API-semantics only.
