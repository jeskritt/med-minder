---
description: "Task list for In-App Admin User Management (Feature 009)"
---

# Tasks: In-App Admin User Management

**Input**: Design documents from `/specs/009-admin-user-management/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/users.openapi.yaml

**Tests**: INCLUDED — the constitution mandates a ≥ 85% coverage gate and CI integration tests
(Principle V), and research D8 specifies the test layout. Test tasks are first-class here.

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md) so each story is an
independently testable increment. The audit-log table + writer are foundational (every US1–US3
action records an entry, FR-013); the audit *view* is the P3 story US4.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4 (omitted for Setup, Foundational, Polish)

## Path Conventions

Web app: `backend/src/medminder/`, `backend/tests/`, `frontend/src/`. Paths below are exact.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding shared by every admin API test.

- [ ] T001 Add `admin_user` and `non_admin_user` fixtures plus an admin-authenticated client helper to `backend/tests/api/conftest.py` (reuse the existing `AsyncClient`/`ASGITransport` + login helpers).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The admin gate, the audit table + writer, the temp-password generator, and the
shared id-lookup/guard helpers. US1 cannot record audit entries or generate passwords, and
US2/US3 cannot enforce guards, until these exist.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [ ] T002 Create `AdminAuditLog` model (append-only: `id`, `actor_id` FK→users, `target_user_id` FK→users, `action` enum, `details` JSONB, `created_at`; no `updated_at`/`deleted_at`) in `backend/src/medminder/db/models/admin_audit.py` per data-model.md
- [ ] T003 Re-export `AdminAuditLog` from `backend/src/medminder/db/models/__init__.py` (so Alembic autogenerate sees the table)
- [ ] T004 Generate the Alembic migration for `admin_audit_log` (`just migrate-rev "add admin_audit_log"`), review it, and confirm `alembic upgrade head` + `alembic check` are clean
- [ ] T005 [P] Add `generate_temp_password()` (stdlib `secrets`, ≥ 12 chars, cryptographically secure) to `backend/src/medminder/domain/passwords.py` (FR-004/FR-011-entropy)
- [ ] T006 [P] Add `record_admin_action(session, *, actor_id, action, target_user_id, details)` to new `backend/src/medminder/domain/audit.py` (writes one row; never includes secret values — FR-013/FR-020)
- [ ] T007 Add `get_user_by_id(...)`, `count_active_admins(...)` (with a `FOR UPDATE` lock on the active-admin rows — FR-021), and new `SelfActionError` / `LastAdminError` to `backend/src/medminder/domain/users.py`
- [ ] T008 Add the `require_admin` dependency (wraps `get_current_user`; 403 if `role != "admin"`) to `backend/src/medminder/api/deps.py` (FR-001)
- [ ] T009 [P] Domain test: `generate_temp_password` length/randomness/hashes in `backend/tests/domain/test_temp_password.py`
- [ ] T010 [P] Domain test: `record_admin_action` writes exactly one row with no secret in `details`; and assert (via `caplog`) that the create/reset code paths emit no password or hash to logs (FR-013/FR-020) — in `backend/tests/domain/test_admin_audit.py`
- [ ] T011 [P] Domain test: `count_active_admins`, self-action guard, and last-admin guard (deactivate + demote); plus a serialized two-operation test proving concurrent last-admin removals cannot both succeed under the `FOR UPDATE` lock (FR-021) — in `backend/tests/domain/test_admin_guards.py`
- [ ] T012 Create the `/api/v1/users` router skeleton (`APIRouter(prefix="/api/v1/users", tags=["users"])`, all routes `Depends(require_admin)`) in `backend/src/medminder/api/users.py` and register it in `backend/src/medminder/app.py`

**Checkpoint**: Admin gate, audit table/writer, generator, and guard helpers exist and are unit-tested.

---

## Phase 3: User Story 1 — Provision and view users (Priority: P1) 🎯 MVP

**Goal**: An admin lists active users and creates a user (typed or generated password, shown once).

**Independent Test**: Sign in as admin → open the admin Users page → create a user (typed, then
generated) → the new user appears in the list and can sign in; a non-admin cannot reach the page
or the endpoints.

### Tests for User Story 1 (write first)

- [ ] T013 [P] [US1] API test: non-admin → 403 and unauthenticated → 401 on `GET`/`POST /api/v1/users` in `backend/tests/api/test_users_admin_access.py` (FR-001/SC-003)
- [ ] T014 [P] [US1] API test: create — typed → 201 (no temp pw); `generate` → 201 + `temporary_password` once; duplicate email (incl. soft-deleted) → 409; short typed pw → 422; both/neither password+generate → 422; malformed email → 422 (FR-023); the created user can authenticate immediately with no forced password change (FR-018); one audit row written — in `backend/tests/api/test_users_create.py`

### Implementation for User Story 1

- [ ] T015 [US1] Add `UserOut`, `UserListOut`, `UserCreate`, `CreatedUser` Pydantic schemas (`extra="forbid"`; `email: EmailStr` and `name: Field(min_length=1, max_length=100)` per FR-023; `UserCreate` `model_validator` enforces exactly one of `password`/`generate`) in `backend/src/medminder/api/users.py`
- [ ] T016 [US1] Implement `GET /api/v1/users` (active users via `list_users`) in `backend/src/medminder/api/users.py`
- [ ] T017 [US1] Implement `POST /api/v1/users` (create via `create_user`; `generate_temp_password` when requested; `record_admin_action`; map `DuplicateEmailError`→409, `PasswordTooShortError`→422; return `CreatedUser` with one-time `temporary_password`) in `backend/src/medminder/api/users.py`
- [ ] T018 [US1] Regenerate the typed client (`just generate-client`) so `frontend/src/api/v1.d.ts` covers the new list/create endpoints
- [ ] T019 [P] [US1] Add `useUsers` (query) and `useCreateUser` (mutation, invalidates `["admin","users"]`) to `frontend/src/lib/adminUsers.ts`
- [ ] T020 [US1] Create the admin layout route with a `beforeLoad` admin guard (read `/me`; redirect non-admins) in `frontend/src/routes/admin.tsx`
- [ ] T021 [US1] Create the users page (list + "Add user") in `frontend/src/routes/admin.users.tsx`
- [ ] T022 [US1] Create `UserList` (card rows: email/name/role/created — display only for now) in `frontend/src/components/admin/UserList.tsx`
- [ ] T023 [US1] Create `UserFormDialog` (create mode: email/name/role + type-or-generate password control; 409/422 → field errors) in `frontend/src/components/admin/UserFormDialog.tsx`
- [ ] T024 [US1] Show a generated temporary password exactly once (copy button + "won't be shown again") after create — in `UserFormDialog.tsx` or a small `TempPasswordDialog.tsx` under `frontend/src/components/admin/`
- [ ] T025 [P] [US1] Show an "Admin" nav link only when `useCurrentUser()?.role === "admin"` in `frontend/src/components/NavBar.tsx` (FR-015)
- [ ] T026 [US1] Component test: nav link visible only for admins; a non-admin hitting `/admin/users` is redirected by the route guard (FR-001); list renders; create dialog calls `POST`; generated temp password shown once — in `frontend/src/__tests__/AdminUsers.test.tsx`

**Checkpoint**: MVP — admins can list and create users in-app; non-admins are locked out; each create writes an audit row.

---

## Phase 4: User Story 2 — Edit a user and reset password (Priority: P2)

**Goal**: An admin edits name/email/role and resets passwords; a reset revokes the target's sessions.

**Independent Test**: Edit a user's name/role (persists); change email to a taken one (409);
reset a user's password and confirm their pre-existing sessions stop authenticating; editing your
own row here is refused.

### Tests for User Story 2 (write first)

- [ ] T027 [P] [US2] API test: edit — name/email/role → 200; duplicate email → 409; malformed email → 422 (FR-023); editing self → 403; demoting the sole admin → 409; unknown field → 422; **non-admin → 403** (FR-001/SC-003); audit row — in `backend/tests/api/test_users_edit.py`
- [ ] T028 [P] [US2] API test: reset — revokes the target's existing sessions (a pre-existing session 401s after); self → 403; `generate` returns temp pw once; **non-admin → 403** (FR-001/SC-003); audit row — in `backend/tests/api/test_users_password.py`

### Implementation for User Story 2

- [ ] T029 [US2] Add `UserUpdate` (≥1 of name/email/role, `extra="forbid"`, `email: EmailStr`, `name: Field(min_length=1, max_length=100)` per FR-023), `PasswordSet`, and `PasswordResetOut` schemas in `backend/src/medminder/api/users.py`
- [ ] T030 [US2] Add `admin_update_user(session, *, actor, user_id, ...)` (resolve by id → self-edit guard → last-admin demote guard → reuse `update_user` → `record_admin_action`) in `backend/src/medminder/domain/users.py`
- [ ] T031 [US2] Add `admin_reset_password(session, *, actor, user_id, password|generate)` (resolve → self guard → reuse `update_user(new_password=…)` which revokes sessions → `record_admin_action`; returns temp pw if generated) in `backend/src/medminder/domain/users.py`
- [ ] T032 [US2] Implement `PATCH /api/v1/users/{user_id}` (map `UserNotFoundError`→404, `DuplicateEmailError`/`LastAdminError`→409, `SelfActionError`→403, validation→422) in `backend/src/medminder/api/users.py`
- [ ] T033 [US2] Implement `POST /api/v1/users/{user_id}/password` (200 + one-time temp pw; `SelfActionError`→403; `UserNotFoundError`→404) in `backend/src/medminder/api/users.py`
- [ ] T034 [US2] Regenerate the typed client (`just generate-client`) for the edit/reset endpoints
- [ ] T035 [P] [US2] Add `useUpdateUser` and `useResetPassword` mutations to `frontend/src/lib/adminUsers.ts`
- [ ] T036 [US2] Extend `UserFormDialog` with an edit mode (name/email/role) in `frontend/src/components/admin/UserFormDialog.tsx`
- [ ] T037 [US2] Create `ResetPasswordDialog` (type-or-generate; one-time temp display) in `frontend/src/components/admin/ResetPasswordDialog.tsx`
- [ ] T038 [US2] Add Edit + Reset-password row actions to `UserList`, and render the acting admin's own row actions **disabled** with a "manage in profile editor" hint (FR-019) in `frontend/src/components/admin/UserList.tsx`
- [ ] T039 [US2] Extend the component test: edit calls `PATCH`; reset calls the password endpoint; self-row actions are disabled — in `frontend/src/__tests__/AdminUsers.test.tsx`

**Checkpoint**: Admins can edit users and reset passwords; self-edit and last-admin demotion are blocked; resets log the target out everywhere.

---

## Phase 5: User Story 3 — Deactivate a user (Priority: P2)

**Goal**: An admin deactivates a user via an in-app confirm; the user is signed out everywhere and
hidden; self-deactivation and last-admin removal are blocked.

**Independent Test**: Deactivate a test user → they vanish from the list, can't authenticate, and
their sessions are revoked; attempting to deactivate yourself or the sole admin is refused.

### Tests for User Story 3 (write first)

- [ ] T040 [P] [US3] API test: deactivate → 204, user gone from list + sessions revoked; self → 403; sole admin → 409; **non-admin → 403** (FR-001/SC-003); audit row — in `backend/tests/api/test_users_delete.py`

### Implementation for User Story 3

- [ ] T041 [US3] Add `admin_deactivate_user(session, *, actor, user_id)` (resolve → self guard → last-admin guard → reuse `soft_delete_user` which revokes sessions → `record_admin_action`) in `backend/src/medminder/domain/users.py`
- [ ] T042 [US3] Implement `DELETE /api/v1/users/{user_id}` (204; `SelfActionError`→403; `UserNotFoundError`→404; `LastAdminError`→409) in `backend/src/medminder/api/users.py`
- [ ] T043 [US3] Regenerate the typed client (`just generate-client`) for the delete endpoint
- [ ] T044 [P] [US3] Add `useDeactivateUser` mutation to `frontend/src/lib/adminUsers.ts`
- [ ] T045 [US3] Create `DeactivateUserModal` (in-app `role="dialog"` confirm — NOT native `confirm()`) in `frontend/src/components/admin/DeactivateUserModal.tsx`
- [ ] T046 [US3] Add a Deactivate row action to `UserList` wired to the modal (disabled on the self-row) in `frontend/src/components/admin/UserList.tsx`
- [ ] T047 [US3] Extend the component test: deactivate opens the in-app modal and calls `DELETE`; self-row deactivate is disabled — in `frontend/src/__tests__/AdminUsers.test.tsx`

**Checkpoint**: Full lifecycle (create/edit/reset/deactivate) works in-app with lockout-proof guards.

---

## Phase 6: User Story 4 — Audit trail view (Priority: P3)

**Goal**: A read-only in-app view of the audit entries that US1–US3 already record.

**Independent Test**: Perform create/edit/reset/deactivate, open the audit view → the entries
appear newest-first, attributed to the actor, with no secret values; non-admins can't view it.

### Tests for User Story 4 (write first)

- [ ] T048 [P] [US4] API test: `GET /api/v1/users/audit-log` returns entries reverse-chronological with no secret values; non-admin → 403; and confirm the audit log exposes no edit/delete route (append-only, FR-022) — in `backend/tests/api/test_users_audit.py`

### Implementation for User Story 4

- [ ] T049 [US4] Add `AuditEntryOut` + `AuditListOut` schemas and implement `GET /api/v1/users/audit-log` (declare before `/{user_id}`; newest-first) in `backend/src/medminder/api/users.py`
- [ ] T050 [US4] Regenerate the typed client (`just generate-client`) for the audit endpoint
- [ ] T051 [P] [US4] Add `useAuditLog` query to `frontend/src/lib/adminUsers.ts`
- [ ] T052 [US4] Create the read-only audit view (linked from the admin users page) in `frontend/src/routes/admin.audit.tsx`
- [ ] T053 [US4] Component test: the audit view renders entries newest-first — in `frontend/src/__tests__/AdminUsers.test.tsx`

**Checkpoint**: All four stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns (Docs sweep + gates)

**Purpose**: The FR-013/Principle-IV documentation sweep and the final merge gates.

- [ ] T054 [P] Write **ADR-0014 — "In-app admin user management"** (Proposed→Accepted) recording the `require_admin` gate, the `/api/v1/users` surface reusing the user domain, the guards, type-or-generate temp passwords with voluntary rotation, the successes-only `admin_audit_log`, and the **reversal of the glossary's "no admin web UI in v1"** stance, with the Principle I threat note — in `docs/adr/0014-in-app-admin-user-management.md`
- [ ] T055 [P] Add `admin_audit_log` (and its FKs to `users`) to the ER diagram in `docs/diagrams/er.md`
- [ ] T056 [P] Add a deactivate-with-session-revoke sequence diagram in `docs/diagrams/admin-deactivate-user.md`
- [ ] T057 [P] Update the **Admin** glossary entry (in-app + CLI, shared domain) and add an **Audit log** term in `docs/glossary.md`
- [ ] T058 [P] Add an in-app admin-management user story alongside the CLI-only UC-1 in `docs/user_stories.md`
- [ ] T059 Add a "surprises" note (admin surface behind `require_admin`; append-only successes-only audit; read-only self-row; temp passwords shown once, voluntary rotation) in `CLAUDE.md`
- [ ] T060 Finalize the merge gate: tick the remaining reviewer-confirmation items in `specs/009-admin-user-management/checklists/requirements.md` and `checklists/security.md` (`[x]`/`[~]`)
- [ ] T061 Run the `quickstart.md` walkthrough end-to-end against `just dev` and confirm every expected result
- [ ] T062 Run all gates: `just lint`, `just typecheck`, `just test` (coverage ≥ 85%), `just generate-client` (no client drift), and `alembic upgrade head` + `alembic check` (no migration drift)
- [ ] T063 [P] Regression test: confirm a regular user still cannot change their own email or role — `PATCH /me` with an `email`/`role` field is rejected `422` (`extra="forbid"`, FR-017) — in `backend/tests/api/test_me_profile.py`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → after Setup; **blocks all stories** (gate, audit table/writer, generator, guards).
- **US1 (P3)** → after Foundational. The MVP.
- **US2 (P4)**, **US3 (P5)** → after Foundational; independently testable. They edit the same shared
  files as US1 additively (`api/users.py`, `domain/users.py`, `lib/adminUsers.ts`, `UserList.tsx`),
  so if worked in parallel, coordinate those files; run in priority order otherwise.
- **US4 (P6)** → after Foundational (needs the audit table) and benefits from US1–US3 having
  produced entries to display; the endpoint/view themselves only depend on Foundational.
- **Polish (P7)** → after the stories you intend to ship.

### Within a story

- Tests first (write failing) → schemas → domain → endpoints → client regen → frontend hooks →
  components/routes → component tests.

### Parallel opportunities

- Foundational: T005, T006, T009, T010, T011 are `[P]` (distinct files); T002→T003→T004 are
  sequential (model → register → migration); T007/T008 are independent of the audit chain.
- Per story: the two API tests are `[P]`; the `lib/adminUsers.ts` hook task is `[P]` against
  backend tasks; same-file endpoint/schema tasks in `api/users.py` are sequential.
- Polish: T054–T058 are `[P]` (separate doc files).

---

## Parallel Example: Foundational

```bash
# After T002→T003→T004 (model/register/migration), run the independent domain pieces together:
Task: "T005 generate_temp_password in backend/src/medminder/domain/passwords.py"
Task: "T006 record_admin_action in backend/src/medminder/domain/audit.py"
Task: "T009 temp-password domain test"
Task: "T010 audit-writer domain test"
Task: "T011 guards domain test"
```

## Parallel Example: User Story 1

```bash
# Tests first, in parallel:
Task: "T013 admin-access API test (403/401)"
Task: "T014 create API test (type/generate/409/422/audit)"

# Frontend hook + nav link can proceed alongside backend endpoint work:
Task: "T019 useUsers + useCreateUser in frontend/src/lib/adminUsers.ts"
Task: "T025 Admin nav link in frontend/src/components/NavBar.tsx"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → Phase 2 Foundational (CRITICAL).
2. Phase 3 US1.
3. **STOP & VALIDATE**: admins list + create users in-app; non-admins blocked; audit rows written.
4. Demo / ship the MVP — the one-shot CLI job is no longer needed for provisioning.

### Incremental delivery

US1 (provision) → US2 (edit/reset) → US3 (deactivate) → US4 (audit view) → Polish (ADR + doc
sweep + gates). Each story is an independently testable, shippable increment.

---

## Notes

- `[P]` = different files, no incomplete dependency. Same-file tasks (most of `api/users.py`,
  `domain/users.py`, `UserList.tsx`) are intentionally sequential.
- Backend tests run against **real Postgres** (rollback-per-test); reuse `tests/api/conftest.py`.
- Regenerate `api/v1.d.ts` whenever endpoints change (`just generate-client`); CI fails on drift.
- Do **not** use native `confirm()` for deactivation (T045) — in-app modal only.
- The doc sweep (T054–T059) is part of "done" per Constitution Principle IV, not optional polish.
- Git is the user's domain — commit/branch when you decide; no task assumes a commit.
