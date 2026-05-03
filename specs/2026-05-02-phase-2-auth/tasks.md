---
description: "Tasks for Phase 2 — Auth (login / logout)"
---

# Tasks: Phase 2 — Auth (login / logout)

**Input**: Design documents from `/specs/2026-05-02-phase-2-auth/`
**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/auth.openapi.yaml`, `quickstart.md`

**Tests**: Tests are explicitly required by `spec.md` (each user story has an Independent Test plus Acceptance Scenarios) and by `plan.md` §2.5 (which enumerates concrete test files and the Argon2id timing assertion). Test tasks are included.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: Which user story this task belongs to (US1–US7). Setup, Foundational, and Polish tasks do not carry a story label.
- All paths are repository-relative.

## Path Conventions

- Web app: `backend/src/medminder/…`, `backend/tests/…`, `frontend/src/…`, `frontend/src/__tests__/…`, `docs/…`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pull in the new dependencies and add the cookie-related settings the rest of the phase will read.

- [ ] T001 Add `itsdangerous>=2.2.0,<3.0` to `[project.dependencies]` in `backend/pyproject.toml`.
- [ ] T002 Add `freezegun>=1.5.0,<2.0` to `[project.optional-dependencies].dev` in `backend/pyproject.toml`.
- [ ] T003 [P] Extend `backend/src/medminder/settings.py` with `SESSION_SECRET: str` (required when `env != "development"`, with a documented dev-only fallback), `SESSION_COOKIE_NAME: str = "mm_session"`, and a derived `session_cookie_secure` property (true when `env != "development"`).
- [ ] T004 [P] Document the new `SESSION_SECRET` (dev fallback + production requirement) and link the forthcoming login sequence diagram in `backend/README.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting domain + HTTP scaffolding that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Implement `backend/src/medminder/api/deps.py` with `get_session` (yields an `AsyncSession` from `app.state.session_factory`) and the `get_current_user` dependency that reads the `mm_session` cookie via `itsdangerous.URLSafeTimedSerializer.loads(...)`, calls `domain.sessions.authenticate_token`, raises `HTTPException(401)` on miss / expired / tampered, and refreshes the `Set-Cookie` `Max-Age` on the outgoing response (FR-003 + FR-009).
- [ ] T006 Implement `backend/src/medminder/domain/sessions.py` with `SESSION_LIFETIME = timedelta(days=30)`, `generate_token() -> str` (`secrets.token_urlsafe(32)`), `hash_token(plaintext) -> str` (SHA-256 hex), `async create_session(session, user_id) -> tuple[Session, str]` returning the row + plaintext token, `async authenticate_token(session, plaintext_token) -> User | None` (lookup by `token_hash`, reject when `expires_at <= now()` without mutation, otherwise mutate `expires_at = now() + SESSION_LIFETIME` and return the `User`), `async delete_session_by_token_hash(session, token_hash) -> bool`, and `async revoke_all_user_sessions(session, user_id) -> int`.
- [ ] T007 [P] Implement `backend/src/medminder/domain/auth.py` with the `LoginOutcome` enum (`success | wrong_password | unknown_email | soft_deleted`), a module-level `DUMMY_HASH` (a real Argon2id hash precomputed at import to keep failure timings uniform — D5), and `async attempt_login(session, *, email, password, ip, user_agent) -> tuple[User | None, LoginOutcome]` that runs Argon2id verification on every path (against the user hash on found, against `DUMMY_HASH` otherwise) and emits exactly one INFO log line per attempt with `outcome`, `user_id` (or `None`), `source_ip`, `user_agent` (FR-019, no email / password / token material).
- [ ] T008 [P] Create empty `APIRouter()` instances in `backend/src/medminder/api/auth.py` and `backend/src/medminder/api/me.py`, then wire `backend/src/medminder/app.py` to `include_router` both. T011, T012, and T021 attach handlers to these router instances; scaffolding the registration here means handlers added later light up automatically without further `app.py` edits.
- [ ] T009 [P] Unit tests `backend/tests/domain/test_sessions.py` covering token mint/hash, create + lookup round-trip, rolling-expiry mutation on a successful authenticate, expired-row rejection without mutation, single delete by hash, bulk delete by user_id.
- [ ] T010 [P] Unit tests `backend/tests/domain/test_auth.py` covering all four `LoginOutcome` paths, dummy-hash timing parity, and the FR-019 log shape via `caplog` (assert no email / password / token / hash substring appears in any record).

**Checkpoint**: Domain layer + auth dependency + router scaffolding ready — story phases can now begin.

---

## Phase 3: User Story 1 — Successful login (Priority: P1) 🎯 MVP

**Goal**: A registered user submits credentials on `/login`, receives a signed `mm_session` cookie, lands on the stub `/medications` page, and `GET /me` returns `{ id, name, role }`.

**Independent Test**: Seed a user via `medminder-admin user add`, navigate to `/login`, submit the seeded credentials, observe the redirect to `/medications`, observe one new `sessions` row, observe the cookie attributes (HttpOnly, SameSite=Lax, persistent), and observe `/api/me` returning the user's id/name/role with the cookie present.

### Implementation

- [ ] T011 [US1] Implement `POST /auth/login` in `backend/src/medminder/api/auth.py` per `contracts/auth.openapi.yaml` — pydantic `LoginRequest` (email lowercased + trimmed, password not normalized), call `domain.auth.attempt_login`, on success delete any pre-existing session keyed by the inbound cookie (FR-016), `create_session`, sign the plaintext token with `itsdangerous`, set the `mm_session` cookie (`HttpOnly`, `SameSite=Lax`, `Max-Age=2592000`, `Secure` from settings), return `204 No Content`. Reuses `domain.users.get_user_by_email(include_deleted=False)` (FR-014) and `domain.passwords.verify_password` (FR-013) inside `attempt_login`.
- [ ] T012 [US1] Implement `GET /me` in `backend/src/medminder/api/me.py` — depends on `get_current_user`, returns the `Me` schema (`id`, `name`, `role`); the `get_current_user` dependency from T005 already refreshes the `Set-Cookie` `Max-Age` (FR-003 + FR-009 cookie half, FR-018).
- [ ] T013 [US1] Integration test `backend/tests/api/test_login.py::test_login_success` — seeds a user, posts credentials, asserts 204, asserts exactly one new row in `sessions` for the user, asserts the response `Set-Cookie` carries `HttpOnly`, `SameSite=Lax`, `Max-Age=2592000`, and `Secure` matches `settings.session_cookie_secure`.
- [ ] T013a [US1] Integration test `backend/tests/api/test_login.py::test_relogin_replaces_existing_session` — log in user A and capture the resulting `mm_session` cookie and the new `sessions.id`. Submit a second valid login for user A with the cookie still attached on the inbound request. Assert: the original `sessions` row is gone, exactly one new `sessions` row exists for user A (different `id`), the response carries a fresh `Set-Cookie` whose signed value differs from the original, and `GET /me` with the new cookie succeeds while `GET /me` with the original cookie returns 401 (FR-016).
- [ ] T013b [US1] Integration test `backend/tests/api/test_login.py::test_failed_relogin_preserves_existing_session` — log in user A. Submit a second login carrying user A's cookie but with the wrong password. Assert: response is 401 with the generic FR-004 body, the original `sessions` row is still present with `expires_at` unchanged, no `Set-Cookie` is set on the failure response (research D9 — a typo must not log the user out).
- [ ] T014 [P] [US1] Integration test `backend/tests/api/test_me.py::test_me_with_valid_session` — round-trips login → `GET /me`, asserts 200 with the expected `{ id, name, role }`, asserts the response refreshes the `mm_session` `Set-Cookie`.
- [ ] T015 [US1] Run `just generate-client` and commit the regenerated `frontend/src/api/v1.d.ts` so subsequent frontend tasks can import the new operations.
- [ ] T016 [US1] Modify `frontend/src/lib/api.ts` — set `credentials: "include"` on the `openapi-fetch` client; add a response middleware that, on a 401 from any non-`/auth/*` endpoint, calls `queryClient.clear()` and `router.navigate({ to: "/login" })` (FR-008).
- [ ] T017 [P] [US1] Create `frontend/src/lib/auth.ts` with `useCurrentUser()` (TanStack Query around `GET /me`) and `useLogout()` (TanStack mutation around `POST /auth/logout`).
- [ ] T018 [US1] Create `frontend/src/routes/login.tsx` — react-hook-form + zod schema (email, password); on success `queryClient.invalidateQueries({ queryKey: ["me"] })` then `navigate({ to: "/medications" })`; renders the generic FR-004 error (`"Email or password is incorrect."`) on any 401 from `/auth/login`.
- [ ] T019 [P] [US1] Create `frontend/src/routes/medications.tsx` — Phase 2 stub body indicating "Phase 3 will populate this list"; `beforeLoad` awaits `GET /me` and throws `redirect({ to: "/login" })` on 401 (FR-017). The logout button placeholder is wired in T024.
- [ ] T020 [P] [US1] Vitest `frontend/src/__tests__/login.test.tsx` — renders the form, validates required fields, submits successfully and asserts the `navigate` to `/medications`, asserts the generic error renders on a mocked 401.

**Checkpoint**: Login → cookie → protected `/me` → stub `/medications` happy path is fully exercised.

---

## Phase 4: User Story 2 — Logout (Priority: P1)

**Goal**: An authenticated user clicks logout, the server `sessions` row is deleted, the cookie is cleared, the user lands on `/login`, and a replayed logout is a no-op.

**Independent Test**: From an authenticated browser, click logout. Confirm the `sessions` row is gone, the response clears the cookie, the user lands on `/login`, and a second logout call still returns 204.

### Implementation

- [ ] T021 [US2] Implement `POST /auth/logout` in `backend/src/medminder/api/auth.py` — read the `mm_session` cookie (best-effort; ignore signature failure), `delete_session_by_token_hash`, set the clearing cookie (`mm_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax` plus `Secure` per settings), return 204; idempotent under repeated calls (FR-006).
- [ ] T021b [US2] Run `just generate-client` and commit the regenerated `frontend/src/api/v1.d.ts` (now including the `auth_logout` operation). Required before T024 so the frontend can import the operation. Also re-confirms the OpenAPI-drift CI gate stays green after the new endpoint.
- [ ] T022 [US2] Integration test `backend/tests/api/test_logout.py::test_logout_deletes_row_and_clears_cookie` — login, logout, assert 204, assert the `sessions` row is gone, assert the `Set-Cookie` clears the cookie.
- [ ] T023 [P] [US2] Integration test `backend/tests/api/test_logout.py::test_logout_is_idempotent` — call logout twice; the second call still returns 204 with the clearing cookie.
- [ ] T024 [US2] Modify `frontend/src/routes/medications.tsx` to render a logout button wired to `useLogout`; on success call `queryClient.clear()` then `navigate({ to: "/login" })`.

**Checkpoint**: Login + logout together complete the user-facing session lifecycle.

---

## Phase 5: User Story 3 — Failed login is timing-safe and uniform (Priority: P1)

**Goal**: Wrong-password, unknown-email, and soft-deleted-user attempts all return identical body + 401 status with observably identical timing, and never log PII.

**Independent Test**: Submit each of the three failure modes; assert identical bodies, statuses, and that the wall-clock p95 delta across 100 trials stays below 50 ms (SC-002).

### Implementation

- [ ] T025 [US3] Integration test `backend/tests/api/test_login.py::test_failed_login_outcomes_have_identical_body_and_status` — wrong password, unknown email, and soft-deleted user all return 401 with `{"detail":"Email or password is incorrect."}` and no `Set-Cookie`.
- [ ] T026 [US3] Integration test `backend/tests/api/test_login.py::test_failed_login_outcomes_have_uniform_timing` — 100 paired trials per pair against the real Argon2id verifier (matching SC-002), asserts the wall-clock p95 delta across {wrong-password, unknown-email, soft-deleted} is < 50 ms (mark `@pytest.mark.slow`).
- [ ] T027 [P] [US3] Integration test `backend/tests/api/test_login.py::test_log_line_omits_pii` — drives all four outcomes (success + the three failures) and uses `caplog` to assert no email substring, no password substring, no plaintext token, and no token-hash substring appears in any FR-019 log record.

**Checkpoint**: User-enumeration oracle is closed; logs are scrubbed (Constitution Principle I satisfied for this surface).

---

## Phase 6: User Story 4 — Auth-required route guards (Priority: P1)

**Goal**: Missing, tampered, or expired cookies all yield 401 from any protected endpoint; an unauthenticated browser cannot reach a protected frontend route.

**Independent Test**: Hit `/api/me` with no cookie / a tampered cookie / an expired session — each returns 401. Navigate to `/medications` without a session — redirected to `/login`. With a valid session — `/medications` loads.

### Implementation

- [ ] T028 [US4] Integration test `backend/tests/api/test_me.py::test_me_returns_401_without_cookie`.
- [ ] T029 [P] [US4] Integration test `backend/tests/api/test_me.py::test_me_returns_401_with_tampered_cookie` — a cookie that fails the `itsdangerous` signature check produces 401 with the same body as the no-cookie case.
- [ ] T030 [P] [US4] Integration test `backend/tests/api/test_me.py::test_me_returns_401_with_expired_session_and_does_not_extend` — uses `freezegun` to advance past `expires_at`; asserts 401 and asserts the row's `expires_at` is unchanged.
- [ ] T031 [P] [US4] Vitest `frontend/src/__tests__/medications.guard.test.tsx` — unauthenticated navigation to `/medications` redirects to `/login`; the protected content does not render.

**Checkpoint**: The cookie does real work on both ends of the wire.

---

## Phase 7: User Story 5 — Forced logout on admin password change (Priority: P2)

**Goal**: When the admin CLI changes a user's password, every `sessions` row for that user is deleted in the same transaction (FR-010).

**Independent Test**: Log in user X in browser A, run `medminder-admin user update <id> --password ...`, observe browser A receives 401 on its next request and lands on `/login`; assert all `sessions` rows for user X are gone.

### Implementation

- [ ] T032 [US5] Modify `backend/src/medminder/cli/users.py` — in the `update` command, when `new_password is not None`, call `domain.sessions.revoke_all_user_sessions(session, user.id)` after `update_user(...)` inside the same `async with session.begin()` transaction.
- [ ] T033 [US5] Test `backend/tests/cli/test_user_commands.py::test_update_password_revokes_sessions` — seed a user with two sessions, run `user update --password-stdin`, assert 0 `sessions` rows remain for that user.
- [ ] T033b [P] [US5] Integration test `backend/tests/api/test_revocation.py::test_password_change_invalidates_existing_cookies` — log in user X via `POST /auth/login` and capture the cookie, then run the same in-transaction sequence T032 wires (`update_user(..., new_password=...)` followed by `revoke_all_user_sessions(...)` inside one `async with session.begin()`). Assert `GET /me` with the original cookie returns 401 (SC-004).
- [ ] T034 [P] [US5] Test `backend/tests/cli/test_user_commands.py::test_update_name_only_does_not_revoke_sessions` — seed a user with two sessions, run `user update --name "New Name"`, assert both `sessions` rows are still present (guards against over-broad revocation).

**Checkpoint**: Half #1 of the constitution's revocation guarantee is in place.

---

## Phase 8: User Story 6 — Forced logout on admin soft-delete (Priority: P2)

**Goal**: When the admin CLI soft-deletes a user, every `sessions` row for that user is deleted in the same transaction (FR-011), and a fresh login attempt for that email collapses to the unknown-email response via FR-005.

**Independent Test**: Log in user X in browser A, run `medminder-admin user delete <id>`, observe all `sessions` rows for user X are gone, browser A receives 401 on its next request, and a fresh login for that email returns the same generic error as an unknown email.

### Implementation

- [ ] T035 [US6] Modify `backend/src/medminder/cli/users.py` — in the `delete` command, after `soft_delete_user(...)` call `domain.sessions.revoke_all_user_sessions(session, user.id)` inside the same `async with session.begin()` transaction.
- [ ] T036 [US6] Test `backend/tests/cli/test_user_commands.py::test_delete_revokes_sessions` — seed a user with two sessions, run `user delete`, assert 0 `sessions` rows remain.
- [ ] T036b [P] [US6] Integration test `backend/tests/api/test_revocation.py::test_soft_delete_invalidates_existing_cookies` — log in user X via `POST /auth/login` and capture the cookie, then run the same in-transaction sequence T035 wires (`soft_delete_user(...)` followed by `revoke_all_user_sessions(...)` inside one `async with session.begin()`). Assert `GET /me` with the original cookie returns 401 (SC-004).
- [ ] T037 [P] [US6] Integration test `backend/tests/api/test_login.py::test_soft_deleted_user_login_matches_unknown_email` — soft-delete a previously-existing user via the CLI path, then attempt login; assert the response is byte-identical to the unknown-email case.

**Checkpoint**: Constitution revocation guarantee is fully satisfied (both halves).

---

## Phase 9: User Story 7 — Rolling 30-day session expiry (Priority: P2)

**Goal**: Each authenticated request extends `sessions.expires_at` to "now + 30 days"; a session idle for more than 30 days is rejected and not extended (FR-009).

**Independent Test**: Create a session, advance the clock by 29 days, issue an authenticated request, observe success and that `expires_at` advanced. Then advance another 31 days without any request, issue a request, observe 401 and that the row is left untouched.

### Implementation

- [ ] T038 [US7] Test `backend/tests/api/test_rolling_expiry.py::test_rolling_expiry_extends_at_29_days` — `freezegun.freeze_time` to T+29d, `GET /me` succeeds, asserts the row's `expires_at` is now > the pre-request value.
- [ ] T039 [P] [US7] Test `backend/tests/api/test_rolling_expiry.py::test_expired_session_is_rejected_and_not_extended` — `freezegun.freeze_time` to T+31d, `GET /me` returns 401, asserts the row's `expires_at` is unchanged from before the request.

**Checkpoint**: Production session-lifetime policy is committed and enforced.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, gates, and the manual smoke pass.

- [ ] T040 Add `docs/diagrams/login-sequence.md` — Mermaid `sequenceDiagram` covering the login → cookie → `/me` flow (FR-015, SC-007); link from `backend/README.md`.
- [ ] T041 [P] Run `just lint` and address any findings introduced by Phase 2 code.
- [ ] T042 [P] Run `just typecheck` (`mypy --strict` + `tsc --noEmit`) and address any findings.
- [ ] T043 [P] Run `just test` and confirm the backend coverage gate (≥ 85 %) stays green.
- [ ] T044 Run the `quickstart.md` end-to-end smoke test against `just dev` (steps 0–8). During step 2, time the login → `/medications` round trip (form submit → DOMContentLoaded on `/medications`) and record the value in the PR description; assert ≤ 2 s as the SC-001 verification.
- [ ] T045 During the smoke test, run `docker compose logs backend | grep -iE 'password|email|token|hash'` and confirm zero hits (SC-006).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phases 3–9)**: All depend on Foundational. US1 → US2 → US3 → US4 are sequenced because they edit overlapping HTTP modules; US5, US6, US7 are independent of one another after Foundational.
- **Polish (Phase 10)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only.
- **US2 (P1)**: Depends on US1 (logout edits `api/auth.py` and the `/medications` route added in US1). T024 (frontend logout button) depends on T021b (OpenAPI client regen).
- **US3 (P1)**: Depends on US1 (failure-mode tests target the `/auth/login` endpoint added in US1).
- **US4 (P1)**: Depends on US1 (route-guard tests target `/me` and `/medications` added in US1; tampered/expired tests rely on the cookie machinery in T005).
- **US5 (P2)**: Depends on Foundational only (uses `revoke_all_user_sessions` from T006). Independent of US1–US4.
- **US6 (P2)**: Depends on Foundational only. Independent of US5 and US7.
- **US7 (P2)**: Depends on Foundational only (uses the rolling-expiry mutation in T006). Independent of US5 and US6.

### Within Each User Story

- Backend handler before the integration test that targets it.
- Frontend `lib/api.ts` changes before frontend route code.
- `just generate-client` (T015 in US1, T021b in US2) before any frontend code that imports the newly added operations.
- Models / domain helpers before the services / endpoints that use them (mostly already in Foundational).

### Parallel Opportunities

- All Setup [P] tasks (T003, T004) can run in parallel.
- All Foundational [P] tasks (T007, T008, T009, T010) can run in parallel — `domain/auth.py`, `app.py` router scaffolding, and the two test files are independent files.
- Within US1: T014, T017, T019, T020 marked [P] can run in parallel once their non-[P] predecessors land. T013a and T013b depend on T011 only (same file as T013 → not [P] with each other or with T013).
- Within US3: T027 can run in parallel with T025 / T026.
- Within US4: T029, T030, T031 can all run in parallel.
- Within US5: T033b and T034 can both run in parallel with T033.
- Within US6: T036b and T037 can both run in parallel with T036.
- Within US7: T039 in parallel with T038.
- Polish: T041, T042, T043 in parallel; T044 / T045 sequential at the end.
- US5, US6, US7 can be parallelized across developers after Foundational.

---

## Parallel Example: User Story 1

```bash
# Once T011 (POST /auth/login), T012 (GET /me), T015 (generate-client), T016 (api.ts), and T018 (login route) are done,
# launch the remaining US1 [P] tasks together:
Task: "Integration test backend/tests/api/test_me.py::test_me_with_valid_session"     # T014
Task: "Create frontend/src/lib/auth.ts with useCurrentUser and useLogout"             # T017
Task: "Create frontend/src/routes/medications.tsx (stub + beforeLoad guard)"          # T019
Task: "Vitest frontend/src/__tests__/login.test.tsx"                                  # T020
```

## Parallel Example: User Story 4

```bash
# After Foundational + US1, launch US4 entirely in parallel:
Task: "Integration test test_me_returns_401_without_cookie"                           # T028
Task: "Integration test test_me_returns_401_with_tampered_cookie"                     # T029
Task: "Integration test test_me_returns_401_with_expired_session_and_does_not_extend" # T030
Task: "Vitest medications.guard.test.tsx"                                             # T031
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup.
2. Phase 2: Foundational (CRITICAL — blocks every story).
3. Phase 3: US1.
4. **STOP and VALIDATE**: smoke-test login → `/medications` → `/me` end-to-end.
5. Demo if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. + US1 → MVP login (demo).
3. + US2 → user-facing session lifecycle complete.
4. + US3 → enumeration oracle closed.
5. + US4 → access-control boundary enforced.
6. + US5, US6 → admin revocation guarantee complete.
7. + US7 → production lifetime policy committed.
8. Phase 10: documentation + gates + smoke.

### Parallel Team Strategy

After Foundational lands:

- Developer A: US1 → US2 → US3 → US4 (single serial track on the auth HTTP surface).
- Developer B: US5.
- Developer C: US6.
- Developer D: US7.

All converge on Phase 10 (docs + gates).

---

## Notes

- `[P]` tasks edit different files and have no dependencies on incomplete tasks.
- `[Story]` labels appear only on Phase 3–9 tasks; Setup, Foundational, and Polish do not carry them.
- No new Alembic migration is anticipated this phase — `data-model.md` records that the existing `users` and `sessions` tables already have the columns Phase 2 needs.
- Phase 2+ uses the strict spec-kit artifact set; do not generate the legacy `requirements.md` / `validation.md` triplet (per `CLAUDE.md`).
- Avoid: vague tasks, same-file conflicts marked `[P]`, cross-story dependencies that break independence beyond those documented above.
