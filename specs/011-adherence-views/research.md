# Phase 0 Research — Long-term adherence views

All `NEEDS CLARIFICATION` were resolved in `spec.md` (Clarifications + Assumptions). This
file records the design decisions that shape the implementation.

## D1 — Adherence is derived, never stored

- **Decision**: Compute all per-day statuses, percentages, and course progress on read from
  the existing `doses` / `dose_voids` / `medications` / `schedules` / `schedule_medications`
  tables. No aggregate/summary table, no migration.
- **Rationale**: The data needed already exists and the single-tenant dose volume is small,
  so a materialized aggregate would be premature optimization and a data-duplication bug
  source (it could drift from the append-only ledger after a void). Honors data minimization
  (Principle I) and KISS/YAGNI (Principle III).
- **Alternatives considered**: A nightly-rolled `adherence_days` table (rejected: drift risk,
  new write surface, new migration, no measurable need at this scale); a Postgres view
  (rejected: per-day bucketing depends on the *caller's current* IANA zone, which a static
  SQL view can't parameterize cleanly).

## D2 — "Missed" semantics and the 4-hour tolerance

- **Decision**: For a medication's schedule slot expected on local day D, the slot is:
  **taken** if ≥1 non-voided dose links that (schedule, medication) within D's local-day
  window; **missed** if no such dose exists *and* the slot's scheduled datetime + **4 hours**
  is in the past; **future / not-yet-due** if the tolerance has not yet elapsed. A day with
  multiple expected slots is **partial** when some are taken and some missed, **taken** when
  all taken, **missed** when all missed.
- **Rationale**: Matches `docs/design/adherence-tracking.md` (4h working assumption) and the
  `/speckit-clarify` answer (no "skipped" state; scheduled-and-untaken-past-tolerance =
  missed). The tolerance prevents a slot from flipping to red the instant its time passes.
- **Alternatives considered**: Per-medication configurable tolerance (deferred to v2 per the
  spec assumption); end-of-day cutoff (rejected: too lenient for morning meds, and breaks the
  "did I take my 8am dose?" question by mid-morning).

## D3 — Adherence honors `days_of_week`; `today_view` does not

- **Decision**: The per-day expectation set uses `schedules.days_of_week` — a slot only
  counts as expected (and therefore can be "missed") on days its bitmask includes. This
  **differs** from `today_view`, which (post UX-enhancements) dropped the day-of-week SQL
  filter and instead mutes off-schedule rows visually.
- **Rationale**: A Mon–Fri medication must not be scored "missed" on weekends, or the
  percentage and calendar are wrong. `today_view`'s muting is a single-day UI affordance;
  adherence is a historical scoring view where the expectation set must be correct.
- **Alternatives considered**: Ignoring `days_of_week` like `today_view` (rejected: produces
  false "missed" and depresses the percentage for any non-daily schedule).

## D4 — Voided doses are excluded everywhere

- **Decision**: Every count (taken slots, percentage numerator, course progress, CSV rows)
  uses the established `NOT EXISTS (dose_voids)` filter. A voided dose contributes nothing.
- **Rationale**: A void is an explicit correction ("I didn't actually take it"); counting it
  would misreport adherence. Resolves the design doc's open question ("include un-taken
  doses? — no").
- **Alternatives considered**: Reporting voids separately in the export (deferred — corrections
  are rare; out of scope per the spec assumption).

## D5 — Day bucketing uses the user's *current* IANA zone

- **Decision**: Bucket every dose's `taken_at` into a local day using the user's current
  `users.timezone` (with the same optional `?timezone=` override the Today endpoint accepts),
  reusing `domain.timezone.resolve_today_bounds` per day across the range.
- **Rationale**: Consistent with the rest of the app (Today view, `max_doses_per_day` cap) and
  the clarified assumption. Resolves the design doc's open question.
- **Alternatives considered**: The zone in effect when each dose was recorded (rejected: not
  stored per-dose, and inconsistent with every other view).

## D6 — Course progress is a windowless per-med scalar, returned with the adherence read

- **Decision**: Course progress = count of the medication's **non-voided** doses vs
  `medications.total_doses`, plus a `complete` boolean (count ≥ total). It is independent of
  the calendar/trend date window and is returned in the same per-medication adherence response
  (rather than adding fields to the medications CRUD endpoints). Meds with `total_doses = NULL`
  return no course block. **Display-only** — reaching completion does not touch reminders,
  schedules, or the medication record (clarified).
- **Rationale**: Keeps the medications CRUD surface unchanged (loose coupling) while giving the
  detail page a single call for everything it renders. Course size has been captured since
  Phase 3; this is the read that gives it meaning.
- **Alternatives considered**: Adding `doses_taken`/`course_complete` to `MedicationRead`
  (rejected: bloats an unrelated contract and recomputes on every list fetch).

## D7 — One payload feeds both calendar and trend

- **Decision**: The per-medication adherence endpoint returns an ordered array of per-day
  records (date, expected-slot count, taken count, status enum). The calendar and the
  stacked-bar trend are two renderings of the same array; the window/month selection is a
  client concern driving the `from`/`to` query range.
- **Rationale**: The trend's marginal cost is "low if the first is well-modeled" (design doc).
  One contract avoids a second endpoint and keeps the two views consistent by construction.
- **Alternatives considered**: Separate calendar and trend endpoints (rejected: duplicate
  queries, drift risk between the two views).

## D8 — CSV export: stdlib `csv` + streamed attachment, full history

- **Decision**: `GET /api/v1/adherence/export.csv` streams `text/csv` with
  `Content-Disposition: attachment`, one row per **non-voided** dose across **all** the user's
  medications, columns: `medication_name, taken_at, quantity, unit, schedule_label,
  soft_deleted`. Soft-deleted medications are included with the name suffixed " (removed)"
  (and `soft_deleted=true`). Built with the stdlib `csv` module (no new dependency).
- **Rationale**: Matches the design doc's documented schema and UC-6.3. Streaming keeps memory
  flat regardless of history size. Including removed meds keeps an old export coherent.
- **Alternatives considered**: A date-range-filtered export (full history is the v1 scope per
  the assumption; a range filter is a later enhancement); an Excel/xlsx export (rejected:
  needs a dependency; CSV opens in any spreadsheet).

## Cross-cutting

- **Security**: Both endpoints scope every query to `get_current_user`; a `medication_id` in
  the path is always filtered by `user_id` so one user cannot read another's adherence. The
  CSV (PHI) is owner-only, unlogged, and not cached (the SW denylists `/api`).
- **Performance**: Range queries hit existing indexes on `doses(user_id)`,
  `doses(medication_id)`, `doses(schedule_id)`. No new index is needed at single-tenant scale;
  ADR-0016 notes a composite `(user_id, medication_id, taken_at)` index as a future option if
  history grows large.
- **Testing**: The classification matrix is exercised in `domain/test_adherence.py` without a
  server; the endpoints and CSV in `api/test_adherence_api.py` / `test_adherence_export.py`
  against real Postgres.
