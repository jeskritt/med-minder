# Phase 1 — Data Model & Admin CLI: Requirements

## Why this phase

Phase 0 delivered a runnable, typed, tested skeleton with no domain
behavior. Phase 1 introduces the v1 data schema and the admin CLI that
operates on it. The two pieces are bundled because the CLI is the
production-supported path to seed the first admin user, and exercising
the schema through real CRUD operations (rather than synthetic ORM
tests alone) is the most honest validation of the model.

## Sub-phases

- **1a — Data model & migrations.** SQLAlchemy 2.0 typed models,
  Alembic baseline migration, ER diagram.
- **1b — Admin CLI.** Typer app with `user add | delete | update | list`
  plus `db backup | restore`, sharing the Phase 1a domain layer.

## In scope

### 1a — Data model
- SQLAlchemy 2.0 declarative base configured for the typed style.
- Alembic configured against the project Postgres; baseline migration
  that creates every table listed under "Data schema" below.
- Postgres service container added to GitHub Actions CI; tests run
  against a real database, not SQLite.
- ER diagram committed to `docs/diagrams/er.md` (Mermaid).
- Unit tests covering NOT NULL, UNIQUE, FK cascades, CHECK constraints,
  and enum validation for every model.

### 1b — Admin CLI
- `medminder-admin` console-script entry point installed by
  `backend/pyproject.toml`.
- Subcommands:
  - `user add --email --name --role [--password-stdin]`
  - `user delete --email` (soft delete; see "History preservation")
  - `user update --email [--password-stdin] [--new-email] [--name] [--role]`
  - `user list [--role]`
  - `db backup --out <path>` — `pg_dump` wrapper, custom format.
  - `db restore --in <path> [--yes]` — `pg_restore` wrapper with an
    explicit confirmation flag.
- Argon2id password hashing via `argon2-cffi`.
- All write commands run inside a single transaction.
- Domain logic (creating users, hashing passwords, etc.) lives in a
  shared module that the future web auth code (Phase 2) will reuse —
  no duplication of password rules between CLI and HTTP.
- Integration tests against the same Postgres service container used
  by 1a.

## Out of scope (deferred)

- Login UI, session cookies, CSRF, auth middleware — Phase 2.
- Medication CRUD endpoints — Phase 3.
- Reminders delivery / APScheduler / Web Push — Phase 7.
- Drug-interaction enforcement logic (the *table* lands in 1a; the
  enforcement *rules* land in Phase 6).
- A web-based user-management UI — there is none in v1 by design
  (`specs/mission.md` non-goals).
- Soft-delete UI / "trash bin" — soft delete is a backend concept in
  v1; no user-facing surface.

## Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | `medications.times_per_day` semantics | **Source of truth.** App emits a warning when the count of attached schedules disagrees, but never auto-derives. | The user models intent ("3 doses/day") independently of the schedule rows. The mismatch is data the user wants flagged, not silently reconciled. |
| D2 | `schedules.days_of_week` representation | **7-bit bitmask** stored as `SMALLINT` (Mon=bit 0 … Sun=bit 6); default `0b1111111` (all days). | Compact, indexable, atomic. Postgres array would invite per-row scans for "which schedules fire today?" queries. |
| D3 | `reminders` reference shape | **Two nullable FKs** (`medication_id`, `schedule_id`) with a CHECK constraint enforcing exactly one is set, matched against `type`. | Preserves DB-level referential integrity. Polymorphic `reference_id` would silently orphan on delete. |
| D4 | `doses.user_id` | **Denormalized FK on `doses`**, copied from `medications.user_id` at insert. | Adherence queries ("everything user X took this week") avoid the join. Constraint: `doses.user_id == medications.user_id` is enforced via trigger or application-level check; documented in the migration. |
| D5 | `medication_interactions` directionality | **Symmetric in semantics, asymmetric in storage.** A single row `(medication_id=A, conflicting_medication_id=B, cooldown_minutes=N)` means "do not take A within N minutes of B *and* do not take B within N minutes of A." Phase 6 enforces both directions. | Tylenol-style: only the less-common drug carries the note. Halves row count and keeps the editing UX simple. UNIQUE on the unordered pair (least-id, greatest-id) prevents duplicates. |
| D6 | Deletion / history | **Soft delete only.** `users`, `medications`, and `schedules` get `deleted_at TIMESTAMPTZ NULL`. `doses` are append-only and never cascade-delete. | The mission promises "an honest record of adherence over time" — cascading would silently destroy that history. Refill warnings and adherence views filter on `deleted_at IS NULL` for the active set. |
| D7 | Dosage numeric type | **`Numeric(10, 3)`** for `quantity_per_dose` and `quantity` on doses. | Float is unsafe for fractional medical units (0.5 mg, 0.125 mg, etc.). 10/3 fits any realistic dose with three-decimal precision. |
| D8 | `users.email` uniqueness | **Functional UNIQUE index on `LOWER(email)`** + storage as-typed. CLI lowercases before lookup. | Case-insensitive uniqueness without losing the user's preferred casing in display. |
| D9 | `users.password_hash` algorithm | **Argon2id** via `argon2-cffi` (already implied by `tech-stack.md`). | Mission-mandated — see `specs/mission.md` engineering principles. |
| D9b | `sessions.token_hash` algorithm | **SHA-256** of the random token bytes. | Session tokens are high-entropy random values, not low-entropy passwords. A slow KDF here would tax every authenticated request without adding security. |
| D10 | `push_subscriptions` uniqueness | **UNIQUE `(user_id, endpoint)`**. | Prevents duplicate rows on re-subscribe; matches Web Push semantics where `endpoint` is the device-unique identifier. |
| D11 | Time / timezone handling | **Schedule times stored in the user's local timezone** (naive `Time`); `users.timezone` is the IANA zone string used at scheduling time to convert to UTC. All `created_at`/`updated_at`/`taken_at`/`expires_at`/`scheduled_for` columns are `TIMESTAMPTZ`. | Wall-clock times that survive DST transitions need to be *user-local* + zone, not UTC. Event timestamps need to be absolute, hence TIMESTAMPTZ. Consistent across the schema. |
| D12 | Inventory fields naming | `total_doses_filled` = doses received in the most recent fill (e.g. "30 from the pharmacy"); `doses_remaining` = current inventory, decremented on each `dose` insert; `total_doses` (optional) = course size for fixed-duration prescriptions like a 14-day antibiotic. All three may coexist. | Disambiguates *prescription duration* from *inventory tracking* per `specs/mission.md`. |

## Data schema

All UUIDs are `UUID` (Postgres native, generated server-side via `gen_random_uuid()`).
All timestamps are `TIMESTAMPTZ`. All tables get `created_at` and (where
mutable) `updated_at`.

### users
- `id UUID PK`
- `email TEXT NOT NULL` — UNIQUE on `LOWER(email)` (D8)
- `password_hash TEXT NOT NULL` — Argon2id (D9)
- `name TEXT NOT NULL`
- `role` enum `('admin', 'user') NOT NULL`
- `timezone TEXT NOT NULL` — IANA zone, e.g. `"America/New_York"` (D11)
- `quiet_hours_start TIME NULL`, `quiet_hours_end TIME NULL`
- `deleted_at TIMESTAMPTZ NULL` (D6)
- `created_at`, `updated_at`

### sessions
- `id UUID PK`
- `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `token_hash TEXT NOT NULL UNIQUE` — SHA-256 hex (D9b)
- `expires_at TIMESTAMPTZ NOT NULL`
- `created_at`

### push_subscriptions
- `id UUID PK`
- `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `endpoint TEXT NOT NULL`
- `p256dh TEXT NOT NULL`, `auth TEXT NOT NULL`
- `created_at`
- `UNIQUE (user_id, endpoint)` (D10)

### medications
- `id UUID PK`
- `user_id UUID NOT NULL REFERENCES users(id)` — restrict on delete; soft delete only (D6)
- `name TEXT NOT NULL`
- `times_per_day SMALLINT NOT NULL CHECK (times_per_day >= 0)` — source of truth (D1)
- `quantity_per_dose NUMERIC(10, 3) NOT NULL CHECK (quantity_per_dose > 0)` (D7)
- `unit TEXT NOT NULL` — e.g. `"mg"`, `"pills"`, `"units"`
- `start_date DATE NULL`, `end_date DATE NULL`
- `total_doses INTEGER NULL CHECK (total_doses > 0)` — course size (D12)
- `timer_preference` enum `('none', 'count_up', 'count_down', 'multi_sub_dose') NOT NULL`
- `min_interval_minutes INTEGER NULL` — required for `count_down` (CHECK at app layer; cross-column CHECK in migration)
- `window_duration_minutes INTEGER NULL` — required for `multi_sub_dose`
- `total_doses_filled INTEGER NOT NULL DEFAULT 0` — most recent fill (D12)
- `doses_remaining INTEGER NOT NULL DEFAULT 0` — current inventory (D12)
- `deleted_at TIMESTAMPTZ NULL` (D6)
- `created_at`, `updated_at`

### medication_interactions
- `id UUID PK`
- `medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE RESTRICT`
- `conflicting_medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE RESTRICT`
- `cooldown_minutes INTEGER NOT NULL CHECK (cooldown_minutes > 0)`
- `CHECK (medication_id <> conflicting_medication_id)`
- UNIQUE on the unordered pair: implemented as `UNIQUE (LEAST(id_a, id_b), GREATEST(id_a, id_b))` via expression index (D5)

### schedules
- `id UUID PK`
- `user_id UUID NOT NULL REFERENCES users(id)` — restrict on delete; soft delete only
- `time_of_day TIME NOT NULL` — naive, in user's TZ (D11)
- `days_of_week SMALLINT NOT NULL DEFAULT 127 CHECK (days_of_week BETWEEN 0 AND 127)` — bitmask (D2)
- `label TEXT NOT NULL` — e.g. `"Morning"`, `"Bedtime"`
- `deleted_at TIMESTAMPTZ NULL`
- `created_at`, `updated_at`

### schedule_medications (M:M association)
- `schedule_id UUID NOT NULL REFERENCES schedules(id) ON DELETE CASCADE`
- `medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE`
- `PRIMARY KEY (schedule_id, medication_id)`
- `created_at`

### doses
- `id UUID PK`
- `user_id UUID NOT NULL REFERENCES users(id)` — denormalized (D4)
- `medication_id UUID NOT NULL REFERENCES medications(id)` — RESTRICT; never cascade (D6)
- `schedule_id UUID NULL REFERENCES schedules(id)` — set when the dose was logged against a specific scheduled slot
- `taken_at TIMESTAMPTZ NOT NULL`
- `quantity NUMERIC(10, 3) NOT NULL CHECK (quantity > 0)` (D7)
- `created_at`
- Trigger / app check: `doses.user_id == medications.user_id` (D4)

### reminders
- `id UUID PK`
- `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `type` enum `('dose', 'refill') NOT NULL`
- `medication_id UUID NULL REFERENCES medications(id) ON DELETE CASCADE`
- `schedule_id UUID NULL REFERENCES schedules(id) ON DELETE CASCADE`
- `status` enum `('pending', 'sent', 'snoozed', 'dismissed') NOT NULL DEFAULT 'pending'`
- `scheduled_for TIMESTAMPTZ NOT NULL`
- `created_at`, `updated_at`
- CHECK constraint per D3:
  - `type='dose'`   → `schedule_id IS NOT NULL AND medication_id IS NULL`
  - `type='refill'` → `medication_id IS NOT NULL AND schedule_id IS NULL`

## Constraints from the constitution

- Fully typed: SQLAlchemy 2.0 *typed* `Mapped[...]` style; `mypy --strict`
  passes on every model.
- No duplication: the CLI and (future) HTTP auth share one
  `users` domain module — password hashing, role checks, lookup-by-email
  all live there.
- Minimal data collection: no fields beyond those listed above. New
  fields require an updated requirements doc and a migration.
- Append-only audit trail: `doses` are immutable from the application's
  perspective. Corrections happen via inserting a compensating row, not
  by deleting or updating.
- Pinned deps: `argon2-cffi`, `sqlalchemy`, `alembic`, `psycopg[binary]`
  (sync, for Alembic), `asyncpg` (async, for the app), `typer`,
  `pytest-cov` are added with upper bounds in `backend/pyproject.toml`.

## Security considerations for new surface area

- **Password hashing.** Argon2id with `argon2-cffi` defaults; reject
  passwords < 12 chars in the CLI; never log raw passwords or password
  hashes (ruff `S105`/`S106` should fire on accidental literals).
- **CLI secret handling.** `--password-stdin` is the only way to provide
  a password; no `--password` flag (process listings, shell history).
- **Backup files.** `db backup` outputs contain every password hash and
  every medication record. The CLI prints a "treat this file as PHI"
  warning and chmods it to `0600` after writing.
- **DB roles.** Migration runner uses a privileged role; the runtime
  app role gets `SELECT, INSERT, UPDATE, DELETE` on tables but no DDL.
  Both are documented in `docs/deployment.md`.
- **Soft-delete leakage.** Default ORM queries filter on
  `deleted_at IS NULL`; the CLI explicitly opts in to seeing tombstoned
  rows. Documented in the domain module.
- **No PII in logs.** Migration and CLI logs reference users by `id`,
  not by email or name.
