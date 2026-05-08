# MedMinder — Entity-Relationship Diagram

The schema below is the v1 data model committed in Phase 1, plus the
`dose_voids` table added in Phase 4. Every table, column, and
relationship matches the committed Alembic migrations
(`backend/alembic/versions/0001_phase_1_baseline.py` and
`backend/alembic/versions/XXXX_add_dose_voids_table.py`) and the
SQLAlchemy models under `backend/src/medminder/db/models/`.

For the rationale behind individual choices, see the **Decisions
(D1–D12)** table in
`specs/2026-04-29-phase-1-data-model/requirements.md`. Highlights
that don't render cleanly in Mermaid:

- **D2** — `schedules.days_of_week` is a 7-bit bitmask
  (`Mon=bit 0 … Sun=bit 6`), `CHECK BETWEEN 0 AND 127`.
- **D3** — `reminders` carries two nullable FKs and a CHECK ensuring
  exactly one is set per `type` value.
- **D4** — `doses.user_id` is denormalized; a Postgres trigger
  enforces `doses.user_id == medications.user_id`.
- **D5** — `medication_interactions` is symmetric in semantics; a
  unique index on the unordered pair (`LEAST/GREATEST`) prevents
  duplicates.
- **D6** — `users`, `medications`, `schedules` are soft-deleted via
  `deleted_at`; `doses` are append-only.
- **D6 (Phase 4)** — un-take is recorded as a compensating row in
  `dose_voids` with `UNIQUE(dose_id)`. Readers (Today view,
  adherence) `LEFT JOIN dose_voids` and ignore doses with a matching
  void. `doses` rows themselves are never updated or deleted.
- **D8** — `users.email` uniqueness is enforced via a functional
  unique index on `LOWER(email)`.
- **D10** — `push_subscriptions` has UNIQUE `(user_id, endpoint)`.

```mermaid
erDiagram
    users ||--o{ sessions : "has"
    users ||--o{ push_subscriptions : "has"
    users ||--o{ medications : "owns"
    users ||--o{ schedules : "owns"
    users ||--o{ doses : "logs"
    users ||--o{ reminders : "receives"

    medications ||--o{ medication_interactions : "conflicts_a"
    medications ||--o{ medication_interactions : "conflicts_b"
    medications ||--o{ schedule_medications : "in"
    schedules ||--o{ schedule_medications : "in"

    medications ||--o{ doses : "logged"
    schedules  ||--o{ doses : "slot"

    doses ||--o| dose_voids : "voided_by"
    users ||--o{ dose_voids : "voids"

    medications ||--o{ reminders : "refill_of"
    schedules  ||--o{ reminders : "dose_of"

    users {
        uuid id PK
        text email "UNIQUE LOWER(email)"
        text password_hash "argon2id"
        text name
        user_role role "admin | user"
        text timezone "IANA"
        time quiet_hours_start
        time quiet_hours_end
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }

    sessions {
        uuid id PK
        uuid user_id FK "ON DELETE CASCADE"
        text token_hash "UNIQUE; SHA-256"
        timestamptz expires_at
        timestamptz created_at
    }

    push_subscriptions {
        uuid id PK
        uuid user_id FK "ON DELETE CASCADE"
        text endpoint
        text p256dh
        text auth
        timestamptz created_at
    }

    medications {
        uuid id PK
        uuid user_id FK "ON DELETE RESTRICT"
        text name
        smallint times_per_day "CHECK >= 0"
        numeric quantity_per_dose "10,3 CHECK > 0"
        text unit
        date start_date
        date end_date
        integer total_doses "CHECK > 0 OR NULL"
        timer_preference timer_preference "none|count_up|count_down|multi_sub_dose"
        integer min_interval_minutes "required for count_down"
        integer window_duration_minutes "required for multi_sub_dose"
        integer total_doses_filled "DEFAULT 0"
        integer doses_remaining "DEFAULT 0"
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }

    medication_interactions {
        uuid id PK
        uuid medication_id FK "ON DELETE RESTRICT"
        uuid conflicting_medication_id FK "ON DELETE RESTRICT"
        integer cooldown_minutes "CHECK > 0"
        timestamptz created_at
    }

    schedules {
        uuid id PK
        uuid user_id FK "ON DELETE RESTRICT"
        time time_of_day "naive, user-local"
        smallint days_of_week "bitmask 0..127"
        text label
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }

    schedule_medications {
        uuid schedule_id PK,FK "ON DELETE CASCADE"
        uuid medication_id PK,FK "ON DELETE CASCADE"
        timestamptz created_at
    }

    doses {
        uuid id PK
        uuid user_id FK "ON DELETE RESTRICT; D4 trigger"
        uuid medication_id FK "ON DELETE RESTRICT"
        uuid schedule_id FK "nullable"
        timestamptz taken_at
        numeric quantity "10,3 CHECK > 0"
        timestamptz created_at
    }

    dose_voids {
        uuid id PK
        uuid dose_id FK "UNIQUE; ON DELETE RESTRICT"
        uuid voided_by_user_id FK "ON DELETE RESTRICT"
        timestamptz voided_at
        timestamptz created_at
    }

    reminders {
        uuid id PK
        uuid user_id FK "ON DELETE CASCADE"
        reminder_type type "dose | refill"
        uuid medication_id FK "nullable; ON DELETE CASCADE"
        uuid schedule_id FK "nullable; ON DELETE CASCADE"
        reminder_status status "pending|sent|snoozed|dismissed DEFAULT pending"
        timestamptz scheduled_for
        timestamptz created_at
        timestamptz updated_at
    }
```
