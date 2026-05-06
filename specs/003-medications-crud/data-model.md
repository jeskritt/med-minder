# Data Model: Medications CRUD

## Entities

### 1. Medication
- `id` (UUID, primary key)
- `user_id` (UUID, foreign key to users)
- `name` (String, required)
- `dosage` (String, required, e.g., "500")
- `unit` (String, required, e.g., "mg")
- `times_per_day` (Integer, required)
- `start_date` (Date, required)
- `end_date` (Date, optional)
- `total_doses` (Integer, optional, NULL if untracked/as needed)
- `refill_count` (Integer, optional)
- `refill_threshold` (Integer, optional)
- `is_deleted` (Boolean, default: false)
- `created_at` (DateTime, default: now)
- `updated_at` (DateTime, default: now, on update: now)

**Validation Rules:**
- `end_date` must be >= `start_date` if provided.
- `total_doses` must be strictly NULL for untracked meds; no manual `0` is allowed.
- `name`, `dosage`, `unit` must not be blank.

### 2. Schedule
- `id` (UUID, primary key)
- `medication_id` (UUID, foreign key to medications)
- `time_of_day` (Time, required)
- `created_at` (DateTime, default: now)
- `updated_at` (DateTime, default: now, on update: now)

**Relationships:**
- `Medication` has a one-to-many relationship with `Schedule`.
