## What this project is

MedMinder — a single-tenant medication tracker PWA. Backend is FastAPI + SQLAlchemy 2.0 + Postgres; frontend is React 19 + Vite + TanStack Router/Query. Mission, personas, and full tech stack live in `specs/mission.md` and `specs/tech-stack.md`.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/003-medications-crud/plan.md
<!-- SPECKIT END -->

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


## Engineering principles

These are binding rules, not aspirations.

- **Security-conscious by default** — MedMinder stores personal medication records. Treat that data with the same care as protected health information: encrypt in transit, minimize what is collected and logged, prefer revocable session-based auth over long-lived tokens, hash credentials with Argon2id, keep secrets out of the repo, and apply least privilege to database roles and deployment credentials. When security and convenience conflict, security wins. New surface area (endpoints, fields, dependencies, third-party calls) requires an explicit threat consideration in the relevant ADR or PR description.
- **SOLID, KISS, DRY, YAGNI** — applied at function, module, and service boundaries.
- **Fully typed** — Python with `mypy --strict`; TypeScript with `strict: true`.
- **Small units** — reasonably sized functions and files; no deeply nested code or conditional logic; no deeply nested data models.
- **Loose coupling** — clear seams between domain logic, persistence, transport, and UI. Domain logic must be testable without a database or HTTP server.
- **Minimal duplication** — one source of truth for each concept; in particular, no parallel hand-maintained code/data models on the frontend and backend.
- **No dead code** — unused code is deleted, not commented out.
- **Easily testable** — pure functions where possible; dependency-injected I/O.
- **Documented** — `docs/` carries ADRs for non-obvious decisions, ER diagrams for the data model, state diagrams for timer/reminder logic, sequence diagrams for key user flows, and the user stories themselves.
