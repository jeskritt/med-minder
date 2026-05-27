# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

MedMinder — a single-tenant medication tracker PWA. Backend is FastAPI + SQLAlchemy 2.0 + Postgres; frontend is React 19 + Vite + TanStack Router/Query. Mission, personas, and full tech stack live in `specs/mission.md` and `specs/tech-stack.md`.

## Spec Kit workflow — find the current plan

Work is organised into phases under `specs/<YYYY-MM-DD>-phase-N-<name>/`, each with `requirements.md`, `plan.md`, `validation.md`. The git branch name encodes the current phase.

**Phase artifact conventions.** Phase 0 (Foundations) and Phase 1 (Data Model & Admin CLI) shipped under the project's ad-hoc `specs/_template/` shape: `requirements.md` + numbered-task `plan.md` + `validation.md`. **From Phase 2 onward, phases use spec-kit's strict output set**: filled `plan.md` (spec-kit template format), `research.md`, `data-model.md`, `quickstart.md`, and a `contracts/` directory. Existing Phase 0 / Phase 1 directories are NOT retro-converted; treat them as legacy. When running any `/speckit-*` command, produce its canonical spec-kit artifacts and do not fold them into the legacy triplet.

The constitution at `.specify/memory/constitution.md` is binding. Five principles, with #1 and #5 the easiest to violate accidentally:
- **Security-conscious by default** (NON-NEGOTIABLE).
- **Fully typed** — backend is `mypy --strict`, frontend is `tsc --noEmit` strict.
- **Loose coupling, testable units.**
- **Documented decisions** — non-trivial choices get an ADR under `docs/adr/`.
- **Cross-platform tooling** — dev is Windows, deploy is Linux. Scripts under `scripts/` are Python only; never add a `.sh` and `.ps1` pair.

## Common commands

All cross-cutting commands live in the `justfile`. It uses bash, so on Windows run from Git Bash or WSL.

| Command | What it does |
|---|---|
| `just dev` | `docker compose up --build` — Postgres 17 + backend + frontend |
| `just dev-down` | Stop the stack |
| `just test` | Backend (pytest, coverage ≥85%) + frontend (vitest) |
| `just lint` | ruff + eslint + prettier `--check` |
| `just typecheck` | `mypy --strict` + `tsc --noEmit` |
| `just migrate` / `just migrate-rev "msg"` / `just migrate-down` | Alembic |
| `just generate-client` | Boots FastAPI, dumps OpenAPI, regenerates `frontend/src/api/v1.d.ts` |

Single test (backend): `cd backend && python -m pytest tests/path/to/test_x.py::test_name -v`
Single test (frontend): `cd frontend && pnpm test -- path/to/file.test.tsx -t "name"`

CI gate worth knowing about: `alembic upgrade head` then `alembic check` runs against a fresh Postgres in CI. After editing models, run `just migrate-rev "..."` locally — uncommitted autogen drift fails the build.

## Architecture sketch

**Backend** (`backend/src/medminder/`):
- `app.py` — FastAPI factory (`create_app`), CORS, `/healthz`. Run with `python -m uvicorn medminder.app:create_app --factory --reload --port 8000`.
- `settings.py` — pydantic-settings; reads `DATABASE_URL`, `CORS_ORIGINS`, `ENV`. `database_url_sync` converts the asyncpg URL to psycopg for Alembic.
- `db/` — `DeclarativeBase`, async engine + session factory, one model file per aggregate under `db/models/`. App uses asyncpg; Alembic uses sync psycopg.
- `domain/` — business logic (e.g. `passwords.py` centralises Argon2 + 12-char minimum, reused by CLI and future auth).
- `cli/` — Typer admin CLI (user mgmt, db backup/restore via `pg_dump`/`pg_restore` on PATH).
- `alembic/` — migrations. `alembic.ini` deliberately omits `sqlalchemy.url`; `env.py` reads it from `Settings.database_url_sync`.

**Frontend** (`frontend/src/`):
- File-based routing under `routes/` compiles to `routeTree.gen.ts` (generated, do not edit).
- `lib/api.ts` — `openapi-fetch` client; types in `api/v1.d.ts` are generated from the backend OpenAPI spec (regenerate via `just generate-client`).
- `main.tsx` wires TanStack Router + a React Query `QueryClient` into router context.
- `@/*` path alias → `src/*` (set in both `tsconfig.json` and `vite.config.ts`).
- Vite dev server proxies `/api` → `http://localhost:8000` (strips the `/api` prefix), so the backend must be on 8000.

## Things that have surprised people

- Backend tests run against **real Postgres**, not SQLite. `tests/conftest.py` wraps each test in a rollback and disables prepared-statement caching for Supabase's transaction-mode pooler.
- Production uses two DB roles (migration-runner with DDL, runtime-app with DML only). Don't collapse them in deployment configs.
- `routeTree.gen.ts` and `api/v1.d.ts` are generated. Edits will be overwritten.
- `CORS_ORIGINS` defaults to deny-all in production — set it explicitly when deploying.
- `just` recipes assume bash; on Windows use Git Bash or WSL, not PowerShell.
- **UX-enhancements batch (see ADR-0009):** schedules are shared user-level resources managed via `GET/POST/PUT/DELETE /api/v1/schedules` (PUT edits time/label/days; DELETE detaches attached meds then soft-deletes; the list response carries `medications[]` so the picker can warn before delete). A med save attaches them by id (it no longer creates per-med schedule rows); the form's `SchedulePicker` edits/deletes inline (pen/trash on each chip). Pill-based meds (`pill_strength` + `pills_per_dose`) derive `quantity_per_dose` server-side. `/today` drops the day-of-week filter (rows mute instead), gates off-schedule takes behind a confirm, and **`TodayItem.schedule_id` / `scheduled_time` are nullable** — unscheduled timer meds surface under "As needed" while their timer runs (`domain.timers.is_timer_active`; count_up uses a 24h horizon).
- **`multi_sub_dose` is a rolling per-dose-window concurrency cap (see ADR-0010), not a tiled window.** `times_per_day` = max doses active at once ("max N at a time"); each dose is active for `window_duration_minutes`; exceeding N → `window_full` 409 (body carries `next_available_at`). `max_doses_per_day` is a *separate* optional daily hard cap → `daily_cap_reached` 409. Both are non-overridable overdose guards. `domain.timers._active_at` is the shared source of truth for the card and the guard.
- **Self-service profile editor (see ADR-0011):** clicking your name in the nav bar opens a modal (`ProfileDialog`) that changes your **display name** via `PATCH /me` and **password** via `POST /me/password`. **Email is not editable** in-app — it stays admin/CLI-managed (`PATCH /me` is `extra="forbid"`, so an email/role field is rejected 422). A password change re-auths with the current password (**wrong current password → 403**, distinct from the 422 for a too-short new password, and **never 401**), then **revokes every session and re-issues the current device's cookie** (`domain.users.change_own_password` + `create_session`) — this device stays signed in, **other devices are logged out**. The 12-char minimum lives only in `domain.passwords`. No schema change; forgot-password recovery is still the admin CLI (`user update --password-stdin`).
- **Reminders + snooze (Phase 7, see ADR-0002):** an in-process `AsyncIOScheduler` runs **one recurring "dispatch tick"** (`scheduler.py`, started in the app lifespan, gated by `settings.reminders_enabled` — **off in tests/CI/Alembic**, and ASGITransport doesn't run lifespan so API tests never start it). **Durable state is the `reminders` table, NOT a SQLAlchemyJobStore** (the DML-only runtime role can't run the jobstore's `CREATE TABLE`); the tick generates dose reminders per **schedule slot** (48h horizon, idempotent), dispatches due ones within a **grace window** (older = overdue, shown in-app, never pushed), and **defers around per-user quiet hours** by rewriting `scheduled_for`. Pure time math → `domain/reminders.py` (no DB imports); DB orchestration → `domain/reminder_dispatch.py`; Web Push (VAPID, `pywebpush` run off-thread) → `domain/push.py`. **`refill_count` is the live on-hand count** (decrements on `create_dose`, restores on `void_dose`; warns at `refill_threshold`; the `uq_reminders_open_refill` partial-unique enforces one open warning per med; re-arms when the count is raised back above threshold). Reminders are **also listable in-app** (`GET /api/v1/reminders`); snooze/dismiss are **in-app only** (`/reminders` route) — notification-action snooze is Phase 8. Schedule create/edit/delete and med attach/detach call `regenerate_schedule_reminders` (re-syncs that schedule's **future pending** rows, preserving sent/dismissed history). Quiet hours are **self-service in-app** via `PUT /me/quiet-hours` (the "Quiet hours" section on the `/reminders` page — both-or-neither bounds, equal bounds rejected, both `null` clears them) **and still admin-CLI-settable** (`user update --quiet-hours-start/--quiet-hours-end`); `GET /me` now also exposes `timezone` + `quiet_hours_start/end` (see ADR-0012). **Timezone is self-service** too (see ADR-0013): `PUT /me/timezone` sets the caller's IANA zone, validated against `zoneinfo` server-side (unknown → 422); the profile modal edits it via a searchable `TimezoneCombobox` (substring filter over `Intl.supportedValuesOf("timeZone")`, commits only a valid zone) — still admin-CLI-settable too. New deps: `apscheduler`, `pywebpush`; VAPID keys via `scripts/generate_vapid_keys.py` (private key env-only).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/008-reminders-snooze/plan.md` (Phase 7 — Reminders + Snooze).
<!-- SPECKIT END -->
