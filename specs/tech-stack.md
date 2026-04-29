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
- **Lint / format / type:** ruff (linting and formatting), mypy `--strict`.

## Frontend

- **Language / runtime:** TypeScript (strict), Node 20+, `pnpm` (strictly enforced).
- **Framework / build:** React 18 + Vite.
- **Routing:** TanStack Router.
- **Server state:** TanStack Query.
- **Client state:** Default to none. Introduce Zustand only if a concrete need arises.
- **Styling:** Tailwind CSS.
- **UI primitives / Components:** shadcn/ui (built on Radix UI and Tailwind CSS).
- **Forms / validation:** React Hook Form + Zod.
- **PWA:** `vite-plugin-pwa` (Workbox under the hood). Service worker handles push notifications and an offline app shell.
- **Testing:** Vitest + React Testing Library for unit/component; Playwright for E2E.
- **Lint / format:** ESLint + Prettier.

## Deployment

To maximize free-tier usage while ensuring background tasks (`APScheduler`) remain reliable, the application targets the following infrastructure:

- **Frontend:** Vercel or Cloudflare Pages (Static Site Hosting, no sleep).
- **Backend:** Koyeb Free Tier (Eco Micro Instance, does not sleep, keeping `APScheduler` alive).
- **Database:** Supabase Free Tier (Direct PostgreSQL connection via `asyncpg`, avoiding REST API limitations).

## API contract

- FastAPI emits OpenAPI automatically.
- A TypeScript client is generated from that OpenAPI document via `openapi-typescript` and committed under `frontend/src/api/`.
- The frontend fetches data using `openapi-fetch`, which natively consumes the generated types for 100% type-safe requests.
- Generation runs in CI; a drift between the spec and the committed client fails the build.
- This is the single source of truth that bridges Pydantic and Zod — frontend types are derived, never hand-maintained.

## Tooling & CI

- **Pre-commit hooks:** ruff, mypy, eslint, prettier, `tsc --noEmit`.
- **CI (GitHub Actions):** lint → typecheck → unit tests → integration tests (with a Postgres service container) → E2E (Playwright) → build artifacts. All gates must pass before merge.
- **Local dev:** Docker Compose brings up Postgres, the FastAPI backend, and the Vite dev server.
- **Secrets:** `.env` files locally (git-ignored); CI uses GitHub Actions secrets; production uses environment variables only.

## Scripts & cross-platform policy

Development happens on Windows; deployment runs on Linux. To avoid drift between parallel `.sh` and `.ps1` versions of the same script, scripts in this repo follow these rules:

- **Default to Python** for anything under `scripts/`. Python is already a project dependency, so it's free to use and runs identically on both platforms.
- **Bash is allowed only inside Linux containers** — Dockerfile `RUN` steps and GitHub Actions Linux jobs. It must not be a developer's direct entry point.
- **`justfile` recipes** stay short and shell out to Python scripts for any non-trivial work. The `just` binary is cross-platform; recipe bodies are not.

## Decisions deferred to ADRs

The following will be captured as ADRs under `docs/adr/` when implemented:

- **ADR-0001** — Sessions over JWTs for v1 auth (chosen; rationale to be written).
- **ADR-0002** — In-process APScheduler vs external Celery/Redis for reminders.
- **ADR-0003** — How types cross the FE/BE boundary (chosen: generated from OpenAPI).
- **ADR-0004** — Timer state machines (modeled where, evaluated client-side vs server-side).
