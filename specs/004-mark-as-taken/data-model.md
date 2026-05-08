# Data Model: mark-as-taken

## Phase context

The `doses` table **already exists** from Phase 1a. Its shape was
designed for this exact use case (see
`specs/2026-04-29-phase-1-data-model/requirements.md` §"doses",
decisions D4, D6, D7, D11). Phase 4 therefore ships:

- **No changes to `doses`.** The columns we need — `user_id`,
  `medication_id`, `schedule_id`, `taken_at`, `quantity`, `created_at` —
  are already in the migration.
- **One new table, `dose_voids`**, to record un-take events as
  compensating rows. This honors D6's append-only audit trail invariant
  ("`doses` are immutable from the application's perspective; corrections
  happen via inserting a compensating row, not by deleting or updating").
- A read-only "today view" join — no schema change required.

## Existing entity — `doses` (Phase 1a, unchanged)

Append-only record of a medication-taken event.

| Column          | Type                          | Notes                                                                                                |
| --------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| `id`            | `UUID PK`                     |                                                                                                      |
| `user_id`       | `UUID NOT NULL`               | FK → `users.id` (RESTRICT). Denormalized per D4. Postgres trigger asserts `== medications.user_id`. |
| `medication_id` | `UUID NOT NULL`               | FK → `medications.id` (RESTRICT). Never cascade-deletes (D6).                                        |
| `schedule_id`   | `UUID NULL`                   | FK → `schedules.id` (RESTRICT). Set for Today-view slot taps; `NULL` for ad-hoc logging.             |
| `taken_at`      | `TIMESTAMPTZ NOT NULL`        | Absolute instant (D11).                                                                              |
| `quantity`      | `NUMERIC(10, 3) NOT NULL`     | `CHECK quantity > 0` (D7).                                                                           |
| `created_at`    | `TIMESTAMPTZ NOT NULL`        |                                                                                                      |

**Phase 4 service rules:**

- `user_id` is derived from the session, never accepted from the
  request body.
- `quantity` defaults to `medications.quantity_per_dose` when the
  request omits it.
- `schedule_id` is required when the dose originates from the Today
  view (so per-slot adherence is computable) and `NULL` for ad-hoc
  doses logged outside the Today view.
- The application never UPDATEs or DELETEs from `doses`. Corrections
  flow through `dose_voids` (below).

## New entity — `dose_voids` (Phase 4)

Records that a previously-inserted `doses` row should be ignored by
the Today view, adherence queries, and (in Phase 7) inventory
decrement. Adding rows here never mutates `doses`.

| Column              | Type                          | Notes                                                                                  |
| ------------------- | ----------------------------- | -------------------------------------------------------------------------------------- |
| `id`                | `UUID PK`                     |                                                                                        |
| `dose_id`           | `UUID NOT NULL UNIQUE`        | FK → `doses.id` (RESTRICT). UNIQUE prevents double-void; second attempt returns `409`. |
| `voided_by_user_id` | `UUID NOT NULL`               | FK → `users.id` (RESTRICT). Service layer asserts it matches `doses.user_id`.          |
| `voided_at`         | `TIMESTAMPTZ NOT NULL`        | Recorded when the void event was created.                                              |
| `created_at`        | `TIMESTAMPTZ NOT NULL`        |                                                                                        |

A `Dose` is **effective** iff no matching `dose_voids` row exists.
"Effective" is the only state every downstream reader (Today view,
adherence queries, Phase 7 inventory) must apply.

## Validation rules (service layer)

- The session user must own the `medications` row referenced by
  `medication_id` (otherwise `403`).
- When `schedule_id` is provided, that schedule must (a) belong to the
  session user, (b) be `deleted_at IS NULL`, and (c) link to the given
  `medication_id` via `schedule_medications` (otherwise `422`).
- A void may only be issued for a dose belonging to the session user
  (otherwise `403`).
- A void on an already-voided dose returns `409`.

## State transitions

```
            POST /api/doses
   (none) ──────────────────▶  doses row inserted (effective)
                                       │
                                       │  POST /api/doses/{id}/void
                                       ▼
                              dose_voids row inserted (dose now ineffective)
```

There is no transition out of "voided" — re-taking the medication
records a fresh `doses` row instead.

## Today-view query (read-only, no schema change)

For session user `U` and a target date `D` in their `timezone` `Z`:

1. Resolve `[start_utc, end_utc)` = the UTC bounds of `D` in zone `Z`
   using `zoneinfo`.
2. Compute the Mon=0…Sun=6 day-of-week bit for `D` in `Z`.
3. Join `schedules s ⨝ schedule_medications sm ⨝ medications m`
   restricted to:
   - `m.user_id = U AND m.deleted_at IS NULL`
   - `s.user_id = U AND s.deleted_at IS NULL`
   - `(s.days_of_week & (1 << dow)) <> 0`
4. For each `(s.id, m.id)` slot, `LEFT JOIN doses d` on the same
   `(schedule_id, medication_id)` with `d.taken_at` in
   `[start_utc, end_utc)`, then `LEFT JOIN dose_voids dv ON dv.dose_id = d.id`
   `WHERE dv.id IS NULL`. The latest such effective dose (or `NULL`)
   is reported per slot.
5. Order by `s.time_of_day` ascending, then medication name.

## Reference

- Phase 1a schema and decisions:
  `specs/2026-04-29-phase-1-data-model/requirements.md` (D4, D6, D7,
  D11).
- ER diagram (will be updated to include `dose_voids`):
  `docs/diagrams/er.md`.
