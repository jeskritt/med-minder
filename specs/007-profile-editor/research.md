# Phase 0 Research — Self-Service Profile Editor

Design decisions made before implementation. Each lists what was chosen, why, and what
was rejected. The spec's Clarifications already fixed the **product** decisions (modal
surface, name ≤ 100, wrong-password → 403, no audit in v1, email admin-managed,
current-password re-auth, keep-current-session). This document resolves the two items
the spec explicitly **deferred to plan** — the **endpoint shape** (D1) and the
**keep-current-session mechanism** (D2) — plus the supporting code/test/doc decisions.

---

## D1 — Endpoint shape: two endpoints, not one

**Decision**: Two **root-level** endpoints on the existing `me` router
(`backend/src/medminder/api/me.py`, no `/api/v1` prefix — consistent with `/me` and
`/auth/*`):

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `PATCH /me` | `{ name }` | `200` → `Me` | `401`, `422` |
| `POST /me/password` | `{ current_password, new_password }` | `204` (+ `Set-Cookie`) | `401`, `403`, `422` |

Request schemas (Pydantic, `extra="forbid"`, strict):
- `ProfileUpdate { name: str = Field(min_length=1, max_length=100) }` — a trim+non-empty
  validator rejects whitespace-only.
- `PasswordChange { current_password: str = Field(min_length=1, max_length=1024);
  new_password: str = Field(min_length=1, max_length=1024) }` — the **12-char minimum is
  not hardcoded here**; it stays in `domain.passwords.password_too_short`
  (`MIN_PASSWORD_LENGTH`) and maps to 422 (D4), preserving the single source of truth.

**Rationale**: Name and password have different semantics — only the password path
re-authenticates, revokes sessions, and re-issues a cookie. Splitting them keeps each
contract single-purpose, makes the 403-vs-422 distinction (D4) clean, and matches the
spec's independently testable US1 (password) and US2 (name). Root-level placement
mirrors the existing `/me` and `/auth/login` conventions.

**Alternatives considered**:
- *Single `PATCH /me` taking optional `name` / `current_password` / `new_password`.*
  Rejected — conditional cookie re-issue and a 403 that applies to only one field muddy
  one response shape; harder to test the two stories independently.
- *Prefix under `/api/v1/...`.* Rejected — the current-user surface (`/me`) is
  deliberately root-level alongside `/auth`; following that keeps the client tidy.

---

## D2 — Keep-current-session mechanism: revoke-all-then-reissue

**Decision**: A new domain function performs the credential change and a full session
revoke; the **endpoint** then mints a fresh session and overwrites the cookie — exactly
mirroring `POST /auth/login` (`api/auth.py:92-96`). New in `domain/users.py`:

```python
class IncorrectPasswordError(DomainError): ...

async def change_own_password(
    session: AsyncSession, *, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(user.password_hash, current_password):
        raise IncorrectPasswordError("Current password is incorrect.")
    if password_too_short(new_password):
        raise PasswordTooShortError(...)            # reuse existing message
    user.password_hash = hash_password(new_password)
    await session.flush()
    await revoke_all_user_sessions(session, user_id=user.id)   # reuse existing
```

Endpoint flow for `POST /me/password` (handler injects `response: Response`):
1. `get_current_user` resolves the user (and refreshes the *old* rolling cookie on the
   shared `response`).
2. `change_own_password(...)` verifies, sets the new hash, flushes, revokes **all** of
   the user's sessions (including the one the request arrived on).
3. `create_session(db, user_id=user.id)` mints a brand-new token; sign it and
   `set_session_cookie(response, …)` — this **overwrites** the cookie the dependency
   set, so the client receives the new token (last write wins on the same `Response`).
4. Return `204`. The current device is now authenticated by the new session; every other
   device's cookie maps to a deleted row and fails on its next request.

**Rationale**: Reuses `revoke_all_user_sessions` (already the CLI's password-change
behavior) **unchanged** and the proven login re-issue path, so no new session-domain
code. Rotating to a brand-new token (rather than preserving the old row) is a mild
security plus and avoids a "delete-all-except-one" query. Taking the **authenticated
`User`** as the argument makes cross-user changes structurally impossible (FR-006). The
request authenticates *before* the revoke, so revoking the current row mid-request is
safe.

**Alternatives considered**:
- *`revoke_other_user_sessions(user_id, keep_token_hash)` that preserves the current
  row.* Rejected — needs a new domain function and threads the current token hash down;
  the reissue approach reuses two existing functions and rotates the token.
- *Reuse `update_user(new_password=…)` (which already revokes all sessions).* Rejected —
  it looks the user up by email and does **not** verify the current password; wrapping
  the re-auth around it is muddier than a purpose-built, `User`-scoped function. Both
  paths still share the `revoke_all_user_sessions` / `hash_password` primitives (DRY at
  the primitive level).

---

## D3 — Display-name change path: reuse `update_user`

**Decision**: `PATCH /me` calls the existing
`domain.users.update_user(session, email=user.email, new_name=body.name)` and returns the
refreshed `Me`. Length/non-empty validation lives at the Pydantic boundary
(`ProfileUpdate`, mirroring `ScheduleWriteBody`'s `Field(max_length=200)` pattern).

**Rationale**: `update_user` already updates the name, flushes, and returns the `User`;
passing the **authenticated user's own** email keeps it scoped to self and avoids a new
function. No session effects (FR-009).

**Alternatives considered**:
- *New `set_display_name(...)` domain function.* Rejected — `update_user` already does
  exactly this; adding a parallel path violates DRY for no benefit.
- *Enforce the 100-char cap in the domain.* Rejected — boundary (Pydantic) validation is
  the established pattern for field shape (schedules/medications) and yields the 422 the
  spec wants automatically.

---

## D4 — Error transport: 403 (wrong current pw) vs 422 (too short), never 401

**Decision**: In `POST /me/password` map domain errors:
- `IncorrectPasswordError` → **`HTTPException(403, "Current password is incorrect.")`**
- `PasswordTooShortError` → **`HTTPException(422, <existing min-length message>)`**

`401` is reserved for `get_current_user` (unauthenticated / expired) and is the only
status the frontend treats as "session expired → bounce to login" (see
`lib/api.ts` middleware, which excludes `/me` and `/auth`). `PATCH /me` validation
failures (empty/over-length name) are ordinary Pydantic `422`s.

**Rationale**: Directly implements the clarified FR-003. A wrong current password is an
authorization-of-action failure, not a malformed request (422) and not a session failure
(401) — using 401 would log the user out mid-edit. Keeping the 12-char rule in the domain
(not Pydantic `min_length=12`) preserves `MIN_PASSWORD_LENGTH` as the single source of
truth shared with the CLI and login.

**Alternatives considered**:
- *Wrong current password → 422.* Rejected by clarification — conflates a failed
  credential check with input validation and would share the new-password error path.
- *Wrong current password → 401.* Rejected — the client auto-redirects on 401, which is
  exactly the wrong UX for an authenticated user mistyping their old password.

---

## D5 — Frontend surface: a modal opened from the nav bar

**Decision**: New `frontend/src/components/profile/ProfileDialog.tsx`, a modal toggled by
local state in `NavBar.tsx` (the current `<span>{user.name}</span>` at `NavBar.tsx:56`
becomes a `<button>`). The dialog has two independent sections, each a React Hook
Form + Zod form (mirroring `MedicationForm`):
- **Profile** — `name` (Zod: trimmed, 1–100). Submits via `useUpdateProfile` (`PATCH
  /me`); `onSuccess` invalidates `["me"]` so the nav bar updates without reload (FR-008).
- **Change password** — `current_password`, `new_password` (Zod: min 12 to give instant
  client feedback; the server remains authoritative). Submits via `useChangePassword`
  (`POST /me/password`). On `403` set a field error on `current_password`; on `422` show
  the new-password message — reusing the `serverError` pattern from `MedicationForm`. The
  cookie rotates transparently, so the user stays signed in; optionally invalidate
  `["me"]`.

Both mutations live in `lib/auth.ts` next to `useCurrentUser`/`useLogout`. Follow the
existing modal pattern in `frontend/src/components/UntakeConfirmModal.tsx` — a plain
conditional-render dialog (`if (!open) return null`) with `role="dialog"`,
`aria-modal="true"`, an `aria-label`, a `fixed inset-0 z-50 … bg-black/40` overlay and a
white card; **no native `<dialog>`** (jsdom-friendly). Match that surface for
consistency; a focus trap / Escape-to-close is an *optional* enhancement the existing
modals do not implement.

**Rationale**: Honors the clarified "modal, not a route" decision and avoids the
TanStack dotted-route parent-layout requirement. Reuses the project's established
RHF + Zod + `serverError` form pattern and `openapi-fetch` typed client, so the surface
is small and consistent.

**Alternatives considered**:
- *Dedicated `/profile` route.* Rejected per clarification (heavier; needs a parent
  `<Outlet />` layout).
- *One combined form/submit for name + password.* Rejected — mirrors the split-endpoint
  decision (D1); independent sections map cleanly to the 403/422 split and the two user
  stories.

---

## D6 — Test layout & coverage

**Decision**:

| File | Scope | Notes |
|---|---|---|
| `backend/tests/domain/test_change_own_password.py` | Domain | Correct current pw → new hash verifies + all sessions deleted; wrong pw → `IncorrectPasswordError`, hash + sessions unchanged; `< 12` → `PasswordTooShortError`, no mutation. |
| `backend/tests/api/test_me_password.py` | API integration (US1) | `POST /me/password`: correct → 204 and a fresh cookie that still authenticates while a *second* pre-existing session for the same user now 401s on `/me`; wrong current → 403; too-short → 422; unauthenticated → 401. |
| `backend/tests/api/test_me_profile.py` | API integration (US2) | `PATCH /me` happy path (200, `Me.name` updated) + empty/whitespace/over-100 → 422; **a body with extra fields (`email`/`role`) rejected (422, `extra="forbid"`) — FR-010**; unauthenticated → 401. |
| `backend/tests/api/test_password_recovery.py` | API integration (US3) | Admin-set password via `update_user(new_password=…)` → login works → `POST /me/password` changes it → temp-password login now 401s (FR-011). |
| `frontend/src/__tests__/ProfileDialog.test.tsx` | Component | Opens from the nav-bar name; name save calls `PATCH /me` + reflects on success; password save calls `POST /me/password`; a 403 surfaces on the current-password field; a too-short new password is blocked client-side. |

Reuse `backend/tests/api/conftest.py` (`AsyncClient` + `ASGITransport`, login helper,
shared transactional session) and the real-Postgres rollback fixture. Project coverage
stays ≥ 85% (FR-014); the new `change_own_password` is small and fully covered by the
domain test.

**Rationale**: The API test for "other sessions die, this one survives" is the testable
core of FR-005/SC-003; the wrong-pw 403 and too-short 422 tests pin FR-003/D4. Mirrors
the existing `tests/api/test_me.py` and `tests/api/test_schedules_crud.py` patterns.

**Alternatives considered**:
- *Only API tests (skip the domain test).* Rejected — `change_own_password` is the
  security-relevant unit; a no-DB-needed domain test is cheap and pins the revoke + verify
  behavior independently of transport.

---

## D7 — Docs, ADR & README (FR-015 / FR-016, executed in implement phase)

**Decision**:
- **ADR-0011 — "Self-service credential management"** (`docs/adr/0011-…md`), Proposed →
  **Accepted** with the PR. Captures: self-service password change with current-password
  re-auth, the 403/422/never-401 transport, and revoke-all-then-reissue session handling;
  records the no-audit-in-v1 decision and email-stays-admin-managed scope, with the
  Principle I threat note. Next free ADR number is **0011** (0010 is the highest).
- **Sequence diagram** `docs/diagrams/profile-password-change.md` — the
  verify → set-hash → revoke-all → reissue-cookie flow (Principle IV "key user flows").
- **ER diagram unchanged** — state this explicitly in the PR; no schema delta.
- **`README.md` Quickstart** gains a create-first-user + set/reset-password step using
  the existing CLI, pointing to the self-service editor afterward (FR-016); keep
  consistent with `backend/README.md` (stdin-only, 12-char min) without contradiction.
- **`CLAUDE.md`** gains a one-line "surprises" note: profile editor = `PATCH /me` +
  `POST /me/password`; password change rotates the session (other devices logged out);
  email is admin/CLI-only.
- **`checklists/security.md`** — required merge gate for this security-sensitive feature
  (Principle IV); generate with `/speckit-checklist`.

**Rationale**: Satisfies the constitution's "Documented decisions" and the spec's doc
sweep (FR-015/FR-016) and "Check docs/adr before speccing" lineage. These are
documentation tasks scheduled in `/speckit-tasks`, not part of `/speckit-plan` output.

**Alternatives considered**:
- *Fold the decision into an existing ADR (e.g., ADR-0001 sessions).* Rejected — a
  distinct, security-relevant decision warrants its own ADR per Principle IV.
