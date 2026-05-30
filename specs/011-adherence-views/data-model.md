# Phase 1 Data Model — Long-term adherence views

**No schema change. No migration.** This feature is entirely **derived** from existing
tables (D1). This document describes the existing tables it reads and the **derived,
non-persisted** structures the domain computes.

## Existing tables read (no modification)

| Table | Columns used | Role in adherence |
|---|---|---|
| `medications` | `id`, `user_id`, `name`, `unit`, `quantity_per_dose`, `total_doses`, `timer_preference`, `start_date`, `end_date`, `deleted_at` | The subject; `total_doses` drives course progress; `start_date`/`end_date` bound the "active" window (inactive days); `deleted_at` → "(removed)" in export |
| `schedules` | `id`, `user_id`, `time_of_day`, `days_of_week`, `label`, `deleted_at` | The **expected** slots per day; `days_of_week` decides whether a slot is expected on a given local day (D3); `label` → CSV `schedule_label` |
| `schedule_medications` | `schedule_id`, `medication_id` | M:M linking a medication to its expected slots |
| `doses` | `id`, `user_id`, `medication_id`, `schedule_id`, `taken_at`, `quantity` | The **taken** events; bucketed into local days by `taken_at` (D5) |
| `dose_voids` | `dose_id` | Excludes voided doses everywhere via `NOT EXISTS` (D4) |
| `users` | `timezone` | Current-TZ day bucketing (D5) |

No new columns, constraints, indexes, or tables are added. (ADR-0016 notes a possible future
composite index on `doses(user_id, medication_id, taken_at)` if history volume grows; **not**
part of this phase.)

## Derived structures (in-memory, `domain/adherence.py`)

### `DayStatus` (enum)

`taken` | `partial` | `missed` | `future` | `inactive`

- **inactive** — local day is before `start_date` or after `end_date`, **or** the medication
  has no slot expected that day (per `days_of_week`) and no dose taken. Excluded from the
  adherence percentage (FR-014).
- **future** — at least one expected slot whose `scheduled time + 4h tolerance` is still in
  the future and is untaken; no expected slot is yet "missed".
- **taken / partial / missed** — over the day's *expected* slots (honoring `days_of_week`):
  all taken / some taken / none taken-and-past-tolerance.

A PRN/unscheduled medication (no linked active schedule) never produces `missed`: days with a
non-voided dose are `taken`, all others `inactive` (FR-006).

### `DayAdherence` (one per local day in the requested range)

| Field | Type | Notes |
|---|---|---|
| `date` | date (local) | Day in the user's current TZ |
| `expected` | int | Count of slots expected that day (0 for PRN / non-scheduled days) |
| `taken` | int | Count of expected slots with ≥1 non-voided dose that day |
| `status` | `DayStatus` | Classified per the rules above |

### `MedicationAdherence` (the per-medication windowed response)

| Field | Type | Notes |
|---|---|---|
| `medication_id` | uuid | Echoed |
| `timezone` | str | The IANA zone actually used for bucketing |
| `from` / `to` | date | The local-day range covered. **Wire names** are `from`/`to`; because `from` is a Python keyword, the Pydantic model and the FastAPI query params declare aliased fields (e.g. `from_: date = Query(alias="from")`, `model_config = {"populate_by_name": True}`) so the OpenAPI schema — and thus the generated TS client — still uses `from`/`to`. |
| `days` | `DayAdherence[]` | Ordered ascending; feeds both calendar and trend (D7) |
| `adherence_pct` | number \| null | `(taken_slots ÷ expected_slots) × 100`, a **0–100** value rounded to one decimal place, over the window, excluding inactive/future days; **null** for PRN/unscheduled meds (no "missed") (FR-017) |
| `course` | `CourseProgress` \| null | Present iff `total_doses` is set (D6) |

### `CourseProgress`

| Field | Type | Notes |
|---|---|---|
| `total` | int | `medications.total_doses` |
| `taken` | int | Non-voided dose count for the medication (window-independent) |
| `complete` | bool | `taken >= total` (display-only — no side effects) |

### `ExportRow` (one per non-voided dose, all medications)

| Column | Source | Notes |
|---|---|---|
| `medication_name` | `medications.name` | Suffixed " (removed)" when `deleted_at` is set (FR-012) |
| `taken_at` | `doses.taken_at` | ISO-8601, in the user's current TZ |
| `quantity` | `doses.quantity` | |
| `unit` | `medications.unit` | |
| `schedule_label` | `schedules.label` | Empty when the dose has no `schedule_id` |
| `soft_deleted` | `medications.deleted_at is not None` | `true`/`false` |

## Validation / invariant notes

- Every query filters on the session user's `id`; a path `medication_id` is always joined with
  `medications.user_id = current_user.id` (cross-user isolation, FR-015).
- Voided doses are excluded by the same `NOT EXISTS (SELECT 1 FROM dose_voids WHERE
  dose_voids.dose_id = doses.id)` pattern used by `today_view` (D4).
- The range endpoint caps the maximum span at **366 days** to bound work; a span wider than
  that, or an inverted range (`to` < `from`), → 422 (FR-018). An unknown `timezone` → 400.
