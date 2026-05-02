# Phase 1 — Data Model & Admin CLI: Plan

Numbered task groups. Each group ends with something committable.
Sub-phase 1a is the data layer; sub-phase 1b is the CLI on top of it.

## 0. Dependencies & Postgres in CI

[x] 0.1 Add to `backend/pyproject.toml`, all version-pinned with upper bounds:
    `sqlalchemy`, `alembic`, `psycopg[binary]` (sync, used by Alembic),
    `asyncpg` (async, used by the app), `argon2-cffi`, `typer`,
    `pytest-cov`. Update `pnpm-lock` is N/A (backend-only changes).
[x] 0.2 Add `pytest-cov` config to `backend/pyproject.toml`:
    `--cov=medminder --cov-report=term-missing --cov-fail-under=85`.
    The threshold is intentionally not 100 — Phase 1 is models + a
    thin CLI; coverage is meaningful at this level.
[x] 0.3 Extend `.github/workflows/ci.yml` with a Postgres 16 service
    container on the `backend-tests` job. Wire `DATABASE_URL` to the
    service. Phase 0 deferred this; Phase 1 owns it.
[x] 0.4 Add a CI gate that runs `alembic upgrade head` against a fresh DB
    and then `alembic check` — fails on uncommitted autogen changes.

## 1a — Data model & migrations

### 1a.1 SQLAlchemy setup
[x] 1a.1.1 Create `backend/src/medminder/db/__init__.py` exposing
       `Base`, an async `engine` factory, and an
       `async_session_factory`. Use the SQLAlchemy 2.0 typed
       `DeclarativeBase` style.
[x] 1a.1.2 Settings (`pydantic-settings`) gain `DATABASE_URL` (already
       wired in Phase 0 as a passthrough); add `DATABASE_URL_SYNC`
       derived from it for Alembic.

### [x] 1a.2 Models
One file per aggregate under `backend/src/medminder/db/models/`:
`users.py`, `sessions.py`, `push_subscriptions.py`, `medications.py`,
`medication_interactions.py`, `schedules.py`, `schedule_medications.py`,
`doses.py`, `reminders.py`. All fields and constraints exactly per
`requirements.md` "Data schema". Highlights:
- Functional UNIQUE index on `LOWER(users.email)` (D8) declared via
  `Index("ix_users_email_lower", func.lower(email), unique=True)`.
- Bitmask check on `schedules.days_of_week` (D2).
- Two-FK + CHECK shape on `reminders` (D3).
- `medications.deleted_at` and a `MedicationsActive` selectable view
  for default queries (D6).
- `medication_interactions` UNIQUE on the *unordered* pair via an
  expression index using `LEAST`/`GREATEST` (D5).
- `doses.user_id` with a CHECK trigger asserting it equals
  `medications.user_id` (D4) — implemented as a Postgres trigger in
  the migration, not in Python.

### 1a.3 Alembic baseline
[x] 1a.3.1 `alembic init` under `backend/alembic/`; configure `env.py` to
       import `Base.metadata` and read the URL from settings.
[x] 1a.3.2 `alembic revision --autogenerate -m "phase 1 baseline"`.
       Hand-edit the migration to add the bits autogen misses:
       expression UNIQUE indexes, `LOWER(email)` index, the
       cross-user-id trigger on `doses`.
[x] 1a.3.3 Wire `just migrate` to `alembic upgrade head` (replace the
       Phase 0 stub).

### [x] 1a.4 Tests
For every model, a `tests/db/test_<model>.py` covering:
- Insert with all required fields succeeds.
- Each NOT NULL column rejects `None`.
- Each UNIQUE / functional UNIQUE rejects duplicates (including the
  email-case-insensitive case).
- Each CHECK constraint rejects out-of-range values.
- FK ON DELETE behavior (CASCADE vs RESTRICT) matches the spec.
- The `reminders` CHECK rejects illegal `(type, *_id)` combos.
- The `doses.user_id == medications.user_id` trigger fires on mismatch.
- Soft-delete semantics: a deleted user's medications and schedules
  are still readable via the explicit "include deleted" path.

### 1a.5 ER diagram
[x] 1a.5.1 Author `docs/diagrams/er.md` as a Mermaid `erDiagram`. It must
       reflect every column and relationship in the committed
       migration. The plan-validation step diffs this against
       autogen output to keep it honest.

## 1b — Admin CLI

### 1b.1 CLI scaffolding
[x] 1b.1.1 Create `backend/src/medminder/cli/__init__.py` and
       `backend/src/medminder/cli/main.py` exposing a Typer app.
[x] 1b.1.2 Add a `[project.scripts]` entry in `pyproject.toml`:
       `medminder-admin = "medminder.cli.main:app"`.
[x] 1b.1.3 The CLI uses the same settings module as the web app so
       `DATABASE_URL` is the single source of truth.

### 1b.2 Domain module (shared with future auth)
[x] 1b.2.1 `backend/src/medminder/domain/users.py` exports:
       `create_user`, `update_user`, `soft_delete_user`, `list_users`,
       `get_user_by_email`, `verify_password`, `hash_password`. All
       async, all take an `AsyncSession`.
[x] 1b.2.2 Argon2id parameters live here as module-level constants so
       that future auth code reuses them verbatim. `verify_password`
       uses `argon2-cffi`'s `PasswordHasher.verify` which handles
       constant-time comparison and detects rehash needs.
[x] 1b.2.3 Email is normalized to lowercase before lookup. Display
       casing is preserved.

### 1b.3 User commands
[x] 1b.3.1 `user add` — required `--email`, `--name`, `--role`; optional
       `--password-stdin` (default) reads exactly one line from stdin.
       Reject passwords shorter than 12 chars. Print only the new
       user's `id` on success.
[x] 1b.3.2 `user delete --email` — soft delete (sets `deleted_at`).
       Refuses to hard-delete in v1. Prints the affected user `id`.
[x] 1b.3.3 `user update --email` with optional `--password-stdin`,
       `--new-email`, `--name`, `--role`. At least one mutating flag
       required.
[x] 1b.3.4 `user list [--role] [--include-deleted]` — table output;
       columns: `id, email, name, role, created_at, deleted_at`.

### 1b.4 Backup / restore commands
[x] 1b.4.1 `db backup --out <path>` — shells out to `pg_dump
       --format=custom --file=<path>` against `DATABASE_URL`. After
       the dump succeeds, `chmod 0600 <path>` (Unix only — print a
       warning on Windows reminding the operator to ACL the file).
       Stdout: a sentence reminding the operator the file contains
       all password hashes and medication records, treat as PHI.
[x] 1b.4.2 `db restore --in <path>` — refuses to run without `--yes`,
       runs `pg_restore --clean --if-exists` against `DATABASE_URL`.
       Aborts if the target DB has non-Alembic tables and `--yes` was
       not given.
[x] 1b.4.3 Both commands respect `DATABASE_URL` only; no flag for
       host/port/user/pass — keeps connection-string secrets out of
       process listings.

### 1b.5 Tests
[x] 1b.5.1 Integration tests under `backend/tests/cli/` use the same
       Postgres service container as 1a tests. A `cli_runner` fixture
       wraps Typer's `CliRunner`.
[x] 1b.5.2 Cover: create / list / update (each field) / delete /
       password verification round-trip / case-insensitive email
       lookup / duplicate email rejection / role enum rejection /
       short-password rejection / missing-user error messages.
[x] 1b.5.3 Backup/restore tests run against an ephemeral schema:
       seed → backup → drop → restore → assert counts and
       Argon2id-verifiable passwords still work.

## 2. Documentation

[x] 2.1 Update `docs/deployment.md`:
    - Run `alembic upgrade head` on backend boot (release command on
      Koyeb).
    - First admin user is created via `medminder-admin user add` from
      a one-shot Koyeb job after the first deploy.
    - Backup/restore via `medminder-admin db backup|restore`.
[x] 2.2 Update `backend/README.md` to document:
    - `medminder-admin --help`.
    - The Argon2id parameter constants module.
    - The dual roles for migration vs runtime DB users.
[x] 2.3 Add ADR-0001 (sessions over JWTs — chosen) since Phase 1 commits
    to the `sessions` table shape; deferred wire-up is Phase 2 but the
    *decision* is made now.

## 3. Exit-criteria sweep

[x] 3.1 All exit criteria from `roadmap.md` for Phase 1:
    - `mypy --strict` clean across new code.
    - Coverage gate passing at ≥ 85%.
    - ER diagram present and matches the committed migration.
    - Security note in the PR description per `requirements.md`
      §"Security considerations for new surface area".
    - No dead code, no commented-out code, no TODO without an issue.
[x] 3.2 Phase 1 PR description summarizes the data-model decisions
    (D1–D12) so reviewers can challenge them in one place.
