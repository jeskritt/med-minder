# Implementation Plan: Self-Service Profile Editor

**Branch**: `007-profile-editor` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-profile-editor/spec.md`

## Summary

Authenticated users edit their own **display name** and **password** from a **modal**
opened by clicking their name in the nav bar — so the admin never knows the
user-chosen password. Two new root-level endpoints back it: `PATCH /me` (display name)
and `POST /me/password` (current-password re-auth → new password). A wrong current
password returns **403** (distinct from the **422** for a too-short new password, never
**401**). On a successful password change the server revokes **all** of the user's
sessions and **re-issues a fresh session cookie** so the current device stays signed in
while every other device is logged out. The work reuses the Phase 2 auth substrate and
the existing password/session/user domain wholesale; **no schema change**. A forgotten
password is recovered with the **existing** admin CLI (`user update … --password-stdin`)
— verified and documented, not rebuilt. Closes with a doc sweep (ADR-0011, a
password-change sequence diagram, `CLAUDE.md`, and a root-README quickstart step).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 + React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (typed `Mapped`), Pydantic v2 strict,
`argon2-cffi`, `itsdangerous` (signed cookies); TanStack Router/Query, React Hook Form +
Zod, `openapi-fetch` with the generated `api/v1.d.ts` client.

**Storage**: PostgreSQL — existing `users` and `sessions` tables only. **No new tables
or columns; no Alembic migration.**

**Testing**: pytest + pytest-asyncio + httpx `ASGITransport` against **real Postgres**
(rollback-per-test); vitest + Testing Library (frontend).

**Target Platform**: Linux server + browser PWA.

**Project Type**: Web application (backend + frontend).

**Performance Goals**: Standard interactive web; a name change is reflected in the nav
bar within 2 s / on the next `["me"]` refetch (SC-004).

**Constraints**: `mypy --strict` and `tsc --noEmit` strict; coverage ≥ 85% (no module
< 70%); no raw passwords / hashes / emails in logs (Principle I); scoped-to-self by
construction.

**Scale/Scope**: Single-tenant, low-traffic. Net new surface: 2 endpoints, 1 domain
function, 1 modal component, 2 React-Query mutations.

*No `NEEDS CLARIFICATION` remain — the four `/speckit-clarify` answers (modal surface,
name ≤ 100, wrong-pw → 403, no audit in v1) and the three spec decisions (fields,
re-auth, session handling) are settled in `spec.md` Clarifications.*

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — still PASS.*

- **I. Security-Conscious by Default (NON-NEGOTIABLE)** — PASS. Password change requires
  current-password re-auth (`verify_password`), returns **403** on mismatch (never 401,
  which would bounce the user to login), revokes all sessions then re-issues a rotated
  token, and never logs secrets. The domain entry point takes the **authenticated
  `User`** (not an email/id parameter), so there is structurally no path to change
  another user's credentials (FR-006/FR-012). New surface area (2 endpoints) gets its
  threat note in **ADR-0011** and the PR's "Security considerations" section. Email stays
  admin-managed (FR-010). A `checklists/security.md` merge gate is required for this
  security-sensitive feature (Principle IV) — generate via `/speckit-checklist`.
- **II. Fully Typed Across the Stack** — PASS. New Pydantic request models run strict
  (`extra="forbid"`); the TS client is **regenerated** (`just generate-client`), never
  hand-edited; `mypy --strict` + `tsc --noEmit` cover new code.
- **III. Loose Coupling, Testable Units** — PASS. The password-change logic lands in
  `domain/users.py` (`change_own_password`) and is testable without HTTP; it reuses
  `domain/passwords.py` and `domain/sessions.py`. The name path reuses the existing
  `update_user`. No transport-duplicated logic.
- **IV. Documented Decisions** — PASS with deliverables: **ADR-0011** (Proposed →
  Accepted with the PR); a **sequence diagram** for the password-change-with-reissue flow
  under `docs/diagrams/`; the **ER diagram is unchanged** (no schema delta — noted
  explicitly); `checklists/requirements.md` exists and `checklists/security.md` is added.
- **V. Cross-Platform Tooling Integrity** — PASS. No new scripts, no migration, deps
  unchanged; `just generate-client` is the only generator invoked.

No violations → **Complexity Tracking is empty / omitted.**

## Project Structure

### Documentation (this feature)

```text
specs/007-profile-editor/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions
├── data-model.md        # Phase 1 — entities touched (no schema change)
├── quickstart.md        # Phase 1 — manual + automated verification
├── contracts/
│   └── profile.openapi.yaml   # Phase 1 — PATCH /me, POST /me/password deltas
├── checklists/
│   └── requirements.md  # spec-quality gate (exists); security.md to be added
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/src/medminder/
├── api/
│   ├── me.py              # MODIFY: add PATCH /me + POST /me/password and their
│   │                      #         request schemas (ProfileUpdate, PasswordChange)
│   └── deps.py            # REUSE: get_current_user, set_session_cookie, cookie_serializer
├── domain/
│   ├── users.py           # MODIFY: add change_own_password(...) + IncorrectPasswordError;
│   │                      #         reuse update_user(...) for the name path
│   ├── passwords.py       # REUSE: verify_password, password_too_short, hash_password
│   └── sessions.py        # REUSE: revoke_all_user_sessions, create_session, hash_token
└── app.py                # no change (me router already registered)

backend/tests/
├── domain/test_change_own_password.py   # NEW (US1 password domain)
└── api/
    ├── test_me_password.py              # NEW (US1: POST /me/password)
    ├── test_me_profile.py               # NEW (US2: PATCH /me display name)
    └── test_password_recovery.py        # NEW (US3: CLI-set → login → self-change)

frontend/src/
├── components/
│   ├── NavBar.tsx                 # MODIFY: name becomes a button that opens the dialog
│   └── profile/ProfileDialog.tsx  # NEW: modal with a name section + a password section
├── lib/
│   └── auth.ts                    # MODIFY: add useUpdateProfile + useChangePassword
├── api/v1.d.ts                    # REGENERATE via `just generate-client`
└── __tests__/ProfileDialog.test.tsx   # NEW

docs/
├── adr/0011-self-service-credential-management.md   # NEW (doc sweep)
└── diagrams/profile-password-change.md              # NEW sequence diagram (doc sweep)

README.md                          # MODIFY: Quickstart gains create-user + set-password (FR-016)
CLAUDE.md                          # MODIFY: add a "surprises" note (doc sweep, FR-015)
```

**Structure Decision**: Existing web layout (`backend/` + `frontend/`). The feature is
additive — two endpoints on the existing `me` router, one domain function, one modal —
with no new module boundaries and no database change. Doc/README/ADR edits are part of
the FR-015/FR-016 doc sweep, executed in the implement phase, not here.
