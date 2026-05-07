# Data Model: Medications CRUD

> **Reconciliation note (2026-05-07):** the `medications`, `schedules`, and
> `schedule_medications` tables already shipped in the Phase 1 baseline migration
> (`backend/alembic/versions/0001_phase_1_baseline.py`). This phase builds on
> that schema rather than redefining it. The columns listed below are the
> authoritative model; the Phase 1 columns we add to are noted explicitly.

## Entities

### 1. Medication (existing — `medications` table)

Already defined in `backend/src/medminder/db/models/medications.py`. Existing
columns reused unchanged:

- `id` (UUID, PK, `gen_random_uuid()`)
- `user_id` (UUID, FK → `users.id`, RESTRICT, indexed)
- `name` (Text, required)
- `quantity_per_dose` (Numeric(10,3), required, > 0) — the spec's "dosage"
- `unit` (Text, required, e.g. `"mg"`)
- `times_per_day` (SmallInt, required, ≥ 0)
- `start_date` (Date, optional)
- `end_date` (Date, optional)
- `total_doses` (Integer, optional, NULL ⇒ untracked / as-needed)
- `timer_preference` (enum, required) plus `min_interval_minutes`,
  `window_duration_minutes` — Phase 1a fields, defaulted to `none` for
  Phase 3 records.
- `total_doses_filled`, `doses_remaining` (defaults `0`)
- `deleted_at` (TimestampTZ, nullable) — soft-delete sentinel; replaces the
  `is_deleted` boolean from the original spec.
- `created_at`, `updated_at`

**New columns added by this phase:**

- `refill_count` (Integer, optional, ≥ 0)
- `refill_threshold` (Integer, optional, ≥ 0)

**Validation rules (enforced in domain layer):**

- `end_date` must be `>= start_date` when both are set.
- `total_doses` must be NULL when "untracked"; manual `0` is rejected
  (Phase 1 already has a CHECK `total_doses IS NULL OR total_doses > 0`).
- `name`, `unit` must be non-blank; `quantity_per_dose` must be > 0.

### 2. Schedule (existing — `schedules` table) and join

Already defined in `backend/src/medminder/db/models/schedules.py`:

- `id`, `user_id`, `time_of_day` (Time), `days_of_week` (bitmask, default 127),
  `label` (Text, NOT NULL), `deleted_at`, `created_at`, `updated_at`.

The link to medications is the existing M:M join `schedule_medications`
(`schedules.id` × `medications.id`). The Phase 3 inline-schedule UX uses a
**complete replacement** strategy:

- POST: create `Schedule` rows for each `time_of_day` the user supplied,
  link via `schedule_medications`. Default `label = medication.name`,
  `days_of_week = 127` (every day).
- PUT: drop the `schedule_medications` rows for the medication, soft-delete
  the previously-linked `Schedule` rows (set `deleted_at`), then create new
  ones (research.md item 2 — "complete replacement").
- DELETE (soft): leaves the schedules in place. They are filtered out by
  the medication's `deleted_at` from the listing query.

This shape diverges from the original spec's "Schedule has direct
`medication_id` FK" — that idea was superseded by the existing M:M join.
