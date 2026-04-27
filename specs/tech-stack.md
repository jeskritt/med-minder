# MedMinder — Tech Stack

This document is the authoritative list of technologies and tools used by MedMinder. Deviations require an ADR in `docs/adr/`.

## Repository layout

Monorepo, single git repository.

```
med-minder/
├── backend/         # FastAPI service + admin CLI
├── frontend/        # React + Vite PWA
├── specs/           # Constitution: mission, tech stack, roadmap
├── docs/            # User stories, ADRs, ER/state/sequence diagrams
├── scripts/         # Dev/CI helper scripts
├── docker-compose.yml
└── justfile         # Common dev commands
```

A top-level `justfile` (or `Makefile`) provides single-word commands for common workflows: `just dev`, `just test`, `just lint`, `just typecheck`, `just migrate`.

## Backend

- **Language / runtime:** Python 3.12+.
- **Web framework:** FastAPI.
- **Validation / schemas:** Pydantic v2, strict mode.
- **ORM / migrations:** SQLAlchemy 2.0 (typed style) + Alembic.
- **Database:** PostgreSQL 16 (run via Docker for local dev).
- **Authentication:** Server-side sessions backed by signed, HTTP-only cookies. Password hashing with Argon2id via `argon2-cffi`. No JWTs in v1.
- **Admin CLI:** Typer; same domain layer as the web app, no duplicated logic.
- **Reminders & push:** Web Push (VAPID) via `pywebpush`. Background scheduling via APScheduler running in-process for v1. Switching to Celery + Redis is a deferred decision (see ADR-0002 placeholder).
- **Testing:** pytest, pytest-asyncio, httpx test client, factory-boy (or simple fixtures). Coverage gate enforced in CI.
- **Lint / format / type:** ruff, black, mypy `--strict`.

## Frontend

- **Language / runtime:** TypeScript (strict), Node 20+.
- **Framework / build:** React 18 + Vite.
- **Routing:** React Router.
- **Server state:** TanStack Query.
- **Client state:** Default to none. Introduce Zustand only if a concrete need arises.
- **Styling:** Tailwind CSS.
- **UI primitives:** Radix UI for accessible primitives (dialog, dropdown, etc.).
- **Forms / validation:** React Hook Form + Zod.
- **PWA:** `vite-plugin-pwa` (Workbox under the hood). Service worker handles push notifications and an offline app shell.
- **Testing:** Vitest + React Testing Library for unit/component; Playwright for E2E.
- **Lint / format:** ESLint + Prettier.

## API contract

- FastAPI emits OpenAPI automatically.
- A TypeScript client is generated from that OpenAPI document via `openapi-typescript` (or equivalent) and committed under `frontend/src/api/`.
- Generation runs in CI; a drift between the spec and the committed client fails the build.
- This is the single source of truth that bridges Pydantic and Zod — frontend types are derived, never hand-maintained.

## Tooling & CI

- **Pre-commit hooks:** ruff, black, mypy, eslint, prettier, `tsc --noEmit`.
- **CI (GitHub Actions):** lint → typecheck → unit tests → integration tests (with a Postgres service container) → E2E (Playwright) → build artifacts. All gates must pass before merge.
- **Local dev:** Docker Compose brings up Postgres, the FastAPI backend, and the Vite dev server.
- **Secrets:** `.env` files locally (git-ignored); CI uses GitHub Actions secrets; production uses environment variables only.

## Decisions deferred to ADRs

The following will be captured as ADRs under `docs/adr/` when implemented:

- **ADR-0001** — Sessions over JWTs for v1 auth (chosen; rationale to be written).
- **ADR-0002** — In-process APScheduler vs external Celery/Redis for reminders.
- **ADR-0003** — How types cross the FE/BE boundary (chosen: generated from OpenAPI).
- **ADR-0004** — Timer state machines (modeled where, evaluated client-side vs server-side).
