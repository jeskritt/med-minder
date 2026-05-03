# Implementation Plan: Phase 2 — Auth (login / logout)

**Branch**: `phase-2-auth` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/2026-05-02-phase-2-auth/spec.md`

## Summary

Phase 2 wires the user-provisioning work delivered in Phase 1 into a usable login surface. It introduces a `POST /auth/login` endpoint that issues a signed, HTTP-only session cookie backed by a row in the existing `sessions` table, a `POST /auth/logout` endpoint that deletes that row, a `GET /me` endpoint that exercises the auth dependency from a real protected route, frontend `/login` and stub `/medications` routes, and the CLI hooks that revoke all of a user's sessions when an admin changes their password or soft-deletes them.

The technical approach reuses every piece of the Phase 1 domain layer — `medminder.domain.users.get_user_by_email` for lookup, `medminder.domain.passwords.verify_password` for comparison, the existing `sessions` table and its SHA-256 `token_hash` index — and adds two new domain modules (`domain.sessions`, `domain.auth`), a small HTTP layer under `api/`, and the frontend route guard. Cookies are signed with `itsdangerous`; rolling 30-day expiry is implemented by mutating `sessions.expires_at` in place (no schema change). Failure paths (wrong password, unknown email, soft-deleted user) all run an Argon2id verification against a module-level dummy hash so response timing is uniform.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x with React 19 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (asyncpg), pydantic v2, argon2-cffi, **new: itsdangerous ≥2.2,<3.0**; TanStack Router + TanStack Query, openapi-fetch, react-hook-form, zod
**Storage**: PostgreSQL 17 (existing). The `users` and `sessions` tables introduced in Phase 1 are sufficient — Phase 2 introduces no new tables, columns, or indexes; no Alembic migration is anticipated.
**Testing**: pytest + pytest-asyncio against a real Postgres service container (existing rollback-per-test fixture in `backend/tests/conftest.py`); httpx + ASGITransport for HTTP-level tests; **new dev dep: freezegun ≥1.5,<2.0** for clock advancement (rolling-expiry tests). Frontend: vitest + @testing-library/react + jsdom.
**Target Platform**: Linux containers in production (Koyeb); developer machines run Windows + Docker Desktop. Both `mypy --strict` and `tsc --noEmit` strict gates apply.
**Project Type**: Web application — separate backend (FastAPI) and frontend (Vite/React) under `backend/` and `frontend/`.
**Performance Goals**: SC-001 — login round-trip under 2 s on a typical home connection. SC-002 — wall-clock p95 timing delta across {wrong-password, unknown-email, soft-deleted} login outcomes ≤ 50 ms over 100 trials.
**Constraints**: Constitution Principle I (security non-negotiable). Cookie signed; SHA-256 token hash never logged; emails never logged; Argon2id verification on every login attempt — including the "no such user" path — to defeat user-enumeration. SameSite=Lax is the only CSRF defense in this phase; explicit CSRF tokens, rate limiting, and account lockout are deferred to Phase 10 per spec assumptions.
**Scale/Scope**: Single-tenant; admin-provisioned user base (low tens to low hundreds of users); unbounded concurrent sessions per user; ≤ ~10 RPS per user under realistic use.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Security-Conscious by Default** — Phase 2 introduces new surface area: `POST /auth/login`, `POST /auth/logout`, `GET /me`, a signed session cookie, a structured login-attempt log line (FR-019), the `itsdangerous` dependency, and a `SESSION_SECRET` setting. Each is justified in the PR's Security considerations section. Argon2id is reused via `medminder.domain.passwords.verify_password` (FR-013) — no parallel hashing; SHA-256 over high-entropy random tokens per ADR-0001 D9b; least-privilege DB roles (migration vs runtime) preserved unchanged. **PASS.**
- **II. Fully Typed Across the Stack** — All new backend code is `mypy --strict` clean; pydantic request/response models run in strict mode; frontend code passes `tsc --noEmit` strict; the OpenAPI client at `frontend/src/api/v1.d.ts` is regenerated and committed when the API surface changes (CI gate enforces drift). **PASS.**
- **III. Loose Coupling, Testable Units** — `domain/sessions.py` and `domain/auth.py` are testable without an HTTP server (only an `AsyncSession` is needed). The CLI revocation hooks call the same `revoke_all_user_sessions` helper the future "log out everywhere" UI would; no logic is duplicated between CLI and HTTP transports. **PASS.**
- **IV. Documented Decisions** — No new ADR is required: ADR-0001 already commits to server-side sessions over JWTs and to SHA-256 token hashing; the Phase 2 decisions D1–D12 sit inside that envelope and are recorded in `research.md`. A new sequence diagram lands at `docs/diagrams/login-sequence.md` (FR-015, SC-007). The phase ships the strict spec-kit output set (`plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`). **PASS, with a note**: this is the first phase to use the strict spec-kit output instead of the project's legacy `requirements.md`+`validation.md` triplet — a deliberate convention switch recorded in `CLAUDE.md`. The constitution still enumerates the legacy triplet under Principle IV; updating that wording is out of scope for this PR.
- **V. Cross-Platform Tooling Integrity** — New dependencies pinned with upper bounds (`itsdangerous>=2.2.0,<3.0`, `freezegun>=1.5.0,<2.0`); no shell scripts added; CI gates unchanged (lint → typecheck → tests → OpenAPI drift → build). No `continue-on-error: true` is introduced. `pip-audit` continues to gate on every PR. **PASS.**

No "Complexity Tracking" entries.

## Project Structure

### Documentation (this feature)

```text
specs/2026-05-02-phase-2-auth/
├── spec.md              # /speckit-specify output (clarified)
├── plan.md              # this file
├── research.md          # Phase 0 — D1–D12 with Decision/Rationale/Alternatives
├── data-model.md        # Phase 1 — entities Phase 2 touches (no schema change)
├── quickstart.md        # Phase 1 — minimal end-to-end flow
├── contracts/
│   └── auth.openapi.yaml   # OpenAPI 3.1 fragment for /auth/login, /auth/logout, /me
└── checklists/
    └── requirements.md     # /speckit-checklist (already present)
```

### Source Code (repository root)

```text
backend/
├── src/medminder/
│   ├── api/                          # NEW (Phase 2)
│   │   ├── __init__.py
│   │   ├── deps.py                   # get_session, get_current_user
│   │   ├── auth.py                   # POST /auth/login, POST /auth/logout
│   │   └── me.py                     # GET /me
│   ├── domain/
│   │   ├── users.py                  # existing (Phase 1) — reused via FR-014
│   │   ├── passwords.py              # existing (Phase 1) — reused via FR-013 + dummy hash for D5
│   │   ├── sessions.py               # NEW — token mint/hash, create/authenticate/revoke
│   │   └── auth.py                   # NEW — login orchestration + structured logging (FR-019)
│   ├── db/
│   │   ├── __init__.py               # existing — async engine, session_scope
│   │   └── models/sessions.py        # existing (Phase 1) — no change
│   ├── cli/
│   │   └── users.py                  # MODIFY — wire revoke_all_user_sessions into update/delete
│   ├── settings.py                   # MODIFY — SESSION_SECRET, SESSION_COOKIE_NAME, derived secure flag
│   └── app.py                        # MODIFY — include_router(auth) and include_router(me)
└── tests/
    ├── api/                          # NEW
    │   ├── test_login.py
    │   ├── test_logout.py
    │   ├── test_me.py
    │   └── test_rolling_expiry.py    # uses freezegun
    ├── domain/
    │   ├── test_sessions.py          # NEW
    │   └── test_auth.py              # NEW
    └── cli/
        └── test_user_commands.py     # MODIFY — assert sessions revoked on update/delete

frontend/
├── src/
│   ├── api/v1.d.ts                   # REGENERATED via just generate-client
│   ├── lib/
│   │   ├── api.ts                    # MODIFY — credentials: "include" + 401 middleware
│   │   └── auth.ts                   # NEW — useCurrentUser, useLogout
│   └── routes/
│       ├── login.tsx                 # NEW
│       └── medications.tsx           # NEW (Phase 2 stub; Phase 3 enriches the same route)
└── src/__tests__/
    ├── login.test.tsx                # NEW
    └── medications.guard.test.tsx    # NEW

docs/
└── diagrams/
    └── login-sequence.md             # NEW (Mermaid sequenceDiagram; FR-015, SC-007)
```

**Structure Decision**: Web application (existing `backend/` + `frontend/` split). Phase 2 introduces a new `backend/src/medminder/api/` package — the first HTTP-handler code in the project beyond the `/healthz` stub in `app.py`. Subsequent phases add their routers to the same package.

## Phased breakdown (numbered task groups)

This breakdown supplements the strict-speckit `plan.md` template above; `/speckit-tasks` will derive ordered tasks from it.

```text
0. Prerequisites & dependencies
   0.1 Add itsdangerous>=2.2.0,<3.0 to backend/pyproject.toml [project.dependencies]
   0.2 Add freezegun>=1.5.0,<2.0 to backend/pyproject.toml [project.optional-dependencies] dev
   0.3 Extend backend/src/medminder/settings.py:
       - SESSION_SECRET: str (required when env != "development"; documented dev-only fallback)
       - SESSION_COOKIE_NAME: str = "mm_session"
       - session_cookie_secure property derived from env

1. Backend domain layer
   1.1 backend/src/medminder/domain/sessions.py
       - Constants: SESSION_LIFETIME = timedelta(days=30)
       - generate_token() -> str (secrets.token_urlsafe(32))
       - hash_token(plaintext: str) -> str (SHA-256 hex)
       - async create_session(session, user_id) -> tuple[Session, str]   # returns row + plaintext
       - async authenticate_token(session, plaintext_token) -> User | None
                # SELECT by token_hash, check expiry, mutate expires_at, return User
       - async delete_session_by_token_hash(session, token_hash) -> bool
       - async revoke_all_user_sessions(session, user_id) -> int
   1.2 backend/src/medminder/domain/auth.py
       - LoginOutcome enum: success | wrong_password | unknown_email | soft_deleted
       - DUMMY_HASH = a fixed Argon2id hash (module constant), used to keep timing uniform
       - async attempt_login(session, *, email, password, ip, user_agent) -> tuple[User | None, LoginOutcome]
       - emits exactly one INFO log line via medminder.logging with outcome / user_id (or None) / ip / ua
   1.3 Unit tests (backend/tests/domain/test_sessions.py, test_auth.py)

2. Backend HTTP layer
   2.1 backend/src/medminder/api/deps.py
       - get_session() async generator (yields AsyncSession bound to app.state.session_factory)
       - get_current_user(request, response, session=Depends(...)) -> User
            * reads cookie; itsdangerous.URLSafeTimedSerializer.loads(...)
            * calls authenticate_token; raises HTTPException(401) on miss/expired/tampered
            * refreshes Set-Cookie Max-Age on the outgoing response (FR-003, FR-009)
   2.2 backend/src/medminder/api/auth.py
       - POST /auth/login — body {email, password}; on success deletes any pre-existing session keyed by
         the inbound cookie (FR-016), creates new session, sets signed cookie, returns 204 No Content
       - POST /auth/logout — deletes session by token hash, clears cookie (HTTP-only Set-Cookie with
         Max-Age=0), idempotent, returns 204
   2.3 backend/src/medminder/api/me.py
       - GET /me — depends on get_current_user; returns {id, name, role}
   2.4 Wire app.py to register the routers
   2.5 Integration tests under backend/tests/api/:
       - login: success / wrong-password / unknown-email / soft-deleted (assert identical body & status;
         assert wall-clock delta < 50 ms over 50 paired trials with the real Argon2id verifier)
       - logout: idempotent under double invocation
       - /me: 401 with no / tampered / expired cookie; 200 with valid cookie returns expected payload
       - FR-016: pre-existing session row is deleted when a new login is submitted with the cookie present
       - rolling expiry under freezegun: at +29d the request succeeds AND expires_at advances; at +31d
         the request 401s and the row is left untouched
       - log-line shape: caplog assertion that no email, password, or token material appears

3. CLI revocation hooks (FR-010, FR-011)
   3.1 cli/users.py::delete — after soft_delete_user, call revoke_all_user_sessions in the same txn
   3.2 cli/users.py::update — when new_password is not None, call revoke_all_user_sessions after the
       update_user call inside the same txn
   3.3 Extend backend/tests/cli/test_user_commands.py:
       - seed user with two sessions; user delete; assert 0 sessions remain
       - seed user with two sessions; user update --password-stdin; assert 0 sessions remain
       - seed user with two sessions; user update --name only; assert 2 sessions remain (no revocation)

4. OpenAPI client regen
   4.1 just generate-client — regenerate frontend/src/api/v1.d.ts with the new endpoints
   4.2 Verify the alembic-check CI gate stays green (no schema change)
   4.3 Verify the OpenAPI-drift CI gate stays green after commit

5. Frontend
   5.1 frontend/src/lib/api.ts
       - credentials: "include" on the openapi-fetch client
       - middleware that, on a 401 response from any non-/auth endpoint, calls
         queryClient.clear() and router.navigate({ to: "/login" })
   5.2 frontend/src/routes/login.tsx
       - react-hook-form + zod schema (email, password); generic error rendering for FR-004
       - on success: queryClient.invalidateQueries(["me"]) then navigate({ to: "/medications" })
   5.3 frontend/src/routes/medications.tsx
       - beforeLoad: await fetch /me; on 401 throw redirect({ to: "/login" })
       - placeholder body indicating Phase 3 will populate it
       - logout button calling POST /auth/logout, then queryClient.clear() + navigate to /login
   5.4 frontend/src/lib/auth.ts
       - useCurrentUser() — TanStack Query around GET /me
       - useLogout()      — TanStack Query mutation around POST /auth/logout
   5.5 Vitest coverage:
       - login form renders, validates, submits, navigates on success, shows generic error on 401
       - medications route guard redirects unauthenticated visitors to /login

6. Documentation
   6.1 docs/diagrams/login-sequence.md — Mermaid sequenceDiagram covering the login + cookie + /me path
   6.2 backend/README.md — document SESSION_SECRET (how to set in dev / prod) and link the diagram
   6.3 No new ADR — link ADR-0001 in the PR description

7. Exit-criteria sweep
   7.1 mypy --strict and tsc --noEmit clean across changed code
   7.2 Backend coverage gate ≥ 85 % still green
   7.3 PR description "Security considerations" section enumerates: new endpoints; new dep
       (itsdangerous); SESSION_SECRET handling; SameSite=Lax CSRF posture; rate-limit and lockout
       deferral to Phase 10; FR-019 logging shape; cookie attribute matrix
```

## Complexity Tracking

No constitution violations to justify.
