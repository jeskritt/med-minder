# Implementation Plan: In-App Admin User Management

**Branch**: `009-admin-user-management` | **Date**: 2026-05-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-admin-user-management/spec.md`

## Summary

Bring the `medminder-admin user` CLI's capabilities into the app for admins, so routine
account work no longer needs a hosting one-shot job. A new **`require_admin`** dependency
gates a new **`/api/v1/users`** router that reuses the existing user domain
(`create_user` / `update_user` / `soft_delete_user` / `list_users`) wholesale — the only
net-new domain logic is the **last-admin / no-self guards**, a **temp-password generator**,
and an **append-only audit log**. Admins list active users; create them (typing a password
or generating a one-time temporary one); edit name/email/role; reset passwords (revoking the
target's sessions); and deactivate (soft-delete + revoke). The acting admin's own row is
**read-only** in the admin UI (self changes go through the existing profile editor), and the
guards make self-deactivation and removing the last admin impossible. Every successful action
writes **one** audit row (actor, action, target, changed-field summary, timestamp — never
secret values); denials stay in ordinary logs. One new table → one Alembic migration. The
frontend adds an admin-only `/admin/users` route, an "Admin" nav link shown only to admins,
and the create/edit/reset/deactivate dialogs (in-app confirm modal, never native
`confirm()`). Closes with ADR-0014 (recording the reversal of "no admin web UI in v1") and a
doc sweep (glossary, user stories, ER diagram, a deactivate-with-revoke sequence diagram,
`CLAUDE.md`).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 + React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (typed `Mapped`), Pydantic v2 strict,
`argon2-cffi`, `itsdangerous` (signed cookies), stdlib `secrets` (temp-password generation —
no new dependency); TanStack Router/Query, React Hook Form + Zod, `openapi-fetch` with the
generated `api/v1.d.ts` client.

**Storage**: PostgreSQL — existing `users` + `sessions` tables (read/write via reused
domain), **one new append-only table `admin_audit_log`** → **one Alembic migration**
(`just migrate-rev`).

**Testing**: pytest + pytest-asyncio + httpx `ASGITransport` against **real Postgres**
(rollback-per-test, prepared-statement cache disabled); vitest + Testing Library (frontend).

**Target Platform**: Linux server + browser PWA.

**Project Type**: Web application (backend + frontend).

**Performance Goals**: Standard interactive web. An admin provisions a user end-to-end in
under 1 minute without touching the hosting console (SC-001).

**Constraints**: `mypy --strict` and `tsc --noEmit` strict; coverage ≥ 85% (no module < 70%);
no raw passwords / hashes / emails in logs (Principle I); admin-only by construction
(`require_admin`); single transaction per request so the audit row commits atomically with
its action.

**Scale/Scope**: Single-tenant, low admin count. Net new surface: 1 dependency, 5 endpoints
(+1 P3 audit-list), 1 table + migration, ~4 domain functions (guards + generator + audit
write), 1 route + layout, ~4 React components, a handful of React-Query hooks.

*No `NEEDS CLARIFICATION` remain — the three `/speckit-specify` scope answers (both password
options, active-only/no-restore, add audit log) and the three `/speckit-clarify` answers
(voluntary rotation, successes-only audit, read-only self-row) are settled in `spec.md`.*

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — still PASS.*

- **I. Security-Conscious by Default (NON-NEGOTIABLE)** — PASS. All endpoints sit behind a new
  `require_admin` dependency (wraps `get_current_user`, 403 on non-admins) — least privilege
  enforced server-side, not just hidden in the UI (FR-001/SC-003). Password reset and
  deactivation reuse `revoke_all_user_sessions` (the established ADR-0001 pattern). Temporary
  passwords are generated with `secrets`, shown **once** in the response body, and only their
  Argon2id hash is persisted (never the plaintext, never logged). The audit log stores changed
  **field names** only — no passwords, hashes, or other secret values (FR-013). Self-action and
  last-admin guards make lockout structurally impossible (FR-009/FR-010/SC-006). New surface
  area (5 endpoints + 1 table) gets its threat note in **ADR-0014** and the PR "Security
  considerations" section; a **`checklists/security.md`** merge gate is required for this
  security-sensitive feature (Principle IV) — generate via `/speckit-checklist`.
- **II. Fully Typed Across the Stack** — PASS. New Pydantic request/response models run strict
  (`extra="forbid"`); the new `AdminAuditLog` model uses 2.0 typed `Mapped[...]`; the TS client
  is **regenerated** (`just generate-client`), never hand-edited; `mypy --strict` + `tsc
  --noEmit` cover new code.
- **III. Loose Coupling, Testable Units** — PASS. The guards (`count_active_admins`,
  last-admin / self checks), the temp-password generator, and the audit-write all live in the
  **domain** and are testable without HTTP or a running server. They orchestrate the existing
  `create_user` / `update_user` / `soft_delete_user` / `revoke_all_user_sessions` primitives —
  the CLI and the app share one domain layer, no transport-duplicated logic.
- **IV. Documented Decisions** — PASS with deliverables: **ADR-0014** (Proposed → Accepted with
  the PR) recording the in-app admin surface and the reversal of the glossary's "no admin web
  UI in v1"; the **ER diagram gains `admin_audit_log`** (schema delta — required by Principle
  IV); a **sequence diagram** for the deactivate-with-session-revoke flow; `checklists/
  requirements.md` exists and `checklists/security.md` is added.
- **V. Cross-Platform Tooling Integrity** — PASS. One Alembic migration via `just migrate-rev`
  (runs in CI against fresh Postgres, `alembic check` for drift); no new `scripts/`; no new
  runtime dependency (`secrets` is stdlib); `just generate-client` is the only generator
  invoked.

No violations → **Complexity Tracking is empty / omitted.**

## Project Structure

### Documentation (this feature)

```text
specs/009-admin-user-management/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions (D1–D9)
├── data-model.md        # Phase 1 — new admin_audit_log table + users/sessions touched
├── quickstart.md        # Phase 1 — manual + API + automated verification
├── contracts/
│   └── users.openapi.yaml   # Phase 1 — /api/v1/users CRUD + reset + audit-list deltas
├── checklists/
│   └── requirements.md  # spec-quality gate (exists); security.md to be added
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/src/medminder/
├── api/
│   ├── deps.py            # MODIFY: add require_admin (wraps get_current_user, 403 if role != admin)
│   ├── users.py           # NEW: /api/v1/users router — list/create/patch/reset-password/delete
│   │                      #      + GET audit-list (P3); request/response schemas (extra="forbid")
│   └── app.py             # MODIFY: include_router(users.router)
├── domain/
│   ├── users.py           # MODIFY: add get_user_by_id, count_active_admins, and admin-scoped
│   │                      #         orchestration (resolve-by-id → reuse update_user/
│   │                      #         soft_delete_user) with last-admin + no-self guards;
│   │                      #         new LastAdminError, SelfActionError
│   ├── passwords.py       # MODIFY: add generate_temp_password() (secrets, ≥ 12 chars)
│   └── audit.py           # NEW: record_admin_action(session, *, actor_id, action,
│   │                      #      target_user_id, details)
├── db/models/
│   ├── admin_audit.py     # NEW: AdminAuditLog (append-only)
│   └── __init__.py        # MODIFY: re-export AdminAuditLog (so Alembic sees the table)
└── alembic/versions/      # NEW: one migration creating admin_audit_log

backend/tests/
├── domain/
│   ├── test_admin_guards.py        # NEW: count_active_admins, last-admin + self guards
│   ├── test_temp_password.py       # NEW: generated pw ≥ 12 chars, random, hashes
│   └── test_admin_audit.py         # NEW: record_admin_action writes one row, no secrets
└── api/
    ├── test_users_admin_access.py  # NEW: non-admin → 403 on every endpoint (US1/FR-001)
    ├── test_users_create.py        # NEW: type/generate, duplicate 409, short 422, temp-once
    ├── test_users_edit.py          # NEW: name/email/role, dup 409, self 403, last-admin 409
    ├── test_users_password.py      # NEW: reset revokes target sessions; self → 403
    ├── test_users_delete.py        # NEW: soft-delete + revoke; self 403; last-admin 409
    └── test_users_audit.py         # NEW: one entry per action; reverse-chron list (P3)

frontend/src/
├── routes/
│   ├── admin.tsx           # NEW: layout (<Outlet/>) + beforeLoad admin guard
│   ├── admin.users.tsx     # NEW: users page (list + dialogs)
│   └── admin.audit.tsx     # NEW (P3): read-only audit view
├── components/admin/
│   ├── UserList.tsx            # NEW: card rows; edit/reset/deactivate actions; self-row read-only
│   ├── UserFormDialog.tsx      # NEW: create + edit modal (RHF + Zod)
│   ├── ResetPasswordDialog.tsx # NEW: type-or-generate; one-time temp-password display
│   └── DeactivateUserModal.tsx # NEW: in-app confirm (UntakeConfirmModal pattern)
├── components/NavBar.tsx   # MODIFY: show an "Admin" link only when user.role === "admin"
├── lib/adminUsers.ts       # NEW: React-Query queries + mutations for /api/v1/users
├── api/v1.d.ts             # REGENERATE via `just generate-client`
└── __tests__/AdminUsers.test.tsx   # NEW

docs/
├── adr/0014-in-app-admin-user-management.md   # NEW (doc sweep) — next free number is 0014
├── diagrams/er.md                              # MODIFY: add admin_audit_log
├── diagrams/admin-deactivate-user.md           # NEW sequence diagram (doc sweep)
├── glossary.md                                 # MODIFY: Admin def + "Audit log" term
└── user_stories.md                             # MODIFY: in-app admin UC alongside CLI UC-1

CLAUDE.md                  # MODIFY: SPECKIT marker → this plan; add a "surprises" note (doc sweep)
```

**Structure Decision**: Existing web layout (`backend/` + `frontend/`). The backend change is
a new `/api/v1/users` router behind a new `require_admin` dep, thin over the existing user
domain plus a small amount of net-new domain logic (guards, generator, audit) and one new
table. The frontend adds an admin-only route subtree and a few dialogs reusing established
patterns (RHF + Zod forms like `MedicationForm`; in-app confirm like `UntakeConfirmModal`).
ADR/ER/glossary/README edits are the FR-013/doc-sweep tasks, executed in the implement phase.
