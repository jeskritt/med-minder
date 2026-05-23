---

description: "Feature 007 — Self-Service Profile Editor: actionable, dependency-ordered tasks"
---

# Tasks: Self-Service Profile Editor

**Input**: Design documents in `specs/007-profile-editor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/profile.openapi.yaml, quickstart.md

**Tests**: Test tasks **are** included. The spec mandates them — SC-003 (current device
stays in, others die), FR-003 (wrong current pw → 403, distinct from 422), and
FR-013/FR-014 (mypy/tsc strict; coverage ≥ 85 %, no module < 70 %). Security decision is
**ADR-0011** (self-service credential change; current-password re-auth;
revoke-all-then-reissue; never 401; no audit in v1).

**Organization**: Tasks are grouped by user story. US1 (password) is the MVP; US2 (name)
is additive on the shared modal; US3 (recovery) is verify + document only — no new CLI.

## Format: `[ID] [P?] [Story] Description`

- **[P]** — parallelizable (different files, no dependency on incomplete tasks)
- **[Story]** — `[US1]`/`[US2]`/`[US3]`. Setup / Foundational / Polish carry no story label.
- File paths are repo-relative.

## Path Conventions (from `plan.md` Project Structure)

- Backend: `backend/src/medminder/`, tests under `backend/tests/{domain,api}/`
- Frontend: `frontend/src/`, tests under `frontend/src/__tests__/`, E2E under `frontend/e2e/`
- Diagrams: `docs/diagrams/`; ADR: `docs/adr/`
- `just` recipes need bash on Windows (Git Bash/WSL); PowerShell-direct equivalent noted on the kickoff task.
- **No DB migration** — this feature changes no schema (data-model.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm a clean, drift-free baseline and create the doc/gate skeletons.

- [ ] T001 **Baseline sanity gate (run FIRST).** Run `just generate-client` (PowerShell-direct: `python scripts/generate_openapi_client.py`) and confirm `git status --porcelain frontend/src/api/v1.d.ts` is empty; then `cd backend && python -m alembic check` → no drift. Mirrors CI; fix any dirtiness before starting. (quickstart.md §3.)
- [ ] T002 [P] Create `docs/adr/0011-self-service-credential-management.md` skeleton, Status **Proposed**, with Context/Decision/Consequences headings and a TODO (filled + Accepted in Polish, per research D7).
- [ ] T003 [P] Create `docs/diagrams/profile-password-change.md` with a `# Profile password change` heading and a TODO note (Mermaid sequence filled in Polish).
- [ ] T004 [P] Create `specs/007-profile-editor/checklists/security.md` skeleton (security-sensitive merge gate, plan.md Constitution §I): unchecked items for current-password re-auth (FR-003), wrong-pw → 403 not 401, scoped-to-self / no cross-user path (FR-006), no raw secrets in logs/responses (FR-012), session revoke-all-then-reissue (FR-005), plus a "PR includes a Security considerations section" line.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared nav-bar entry point and the modal shell that both US1 and US2 mount their sections into.

**⚠️ CRITICAL**: No user-story frontend work can begin until this phase is complete.

- [ ] T005 Make the user's name in `frontend/src/components/NavBar.tsx` an interactive control: replace the `<span className="text-gray-600">{user.name}</span>` (NavBar.tsx:56) with a `<button>` that toggles profile-dialog open state; only when authenticated; remains hidden on `/login` (existing guard). (FR-001)
- [ ] T006 Create `frontend/src/components/profile/ProfileDialog.tsx`: a modal shell that follows `frontend/src/components/UntakeConfirmModal.tsx` — plain conditional render (`if (!open) return null`), `role="dialog"`, `aria-modal="true"`, an `aria-label`, a `fixed inset-0 z-50 … bg-black/40` overlay and a white card (no native `<dialog>`); title "Profile", close control, and two labelled, initially-empty section regions — "Profile" and "Change password" — that US2/US1 fill. Wire open/close to the NavBar trigger. Depends on T005. (FR-002)

**Checkpoint**: Clicking the nav-bar name opens an (empty) modal — ready for the story sections.

---

## Phase 3: User Story 1 — Change my own password without the admin knowing it (Priority: P1) 🎯 MVP

**Goal**: A signed-in user changes their own password (current-password re-auth), stays signed in on this device, and all other sessions are revoked. **ADR-0011 graduates `Proposed → Accepted` on this story's PR.**

**Independent Test** (from spec.md): submit a new password with the correct current password → 204 + this device still works while a second pre-existing session 401s; wrong current password → 403, nothing changed; too-short → 422.

### Tests for User Story 1 ⚠️

> Write these FIRST and confirm they fail before implementation.

- [ ] T007 [P] [US1] `backend/tests/domain/test_change_own_password.py` — correct current pw → `password_hash` changes (new verifies) and all of the user's `sessions` rows are deleted; wrong current pw → `IncorrectPasswordError`, hash + sessions unchanged; `< 12` new pw → `PasswordTooShortError`, no mutation.
- [ ] T008 [P] [US1] `backend/tests/api/test_me_password.py` — via the `httpx.AsyncClient`+`ASGITransport` conftest: correct change → **204** + fresh `mm_session` cookie that still authenticates `GET /me`, while a *second* session minted for the same user before the change now **401**s; wrong current → **403**; too-short → **422**; unauthenticated → **401**. (FR-003/FR-005/SC-003)
- [ ] T009 [P] [US1] Create `frontend/src/__tests__/ProfileDialog.test.tsx` — opens from the nav-bar name; the change-password form calls `POST /me/password`; a 403 response surfaces an error on the **current password** field; a `< 12` new password is blocked client-side.

### Implementation for User Story 1

- [ ] T010 [US1] In `backend/src/medminder/domain/users.py` add `class IncorrectPasswordError(DomainError)` and `async def change_own_password(session, *, user: User, current_password: str, new_password: str) -> None`: `verify_password` (mismatch → `IncorrectPasswordError`), `password_too_short` (→ `PasswordTooShortError`), set `password_hash = hash_password(...)`, `flush`, then `revoke_all_user_sessions(session, user_id=user.id)`. Reuses `domain/passwords.py` + `domain/sessions.py`. Export in `__all__`.
- [ ] T011 [US1] In `backend/src/medminder/api/me.py` add the `PasswordChange` Pydantic-strict model (`current_password`, `new_password`; `Field(min_length=1, max_length=1024)`; **no** hardcoded 12) and `POST /me/password` (status 204): inject `response: Response`, depend on `get_current_user`; call `change_own_password`; on success `create_session(db, user_id=user.id)` → sign with `cookie_serializer` → `set_session_cookie(response, …)` (overwrites the dependency's cookie); map `IncorrectPasswordError`→`HTTPException(403, "Current password is incorrect.")`, `PasswordTooShortError`→422. Depends on T010. (research D2/D4)
- [ ] T012 [US1] Run `just generate-client`; confirm `frontend/src/api/v1.d.ts` carries `POST /me/password` + `PasswordChange`; CI OpenAPI-drift check passes. Depends on T011.
- [ ] T013 [P] [US1] In `frontend/src/lib/auth.ts` add `useChangePassword` (mutation → `client.POST("/me/password", …)`): map `response.status === 403` and `=== 422` to typed field errors; success keeps the (rotated) session — optionally invalidate `["me"]`. Mirrors the `useLogout` shape. Depends on T012.
- [ ] T014 [US1] Fill the "Change password" section in `frontend/src/components/profile/ProfileDialog.tsx` with a React-Hook-Form + Zod form (`current_password`, `new_password`; Zod min 12 for instant feedback, server authoritative); wire `useChangePassword`; 403 → error on `current_password`, 422 → error on `new_password` (reuse the `MedicationForm` `serverError` pattern). Depends on T006, T013.
- [ ] T015 [US1] Fill `docs/adr/0011-self-service-credential-management.md` and set Status **Proposed → Accepted** (this story's PR): records current-password re-auth, 403/422/never-401 transport, revoke-all-then-reissue, no-audit-v1, email-admin-managed scope, and the Principle I threat note.

**Checkpoint**: US1 fully functional — self-service password change, current device stays in, other devices logged out; ADR-0011 Accepted.

---

## Phase 4: User Story 2 — Change my display name (Priority: P2)

**Goal**: A signed-in user updates their display name from the same modal; the nav bar reflects it without a reload; no current-password and no session effects.

**Independent Test** (from spec.md): change the name and save → nav bar shows the new name on the next refetch; empty/whitespace or > 100 chars rejected; no password prompt; sessions untouched.

### Tests for User Story 2 ⚠️

- [ ] T016 [P] [US2] `backend/tests/api/test_me_profile.py` — `PATCH /me` happy path → **200** with `Me.name` updated; empty/whitespace-only and > 100-char name → **422**; a body with extra fields (`email`/`role`) rejected (**422**, `extra="forbid"`) — FR-010; unauthenticated → **401**.
- [ ] T017 [P] [US2] Extend `frontend/src/__tests__/ProfileDialog.test.tsx` with name-section cases: saving the name calls `PATCH /me` and the success path invalidates `["me"]`; an empty name is rejected. (Same file as T009 — sequential, after US1.)

### Implementation for User Story 2

- [ ] T018 [US2] In `backend/src/medminder/api/me.py` add the `ProfileUpdate` model (`name: str = Field(min_length=1, max_length=100)` + a trim/non-empty validator) and `PATCH /me` (response_model `Me`): depend on `get_current_user`, call `domain.users.update_user(db, email=user.email, new_name=body.name)`, return the refreshed user. No session effects. (research D3)
- [ ] T019 [US2] Run `just generate-client`; confirm `frontend/src/api/v1.d.ts` carries `PATCH /me` + `ProfileUpdate`; CI drift check passes. Depends on T018.
- [ ] T020 [P] [US2] In `frontend/src/lib/auth.ts` add `useUpdateProfile` (mutation → `client.PATCH("/me", …)`); `onSuccess` invalidate `["me"]` so the nav bar updates without reload (FR-008). Depends on T019.
- [ ] T021 [US2] Fill the "Profile" section in `frontend/src/components/profile/ProfileDialog.tsx` with a RHF + Zod name form (trimmed, 1–100), prefilled from `useCurrentUser`; wire `useUpdateProfile`; surface validation/`serverError`. Depends on T006, T020.

**Checkpoint**: US1 + US2 both work from the one modal; name change reflected live, password change unaffected.

---

## Phase 5: User Story 3 — Recover a forgotten password via the admin (Priority: P3)

**Goal**: Confirm + document that the existing admin CLI recovers a forgotten password and the user then re-secures it via the editor. **No new CLI code.**

**Independent Test** (from spec.md): admin sets a temp password (existing CLI) → user signs in → user changes it via US1 → the temp password no longer works.

- [ ] T022 [P] [US3] `backend/tests/api/test_password_recovery.py` — exercise the recovery composition: set a new password via `domain.users.update_user(new_password=…)` (the path the CLI `user update --password-stdin` already uses), confirm `POST /auth/login` with it succeeds, then `POST /me/password` changes it and a subsequent login with the temp password **401**s. (The CLI itself is a thin wrapper already covered by existing CLI tests.) (FR-011)
- [ ] T023 [US3] Update the root `README.md` Quickstart (FR-016): add a "create your first user" step (`medminder-admin user add … --password-stdin`) and a "set/reset a password" note (`user update … --password-stdin`), then point users to the self-service editor for changing their own password. Keep consistent with `backend/README.md` (stdin-only, 12-char min) without contradiction.

**Checkpoint**: Recovery path proven and documented; a newcomer can reach a working login from the README alone (SC-007).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation sweep, the security gate, and end-to-end validation.

- [ ] T024 [P] Fill `docs/diagrams/profile-password-change.md` with a Mermaid sequence diagram (verify current pw → set hash → revoke all sessions → mint + set new cookie → 204) and add it to `docs/diagrams/README.md`'s list. (Principle IV)
- [ ] T025 [P] Doc sweep (FR-015): add a one-line "surprises" note to `CLAUDE.md` (profile editor = `PATCH /me` + `POST /me/password`; a password change rotates the session and logs out other devices; email stays admin/CLI-only); scan `docs/glossary.md` for any "password set only via CLI" wording and reconcile. Confirm `docs/diagrams/er.md` needs **no** change (no schema delta) and note that in the PR.
- [ ] T026 [P] Complete `specs/007-profile-editor/checklists/security.md` (re-auth, 403-not-401, scoped-to-self, no secrets logged, revoke-then-reissue) and mark every item `[x]`/`[~]` for the merge gate, including the PR Security-considerations line.
- [ ] T027 [P] `frontend/e2e/profile-editor.spec.ts` (Playwright): sign in → open the modal from the nav-bar name → change the name (nav updates) → change the password → a second browser session is logged out; current session survives. Reuse the existing E2E login helper.
- [ ] T028 Run the full gate (serial, near-last): `just lint`, `just typecheck`, `just test` (project ≥ 85 % via `--cov-fail-under=85`; manually confirm no new module < 70 %), `just generate-client` (tree clean), `cd backend && python -m alembic check` (empty diff — confirms no accidental schema change). (FR-013/FR-014)
- [ ] T029 Execute `specs/007-profile-editor/quickstart.md` end-to-end against the rebuilt stack; confirm SC-001…SC-007.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: T001 first; T002–T004 in parallel after.
- **Foundational (Phase 2)**: after Setup — blocks story *frontend*. (Backend story tasks can start in parallel with Foundational.)
- **US1 (Phase 3)**: after Foundational. MVP.
- **US2 (Phase 4)**: after Foundational. Additive on the shared modal; independently testable. (Shares `ProfileDialog.tsx`/`ProfileDialog.test.tsx` with US1 → sequence US2 after US1 to avoid same-file conflicts.)
- **US3 (Phase 5)**: after US1 exists (its recovery test calls `POST /me/password`). Mostly docs.
- **Polish (Phase 6)**: after the targeted stories.

### Within Each User Story
- Tests written and FAIL before implementation.
- Domain before endpoint; backend endpoint before `just generate-client`; generated client before the frontend that consumes it.

### Parallel Opportunities
- Setup: T002/T003/T004 in parallel (T001 first).
- US1: tests T007/T008/T009 in parallel; `useChangePassword` (T013) ∥ nothing blocking once client regen (T012) done; backend (T010→T011) can run while Foundational FE shell is built.
- US2: tests T016/T017 in parallel (T017 after US1 since same test file); `useUpdateProfile` (T020) after regen.
- Polish: T024/T025/T026/T027 in parallel; T028/T029 are gates (serial, last).

## Parallel Example: User Story 1

```bash
# Tests for US1 together (write first, expect red):
Task: "backend/tests/domain/test_change_own_password.py"
Task: "backend/tests/api/test_me_password.py"
Task: "frontend/src/__tests__/ProfileDialog.test.tsx"

# Then backend domain + endpoint, then regen, then FE:
Task: "Add IncorrectPasswordError + change_own_password in domain/users.py"
Task: "Add PasswordChange + POST /me/password in api/me.py"
```

## Implementation Strategy

### MVP First (User Story 1 only)
1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → 4. **STOP & VALIDATE** (change own password; this device stays in; other sessions die; ADR-0011 Accepted) → 5. Demo.

### Incremental Delivery
Setup + Foundational → US1 (MVP) → US2 (name) → US3 (recovery docs) → Polish (diagram, doc sweep, security gate, E2E, quickstart). Each story is a shippable increment.

## Notes
- `[P]` = different files, no dependency on incomplete tasks.
- No DB migration: `alembic check` must stay an empty diff (T028 verifies).
- The 12-char minimum stays in `domain.passwords` (mapped to 422); never hardcoded in the API schema — single source of truth shared with the CLI/login.
- Git is the user's domain — no branch/commit/PR is created by these tasks; the speckit `after_tasks` hook is optional and not auto-run.
