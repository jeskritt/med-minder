# Phase 0 — Foundations: Requirements

## Why this phase

The repository today contains only the constitution (`specs/`), user stories
(`docs/user_stories.md`), `LICENSE`, and `.gitignore`. Before any product
behavior can be built, we need a runnable, typed, tested skeleton with the
repo layout, dev tooling, CI, and dev-environment plumbing described in
`specs/tech-stack.md`. Phase 0 produces that skeleton and nothing more.

## In scope

- Repo layout per `specs/tech-stack.md`: `backend/`, `frontend/`, `scripts/`,
  top-level `docker-compose.yml` and `justfile`.
- Backend: FastAPI app factory, Pydantic settings (env-driven), single
  `/healthz` endpoint returning `{"status": "ok"}` (liveness only).
- Frontend: React 18 + Vite + TypeScript strict, Tailwind configured, single
  "Hello MedMinder" page that fetches `/healthz` and renders the result.
- OpenAPI → TypeScript client generation pipeline, with the generated client
  committed under `frontend/src/api/` and a CI drift check.
- `docker-compose.yml` brings up Postgres 16, the FastAPI backend, and the
  Vite dev server.
- `justfile` with `dev`, `test`, `lint`, `typecheck`, `migrate` targets.
- Pre-commit hooks: ruff, mypy, eslint, prettier, `tsc --noEmit`.
- GitHub Actions CI workflow with real, required gates: lint → typecheck →
  unit tests → OpenAPI client drift check.
- `docs/adr/0000-template.md` (ADR template) and `docs/diagrams/` with
  README stubs for ER, state, and sequence diagrams.
- `docs/deployment.md` with a beginner-friendly deployment guide.

## Out of scope (deferred)

- Database tables, migrations, ORM models — Phase 1.
- `/readyz` or any DB-touching health check — added when reminders/DB-coupled
  features land.
- Auth, sessions, login UI — Phase 3.
- Postgres service container in CI and any integration tests against it —
  Phase 1+ (when there is something to integrate).
- Playwright E2E job — Phase 11 (or first phase with a flow worth E2E-ing).
- PWA configuration (`vite-plugin-pwa`, manifest, service worker) — Phase 9.
- APScheduler, Web Push / VAPID — Phase 8.

## Decisions

| # | Decision | Choice | Notes |
|---|----------|--------|-------|
| D1 | Task runner | `justfile` | Per `tech-stack.md` primary suggestion; user-confirmed. |
| D2 | `/healthz` semantics | Liveness only | Process-up check; no DB ping. `/readyz` deferred. |
| D3 | CI scope this phase | Full skeleton, real gates | Lint, typecheck, unit tests, OpenAPI drift — all required. No Postgres/Playwright yet. |
| D4 | OpenAPI client generator | `openapi-typescript` | Per `tech-stack.md`. Output committed under `frontend/src/api/`. |
| D5 | Python version | 3.12+ | Per `tech-stack.md`. |
| D6 | Node version | 20+ | Per `tech-stack.md`. Pinned via `.nvmrc` or `engines`. |
| D7 | Cross-platform scripting | Python for anything in `scripts/`; bash allowed only inside Linux containers | Dev is on Windows, deploy is Linux. Avoids dual `.sh` + `.ps1` maintenance. `justfile` recipes shell out to Python for non-trivial work. |

## Constraints from the constitution

- Fully typed: `mypy --strict` for Python, `tsc --noEmit` with `strict: true`
  for TypeScript. Both wired into pre-commit and CI.
- Secrets are env-only; `.env` is git-ignored; an `.env.example` is committed.
- New dependencies are pinned (lockfiles committed).
- No dead code, no commented-out code, no TODOs without an issue.
- ADR-0001 (sessions over JWTs) and ADR-0003 (types via OpenAPI) are
  *referenced* by `tech-stack.md` but not authored in Phase 0 — Phase 0 only
  ships the ADR template. The first real ADR is written when the first
  non-obvious decision is made (likely Phase 1 or 3).

## Security considerations for new surface area

- `/healthz` is unauthenticated and intentionally returns no system detail
  beyond a fixed `{"status":"ok"}`. No version strings, no DB info, no
  hostname.
- CORS for the dev frontend origin is permissive in dev only; production
  config defaults to deny-all and is set via env. Documented in
  `backend/README.md`.
- Cookie-related middleware is **not** added in Phase 0 — sessions arrive in
  Phase 3 with their own ADR.
- Dependencies added are pinned in `pyproject.toml` / `pnpm-lock.yaml`
  and reviewed in the PR description.
