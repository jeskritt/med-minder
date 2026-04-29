# Phase 0 — Foundations: Plan

Numbered task groups. Each group ends with something committable.

## 0. Cross-platform scripting policy

Development happens on Windows; deployment runs on Linux. Anything in
`scripts/` that a developer or CI invokes directly must run unchanged on
both. Two rules:

- **Default to Python** for any non-trivial script. Python is already a
  project dependency (it's the backend language) and works identically on
  both platforms. No dual `.sh` + `.ps1` maintenance burden.
- **Bash is allowed only inside Linux containers** (Dockerfile `RUN`
  steps, GitHub Actions Linux jobs). It must not be a developer's
  expected entry point.
- **`justfile` recipes** stay short and shell out to Python scripts for
  anything beyond a one-liner. `just` itself is cross-platform; recipe
  *bodies* are not. Set `set shell := ["bash", "-cu"]` and document that
  developers on Windows need Git Bash or WSL available (already the case
  here — `just` is the entry point, not raw `.sh` files).

## 1. Repo layout & tooling baseline

1.1 Create `backend/`, `frontend/`, `scripts/` directories with placeholder
    `README.md` files describing their role.
1.2 Add top-level `justfile` with stub targets: `dev`, `test`, `lint`,
    `typecheck`, `migrate`. Each target prints a "not yet wired" message
    until subsequent groups fill them in.
1.3 Add `.editorconfig`.
1.4 **Extend `.gitignore`.** The current file is Python-only (the standard
    GitHub Python template). Append sections for everything Phase 0
    introduces:
    - **Node / Vite / frontend:** `node_modules/`, `frontend/dist/`,
      `frontend/.vite/`, `*.tsbuildinfo`, `.eslintcache`, npm/pnpm/yarn
      debug logs (`npm-debug.log*`, `yarn-debug.log*`, `yarn-error.log*`,
      `pnpm-debug.log*`).
    - **Vitest / Playwright caches** (Playwright not used yet, but its
      patterns are cheap to add now): `coverage/`, `playwright-report/`,
      `test-results/`.
    - **Tooling caches:** `.turbo/`, `.parcel-cache/` (defensive — cheap).
    - **Docker / compose local state:** `*.local`, `.docker/`,
      `docker-compose.override.yml`.
    - **Editor / OS junk:** `.DS_Store`, `Thumbs.db`, `Desktop.ini`,
      `*.swp`, `*.swo`, `.idea/`, `.vscode/` (commented out so users can
      opt in to committing shared settings).
    - **Generated artifacts that are *not* ignored** (committed by
      design): a comment block listing `frontend/src/api/` (OpenAPI
      client) and `pnpm-lock.yaml`, so future contributors don't try to ignore
      them.
    Verify by running `git status` after `just dev` and after running
    tests — only intended files should be untracked.

## 2. Backend skeleton

2.1 `backend/pyproject.toml` with FastAPI, Pydantic v2, uvicorn, ruff, mypy,
    pytest, pytest-asyncio, httpx — all pinned.
2.2 App factory in `backend/src/medminder/app.py` returning a FastAPI
    instance; settings via `pydantic-settings` reading env vars.
2.3 `/healthz` endpoint: returns `{"status": "ok"}`. No DB call, no version,
    no hostname. Unauthenticated by design.
2.4 Unit test: `tests/test_healthz.py` asserts 200 + exact body.
2.5 Wire `just test`, `just lint`, `just typecheck` to the backend.
2.6 `mypy --strict` passes on the whole backend tree.

## 3. Frontend skeleton

3.1 Scaffold `frontend/` with Vite + React 18 + TS strict.
3.2 Install Tailwind CSS, TanStack Router, TanStack Query, React Hook Form,
    Zod, ESLint, Prettier — all pinned.
3.3 Single route `/` rendering "Hello MedMinder" plus a TanStack Query call
    to `/healthz` showing `ok` / `error`.
3.4 Component test (Vitest + RTL) for the home page rendering both states.
3.5 `tsc --noEmit` passes; ESLint + Prettier configured and clean.

## 4. OpenAPI → TypeScript client pipeline

4.1 Script `scripts/generate_openapi_client.py` (Python, cross-platform —
    see §0 Cross-platform scripting policy) that boots the FastAPI app
    in-process, dumps the OpenAPI JSON to a temp file, and shells out to
    `pnpm dlx openapi-typescript` to write `frontend/src/api/`.
4.2 Wire `just generate-client` to invoke that Python script.
4.3 The home page uses the generated client to call `/healthz`, proving the
    end-to-end path works.
4.4 CI drift check: regenerate, then `git diff --exit-code frontend/src/api/`
    fails the build on drift.

## 5. Docker Compose dev environment

5.1 `docker-compose.yml` services: `db` (Postgres 16), `backend` (FastAPI
    via uvicorn with hot reload), `frontend` (Vite dev server).
5.2 Backend reads `DATABASE_URL` from env even though Phase 0 doesn't query
    the DB — this proves config plumbing works for Phase 1.
5.3 `just dev` brings the stack up; `/healthz` reachable from the host;
    home page reachable from the host.
5.4 `.env.example` committed; `.env` git-ignored.

## 6. Pre-commit & CI

6.1 `.pre-commit-config.yaml` with ruff, mypy, eslint, prettier,
    `tsc --noEmit`. All hooks pass on a clean tree.
6.2 `.github/workflows/ci.yml` jobs: `lint`, `typecheck`, `backend-tests`,
    `frontend-tests`, `openapi-drift`. All jobs required to pass.
6.3 No Postgres service container; no Playwright job (deferred — see
    `requirements.md` "Out of scope").

## 7. Docs scaffolding

7.1 `docs/adr/0000-template.md` — ADR template (status, context, decision,
    consequences).
7.2 `docs/diagrams/README.md` — short index naming the three diagram types
    we will accumulate (ER, state, sequence) and pointing to the phases
    that introduce each.
7.3 Top-level `README.md` — quickstart: prerequisites, `just dev`, `just
    test`, link to constitution.
7.4 Generate a secure beginner-level deployment guide (covering Koyeb for backend, Vercel/Cloudflare for frontend, and Supabase for DB) in `docs/deployment.md`.

## 8. Exit-criteria sweep

8.1 Verify all roadmap exit criteria for Phase 0:
    - `mypy --strict` clean, `tsc --noEmit` clean.
    - Unit tests cover `/healthz` and the home page.
    - `docs/diagrams/`, `docs/adr/`, and `docs/deployment.md` exist with the stubs above.
    - No dead code, commented-out code, or unowned TODOs.
    - PR description includes the security note from `requirements.md`
      §"Security considerations for new surface area".
8.2 Open the PR.
