# ADR-0016 — Adherence views are derived, never stored; "missed" = scheduled-and-untaken past a 4h tolerance

## Status

**Accepted** (Phase 9 — Long-term adherence views).

## Context

Phase 9 adds the long-term adherence surface from `docs/user_stories.md` UC-6: a
per-medication calendar ("did I take it yesterday?"), a stacked-bar trend, course progress
for fixed-course meds, and a CSV export of dose history. The roadmap colour-codes days
"taken / missed / skipped", but the data model has no user action that marks a dose as
deliberately *skipped* — `doses` are append-only takes and corrections are compensating
`dose_voids` rows (ADR-0005). We had to decide how adherence is computed and stored, what
"missed" means, how days are bucketed across time zones, and how completion behaves.

Constraints that shaped the decision:

- **Data minimization** (Principle I) — every new field/table needs justification.
- **Single-tenant, modest dose volume** — premature aggregation is a liability, not a win.
- Day bucketing depends on the **caller's current** IANA zone, like the rest of the app
  (`today_view`, the `max_doses_per_day` cap).
- The CSV carries medication names + timestamps (**PHI**); an installed PWA may live on a
  shared device.

## Decision

**Adherence is fully derived on read — no new table, no migration.** A new read-only
domain module `domain/adherence.py` computes everything from existing `doses`,
`dose_voids`, `medications`, `schedules`, `schedule_medications`, exposed by a thin
`/api/v1/adherence` router.

- **No "skipped" state.** A scheduled slot with no qualifying non-voided dose, once past a
  fixed **4-hour tolerance**, is **missed**; before the tolerance elapses it is
  *future/not-yet-due*. Day status is one of taken / partial / missed / future / inactive.
  Introducing a user-facing "skip" action is out of scope (it would need a new write
  surface and schema change).
- **Adherence honours `schedules.days_of_week`.** A slot is only *expected* (and so can be
  "missed") on the weekdays its schedule covers — a Mon–Fri med is *inactive*, not missed,
  on weekends. This **intentionally differs** from `today_view`, which (post UX-enhancements)
  dropped the day-of-week SQL filter and mutes off-day rows visually. Adherence is a
  historical scoring view where the expectation set must be correct.
- **Voided doses are excluded everywhere** (the `NOT EXISTS (dose_voids)` filter) — calendar,
  trend, percentage, course progress, and the CSV. A void is an explicit correction.
- **Current-TZ bucketing.** Each dose's `taken_at` is bucketed into a local day using the
  user's current `users.timezone` (with the same optional `?timezone=` override the Today
  endpoint accepts).
- **Adherence percentage** = `(taken ÷ expected) × 100` over days whose status is
  taken/partial/missed (inactive and future excluded), rounded to one decimal; **null** for
  PRN/unscheduled meds (no "missed" concept).
- **Course progress is display-only.** `total_doses` vs the non-voided dose count, with a
  `complete` flag; reaching completion has **no** side effects on reminders, schedules, or
  the medication record.
- **Window guard.** The per-medication range is capped at **366 days**; inverted or over-cap
  ranges are rejected (422).

## Consequences

- **No schema delta** — the ER diagram is unchanged (a one-line note records this). One fewer
  migration, no drift risk between an aggregate and the append-only ledger.
- The classification math is **pure** (`classify_day`, `window_adherence_pct`), unit-tested
  without a DB; the DB orchestration mirrors `today_view`'s building blocks.
- **Security**: both endpoints scope every query to `get_current_user`; a path
  `medication_id` is always filtered by `user_id` (no cross-user reads, FR-015). The CSV is
  owner-only, unlogged, and never cached (the service worker already denylists `/api`,
  ADR-0015). No new dependency (stdlib `csv`/`zoneinfo`).
- **Performance**: range queries hit the existing `doses(user_id)`, `doses(medication_id)`,
  `doses(schedule_id)` indexes. At single-tenant scale no new index is needed; a composite
  `(user_id, medication_id, taken_at)` index is a future option if history grows large.

## Alternatives considered

- **A rolled-up `adherence_days` aggregate table** — rejected: new write surface + migration,
  drift risk after a void, and no measurable need at this scale.
- **A Postgres view** — rejected: per-day bucketing depends on the caller's *current* zone,
  which a static view can't parameterize cleanly.
- **An explicit "skip dose" action / fourth state** — rejected for v1: needs new data + UI;
  the calendar's core value ("did I take it?") is delivered without it. Revisit if users ask.
- **Per-medication configurable tolerance** — deferred; 4h is hardcoded in v1 per the design
  doc.
