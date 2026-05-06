# MedMinder — Tech Stack

This document is the authoritative list of technologies and tools used by MedMinder. Deviations require an ADR in `docs/adr/`.

## Repository layout

Monorepo, single git repository.

```
med-minder/
├── backend/               # FastAPI service + admin CLI
├── frontend/              # React + Vite PWA
├── specs/                 # Constitution: mission, tech stack, roadmap, phase specs
│   └── _template/         # Skeleton for new phase specs
├── docs/                  # User stories, ADRs, design notes, diagrams, deployment guide
│   ├── adr/
│   ├── design/
│   └── diagrams/
├── scripts/               # Dev/CI helper scripts (Python only)
├── .github/workflows/     # CI definitions
├── .pre-commit-config.yaml
├── .editorconfig
├── docker-compose.yml
├── justfile               # Common dev commands
├── README.md
├── SECURITY.md
└── LICENSE
```

A top-level `justfile` provides single-word commands for common workflows: `just dev`, `just test`, `just lint`, `just typecheck`, `just migrate`, `just generate-client`.

## Backend

- **Language / runtime:** Python 3.12+.
- **Web framework:** FastAPI.
- **Validation / schemas:** Pydantic v2, strict mode.
- **ORM / migrations:** SQLAlchemy 2.0 (typed `Mapped[...]` style) + Alembic.
- **Database:** PostgreSQL 17 (run via Docker for local dev).
- **Authentication:** Database-backed server-side sessions with signed, HTTP-only cookies. Password hashing with Argon2id via `argon2-cffi`. Session token hashing with SHA-256 (random tokens are high-entropy; no KDF needed). No JWTs in v1 — see ADR-0001.
- **Admin CLI:** Typer (`medminder-admin`); same domain layer as the web app, no duplicated logic. Includes `db backup|restore` wrappers around `pg_dump`/`pg_restore`. Lands in Phase 1b.
- **Reminders & push:** Web Push (VAPID) via `pywebpush`. Background scheduling via APScheduler running in-process — see ADR-0002.
- **Testing:** pytest, pytest-asyncio, pytest-cov, httpx test client. Coverage gate enforced in CI from Phase 1 onward. Tests run against a real Postgres service container, not SQLite.
- **Lint / format / type:** ruff (linting and formatting), mypy `--strict`.

## Frontend

- **Language / runtime:** TypeScript (strict), Node 20+, `pnpm` (strictly enforced).
- **Framework / build:** React 18 + Vite.
- **Routing:** TanStack Router.
- **Server state:** TanStack Query.
- **Client state:** Default to none. Introduce Zustand only if a concrete need arises.
- **Styling:** Tailwind CSS.
- **UI primitives / Components:** shadcn/ui (built on Radix UI and Tailwind CSS).
- **Forms / validation:** React Hook Form + Zod (Zod for runtime form validation only — wire-format types are generated, not hand-maintained; see ADR-0003).
- **PWA:** `vite-plugin-pwa` (Workbox under the hood). Service worker handles push notifications and an offline app shell.
- **Testing:** Vitest + React Testing Library for unit/component; Playwright for E2E. The first smoke E2E lands in Phase 4 (mark-as-taken); the full persona suite in Phase 10.
- **Lint / format:** ESLint + Prettier.

## Deployment

To maximize free-tier usage while ensuring background tasks (`APScheduler`) remain reliable, the application targets the following infrastructure:

- **Frontend:** Vercel or Cloudflare Pages (Static Site Hosting, no sleep).
- **Backend:** Koyeb Free Tier (Eco Micro Instance, does not sleep, keeping `APScheduler` alive).
- **Database:** Supabase Free Tier (Direct PostgreSQL connection via `asyncpg`, avoiding REST API limitations).

Database backups and the first-admin bootstrap are done via the
Phase 1b admin CLI, not via Supabase's UI. See `docs/deployment.md`.

## API contract

- FastAPI emits OpenAPI automatically.
- A TypeScript client is generated from that OpenAPI document via `openapi-typescript` and committed under `frontend/src/api/`.
- The frontend fetches data using `openapi-fetch`, which natively consumes the generated types for 100% type-safe requests.
- Generation runs in CI; a drift between the spec and the committed client fails the build.
- This is the single source of truth that bridges Pydantic and Zod — frontend wire-format types are derived, never hand-maintained. See ADR-0003.

## Tooling & CI

- **Pre-commit hooks:** ruff, mypy, eslint, prettier, `tsc --noEmit`.
- **CI (GitHub Actions):** lint → typecheck → unit tests → integration tests (with a Postgres service container, from Phase 1) → E2E (Playwright, from Phase 4) → build artifacts. All gates must pass before merge.
- **Local dev:** Docker Compose brings up Postgres, the FastAPI backend, and the Vite dev server.
- **Secrets:** `.env` files locally (git-ignored); CI uses GitHub Actions secrets; production uses environment variables only.

## Scripts & cross-platform policy

Development happens on Windows; deployment runs on Linux. To avoid drift between parallel `.sh` and `.ps1` versions of the same script, scripts in this repo follow these rules:

- **Default to Python** for anything under `scripts/`. Python is already a project dependency, so it's free to use and runs identically on both platforms.
- **Bash is allowed only inside Linux containers** — Dockerfile `RUN` steps and GitHub Actions Linux jobs. It must not be a developer's direct entry point.
- **`justfile` recipes** stay short and shell out to Python scripts for any non-trivial work. The `just` binary is cross-platform; recipe bodies are not. The justfile sets `set shell := ["bash", "-cu"]`, which means Windows developers need **Git Bash or WSL** available — this is a documented prerequisite in `README.md`.

## Architectural decisions

The non-obvious choices live as ADRs under `docs/adr/`:

- **ADR-0001** — Server-side sessions over JWTs for v1 auth. Status: Proposed, accepted in Phase 2.
- **ADR-0002** — In-process APScheduler over Celery + Redis for v1 reminders. Status: Proposed, accepted in Phase 7.
- **ADR-0003** — Types cross the FE/BE boundary via generated OpenAPI client. Status: Accepted (implemented in Phase 0).
- **ADR-0004** — Timer state machines: modeled where and evaluated when. Status: Proposed, accepted in Phase 5a.
