# Phase 0 — Foundations: Validation

The phase is mergeable when **every** check below passes on a fresh clone.

## A. Local dev experience

1. `just dev` brings up Postgres, backend, and the Vite dev server with no
   manual steps beyond copying `.env.example` to `.env`.
2. `curl http://localhost:8000/healthz` returns HTTP 200 with body
   `{"status":"ok"}` — exact match, no extra fields.
3. The frontend at `http://localhost:5173` renders "Hello MedMinder" and
   visibly displays the `/healthz` result fetched via the generated client.
4. Stopping `just dev` cleanly tears the stack down.

## B. Type & lint gates

5. `just lint` exits 0 on a clean tree (ruff, eslint,
   prettier --check).
6. `just typecheck` exits 0 (`mypy --strict` over `backend/`, `tsc --noEmit`
   over `frontend/`).
7. Pre-commit, when installed, blocks a commit that introduces a lint or
   type violation. Demonstrate by intentionally adding `x: int = "bad"` in
   a throwaway branch and confirming the hook rejects it.

## C. Tests

8. `just test` runs both backend (pytest) and frontend (vitest) suites; both
   green; no skipped tests without an explicit reason.
9. Backend tests include a `/healthz` test asserting status 200 and exact
   body. Frontend tests include a home-page test covering the success and
   error states of the `/healthz` query.

## D. OpenAPI client pipeline

10. Running `just generate-client` on a clean tree produces no diff under
    `frontend/src/api/`. Verified to run successfully on **both** Windows
    (developer machine) and Linux (CI). The underlying script is Python
    (`scripts/generate_openapi_client.py`), not a `.sh`/`.ps1` pair.
11. Adding a new route to the backend (locally, throwaway) and rerunning
    the generator updates `frontend/src/api/`. Reverting the route and
    regenerating returns the tree to clean.
12. The CI `openapi-drift` job fails when committed `frontend/src/api/`
    is out of sync with the backend's OpenAPI document.

## E. CI

13. The GitHub Actions workflow runs on push and PR with required jobs:
    `lint`, `typecheck`, `backend-tests`, `frontend-tests`, `openapi-drift`.
14. All jobs are green on the Phase 0 PR.
15. No `continue-on-error: true` on any required job.

## F. Security & hygiene

16. `/healthz` response contains only `{"status":"ok"}` — no version, no
    hostname, no dependency info, no DB state.
17. `.env` is git-ignored; `.env.example` is committed and contains no real
    secrets.
17a. After `just dev` and `just test` have run on a fresh clone,
    `git status` reports a clean tree — no `node_modules/`, `dist/`,
    `coverage/`, `.vite/`, `*.tsbuildinfo`, `.DS_Store`, or other
    generated/OS files appear as untracked. The `.gitignore` covers
    Node, Vite, test/coverage output, Docker overrides, and OS junk in
    addition to the Python patterns it already had.
18. Every dependency added in Phase 0 is pinned (lockfiles committed for
    both backend and frontend).
19. No `TODO`/`FIXME` comments without a linked issue.
20. PR description contains a "Security considerations" section listing the
    new surface area (`/healthz`, dev CORS config) and the deliberate
    decisions about each (per `requirements.md`).

## G. Docs

21. `docs/adr/0000-template.md` exists and is referenced from the top-level
    `README.md`.
22. `docs/diagrams/README.md` exists and names the three diagram types
    that will accumulate (ER, state, sequence).
23. `docs/deployment.md` exists and contains the beginner-friendly deployment guide.
24. Top-level `README.md` documents prerequisites, `just dev`, `just test`,
    and links to `specs/mission.md`, `specs/roadmap.md`, and
    `specs/tech-stack.md`.

## H. Cross-platform sanity

25. Every script under `scripts/` is `.py`. There are no `.sh` or `.ps1`
    files developers are expected to invoke directly. (Bash inside
    Dockerfiles or GitHub Actions Linux jobs is fine and does not count.)
26. `just dev`, `just test`, `just lint`, `just typecheck`, and
    `just generate-client` all complete successfully on Windows
    (developer machine) and on Linux (CI), with no platform-specific
    branches in the recipe bodies.

When A–H all pass, Phase 0 is done and the PR can merge.
