# Phase 0 Research — In-App Admin User Management

Design decisions made before implementation. Each lists what was chosen, why, and what was
rejected. The spec's Clarifications already fixed the **product** decisions (both password
options; active-only list, no restore; add an audit log; voluntary rotation; successes-only
audit; read-only self-row). This document resolves the **technical** decisions the spec left
to plan: the authorization gate, the endpoint surface, how the id-keyed API reuses the
email-keyed domain, the guards, the temp-password generator, the audit table, the frontend
surface, the test layout, and the doc/ADR sweep.

---

## D1 — Authorization gate: a new `require_admin` dependency

**Decision**: Add `require_admin` to `backend/src/medminder/api/deps.py`:

```python
async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin only.")
    return user
```

Every `/api/v1/users` endpoint depends on `require_admin` instead of `get_current_user`. A
non-admin (authenticated) gets **403**; an unauthenticated caller still gets **401** from the
inner `get_current_user`. The frontend `/admin` route additionally guards in `beforeLoad`
(reads `/me`, redirects non-admins away) and the nav link is hidden for non-admins — but the
server gate is the real boundary (FR-001/FR-015/SC-003).

**Rationale**: Smallest possible addition; composes with the existing cookie/session auth;
keeps least-privilege enforcement server-side (UI hiding is convenience, not security).
Returning the admin `User` lets handlers record the **actor** for the audit log without a
second lookup.

**Alternatives considered**:
- *Per-handler role check inside each endpoint.* Rejected — repeats the check and is easy to
  forget on a new endpoint; a dependency is declarative and uniform.
- *404 instead of 403 for non-admins (resource-hiding).* Rejected — single-tenant, low value;
  a clear 403 is better DX and the route/nav are already admin-gated client-side.

---

## D2 — Endpoint surface: a new `/api/v1/users` router

**Decision**: New router `backend/src/medminder/api/users.py`, `prefix="/api/v1/users"`,
`tags=["users"]`, all behind `require_admin`:

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /api/v1/users` | — | `200` → `{ items: UserOut[] }` (active only) | `401`, `403` |
| `POST /api/v1/users` | `UserCreate` | `201` → `CreatedUser { user, temporary_password? }` | `401`, `403`, `409`, `422` |
| `PATCH /api/v1/users/{user_id}` | `UserUpdate` | `200` → `UserOut` | `401`, `403`, `404`, `409`, `422` |
| `POST /api/v1/users/{user_id}/password` | `PasswordSet` | `200` → `{ temporary_password? }` | `401`, `403`, `404`, `422` |
| `DELETE /api/v1/users/{user_id}` | — | `204` | `401`, `403`, `404`, `409` |
| `GET /api/v1/users/audit-log` | — | `200` → `{ items: AuditEntryOut[] }` | `401`, `403` |

`UserOut`: `{ id, email, name, role, created_at }` (active list). `UserCreate`:
`{ email, name, role, password? , generate? }`. `UserUpdate`: `{ name?, email?, role? }`
(at least one; `extra="forbid"`). `PasswordSet`: `{ password? , generate? }`. Password reset
is a **separate endpoint** (not folded into `PATCH`) because it has distinct semantics —
session revocation and the type-or-generate one-time-secret response — mirroring the Phase 7
split of `POST /me/password` from `PATCH /me`.

Route ordering: declare `GET /audit-log` **before** `GET/PATCH/DELETE /{user_id}`; since
`{user_id}` is a UUID path param, `audit-log` would not match the UUID converter anyway, but
ordering makes intent explicit.

**Rationale**: `/api/v1/...` is the established prefix for resource routers (medications,
schedules-crud, reminders); `/me` and `/auth` stay root-level for the self/auth surface. A
dedicated password endpoint keeps the 409/422 mapping and the one-time-secret response clean.

**Alternatives considered**:
- *Fold password reset into `PATCH` with an optional `password` field.* Rejected — conflates
  a session-revoking, secret-returning action with plain field edits (same reasoning as
  ADR-0007/D1 for the profile editor).
- *Put audit-list on a separate `/api/v1/audit-log` router.* Acceptable, but nesting under
  `users` keeps the admin surface in one file/tag; revisit only if other audit kinds appear.

---

## D3 — Id-keyed API over email-keyed domain: resolve by id, then reuse

**Decision**: The REST surface addresses users by **`{user_id}` (UUID)** — stable, and email
is itself editable. The existing domain functions key on **email**
(`update_user(email=…)`, `soft_delete_user(email=…)`). Bridge them with a new
`get_user_by_id(session, *, user_id, include_deleted=False)` in `domain/users.py`; the
admin-scoped domain helpers resolve the target by id, run the guards, then delegate to the
existing email-keyed functions using the resolved user's current email:

```python
async def admin_update_user(session, *, actor, user_id, new_name=None,
                            new_email=None, new_role=None) -> User:
    target = await get_user_by_id(session, user_id=user_id)        # 404 if None
    _forbid_self(actor, target)                                    # SelfActionError
    await _guard_last_admin_on_role_change(session, target, new_role)
    user = await update_user(session, email=target.email,          # reuse (dup-email, flush)
                             new_name=new_name, new_email=new_email, new_role=new_role)
    await record_admin_action(session, actor_id=actor.id, action=…, target_user_id=user.id,
                              details={"fields": [...]})
    return user
```

The id→email resolve costs one extra in-transaction lookup but reuses `update_user`'s
validated path (case-insensitive duplicate-email check incl. soft-deleted, flush) and
`soft_delete_user`'s revoke-on-delete — no duplicated persistence logic (Principle III).

**Rationale**: Keeps the public contract REST-stable (id) while honoring "reuse the shared
domain" — the CLI (email-keyed) and the app (id-keyed-then-resolved) converge on the same
mutation primitives. The guards and audit write wrap those primitives in one place.

**Alternatives considered**:
- *Refactor `update_user`/`soft_delete_user` to accept a pre-resolved `User` or id.* Rejected
  for now — larger blast radius on CLI call sites for marginal gain; the resolve-then-reuse
  bridge is localized and the double-lookup is negligible at this scale.
- *Address users by email in the path.* Rejected — emails are editable and need URL-encoding;
  UUIDs are the stable identifier used everywhere else.

---

## D4 — Guards: no-self-action and last-admin (net-new domain logic)

**Decision**: Two guards, both pure-ish domain checks (one needs a COUNT query), unit-testable
without HTTP:

- `count_active_admins(session) -> int` — `SELECT count(*) FROM users WHERE role='admin' AND
  deleted_at IS NULL`. To hold the guard under concurrent requests (**FR-021**), the
  deactivate/demote helpers take a row lock on the admin set (`... FOR UPDATE`) inside the
  request transaction before counting, so two simultaneous removals of the last two admins
  serialize rather than both passing the check.
- **No self-action**: `admin_*` helpers raise `SelfActionError` (→ **403**) if
  `target.id == actor.id` for **deactivate** and **password reset** and **role/email/name
  edit**. The acting admin manages their own account via the profile editor (FR-019); the
  admin surface treats the self-row as read-only.
- **Last admin**: raise `LastAdminError` (→ **409**) when an action would leave zero active
  admins — i.e. **deactivating** the sole admin, or **demoting** (role `admin`→`user`) the
  sole admin (FR-010/SC-006).

New domain errors `SelfActionError` and `LastAdminError` join the existing `DomainError`
hierarchy. HTTP mapping in the router: `UserNotFoundError`→404, `DuplicateEmailError`→409,
`LastAdminError`→409, `SelfActionError`→403, `PasswordTooShortError`→422,
`NoChangesSpecifiedError`→422.

**Rationale**: These are the safety properties that make a click-to-delete UI safe to expose
(SC-006). Putting them in the domain means they hold for any future transport too, and they
get cheap no-DB-needed-beyond-count unit tests.

**Alternatives considered**:
- *Enforce guards only in the router.* Rejected — Principle III wants the rule in the domain;
  a router-only check is untested-without-HTTP and bypassable by future callers.
- *Allow self-deactivation if another admin exists.* Rejected per clarification (read-only
  self-row): self-management is the profile editor's job, and forbidding it outright is the
  simplest lockout-proof rule.

---

## D5 — Password provisioning: type-or-generate, voluntary rotation

**Decision**: Shared `PasswordSet`/`UserCreate` validation: **exactly one** of `password`
(typed) or `generate: true` (Pydantic `model_validator` enforces XOR). When `generate` is
set, the domain calls a new `generate_temp_password()` in `domain/passwords.py`:

```python
def generate_temp_password() -> str:
    return secrets.token_urlsafe(12)   # ~16 url-safe chars, ≥ MIN_PASSWORD_LENGTH (12)
```

The plaintext is returned **once** in the create/reset response (`temporary_password`), only
the Argon2id hash is persisted, and it is never logged. Typed passwords still flow through the
shared 12-char minimum (`password_too_short` → 422). There is **no** "must change at next
login" flag — rotation is voluntary via the profile editor (FR-018), so **no schema change**
for password lifecycle.

**Rationale**: Implements the clarified "both options" + "voluntary rotation" directly while
reusing the single source of truth for the length rule and the existing hashing. `secrets`
is stdlib (Principle V — no new dependency) and cryptographically strong.

**Alternatives considered**:
- *A human-friendly word-list passphrase generator.* Rejected — adds a wordlist/dependency for
  a temp secret the user is expected to replace immediately; `token_urlsafe` is sufficient.
- *A `must_change_password` column + login-flow gate.* Rejected per clarification — out of
  scope; keeps the auth flow and schema untouched.

---

## D6 — Audit log: a new append-only `admin_audit_log` table

**Decision**: One new table (full shape in `data-model.md`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `uuid_pk()` |
| `actor_id` | UUID FK → `users.id` | the acting admin |
| `target_user_id` | UUID FK → `users.id` | the affected user |
| `action` | ENUM `admin_audit_action` (`create`,`update`,`role_change`,`password_reset`,`deactivate`) | — |
| `details` | JSONB | changed **field names** (e.g. `{"fields": ["name","email"]}`); for `role_change` may carry `{"role": "user→admin"}`. **Never** passwords/hashes. |
| `created_at` | timestamptz | the "when" (`created_at_col()`) |

Append-only: no `updated_at`, no `deleted_at`. **No success/failure outcome field** —
only successful actions are recorded (clarification); denied/blocked attempts stay in ordinary
server logs. The audit write (`domain/audit.py::record_admin_action`) runs in the **same
request transaction** as the action, so it commits atomically — exactly one row per successful
action (FR-013/SC-004). New model `db/models/admin_audit.py`, re-exported from
`db/models/__init__.py` so Alembic autogenerate sees it; one migration via `just migrate-rev`.

FKs reference `users.id` (no cascade — adherence/audit history must survive a soft-delete; the
target is soft-deleted, its rows remain). `action` distinguishes `update` (name/email) from
`role_change` so the trail is queryable.

**Rationale**: A dedicated table is the minimal way to satisfy "who did what to whom, when"
with field-name granularity and no secret leakage. JSONB `details` avoids a column-per-field
explosion while staying greppable. Same-transaction write guarantees the one-per-action
invariant without a second round trip.

**Alternatives considered**:
- *Reuse application logs only (no table).* Rejected — the clarification explicitly asked for
  an audit **log** queryable in-app (FR-014); logs aren't structured or admin-viewable.
- *Store full before/after values.* Rejected — risks persisting secrets and PII; field-name
  summaries meet the requirement (FR-013 "field names only — never secret values").
- *An `outcome` column for denied attempts.* Rejected per clarification (successes only).

---

## D7 — Frontend: an admin-only `/admin` route subtree + dialogs

**Decision**: TanStack file routes `routes/admin.tsx` (layout: `<Outlet/>` + a `beforeLoad`
that reads `/me` and `redirect`s non-admins to `/`, mirroring the `reminders` guard) and
`routes/admin.users.tsx` (the page). A `routes/admin.audit.tsx` read-only view is the P3
slice. `NavBar.tsx` renders an **"Admin"** link only when `useCurrentUser()?.role === "admin"`.

Components under `components/admin/`:
- `UserList` — card rows (mirrors `MedicationList`), each with Edit / Reset-password /
  Deactivate actions. The **acting admin's own row** renders those actions disabled with a hint
  ("Manage your own account in the profile editor") — FR-019.
- `UserFormDialog` — create + edit modal (RHF + Zod: email, name, role; on create, a
  type-or-generate password control). 409 (duplicate email) and 422 map to field errors via the
  established `serverError` pattern.
- `ResetPasswordDialog` — type-or-generate; on a generated reset, shows the
  `temporary_password` **once** with a copy button and a "won't be shown again" note.
- `DeactivateUserModal` — in-app confirm (the `UntakeConfirmModal` `role="dialog"` pattern;
  **never** native `confirm()`, which freezes Claude-in-Chrome and isn't the project style).

Queries/mutations live in `lib/adminUsers.ts` (`useUsers`, `useCreateUser`, `useUpdateUser`,
`useResetPassword`, `useDeactivateUser`, `useAuditLog`), each invalidating `["admin","users"]`
on success. All calls go through the typed `openapi-fetch` client; `api/v1.d.ts` is
regenerated.

**Rationale**: Reuses the project's route-guard, RHF+Zod form, and in-app-confirm patterns, so
the surface is consistent and small. The dotted-route layout (`admin.tsx` parent for
`admin.users.tsx`) satisfies TanStack's parent-layout requirement noted in project memory.

**Alternatives considered**:
- *A single `/users` route with no `admin` parent.* Rejected — an `admin.tsx` layout is the
  natural home for the shared admin guard and future admin pages (audit), and matches the
  `medications.tsx`→`medications.*` pattern.
- *Native `confirm()` for deactivate.* Rejected — project convention is in-app modals; native
  dialogs freeze the browser-automation tooling.

---

## D8 — Test layout & coverage

**Decision**:

| File | Scope | Notes |
|---|---|---|
| `backend/tests/domain/test_admin_guards.py` | Domain | `count_active_admins`; self-action → `SelfActionError`; sole-admin deactivate/demote → `LastAdminError`; non-last admin allowed. |
| `backend/tests/domain/test_temp_password.py` | Domain | `generate_temp_password()` ≥ 12 chars, distinct across calls, hashes/verifies. |
| `backend/tests/domain/test_admin_audit.py` | Domain | `record_admin_action` inserts exactly one row with actor/target/action/details; `details` carries no secret. |
| `backend/tests/api/test_users_admin_access.py` | API | A `role=user` caller gets **403** on every `/api/v1/users` endpoint; unauthenticated → 401; admin → allowed (FR-001/SC-003). |
| `backend/tests/api/test_users_create.py` | API (US1) | Typed → 201 (no temp pw in body); generate → 201 + `temporary_password` once; duplicate (incl. soft-deleted) email → 409; short typed pw → 422; both/neither password+generate → 422. |
| `backend/tests/api/test_users_edit.py` | API (US2) | name/email/role edits → 200; duplicate email → 409; editing self → 403; demoting the sole admin → 409; `extra` field → 422. |
| `backend/tests/api/test_users_password.py` | API (US2) | Reset revokes the target's existing sessions (a pre-existing session 401s after); self → 403; generate returns the temp pw once. |
| `backend/tests/api/test_users_delete.py` | API (US3) | Deactivate → 204, user gone from list + sessions revoked; self → 403; sole admin → 409. |
| `backend/tests/api/test_users_audit.py` | API (US4/P3) | One audit entry per successful action; list is reverse-chronological; password entries contain no secret. |
| `frontend/src/__tests__/AdminUsers.test.tsx` | Component | Nav "Admin" link shows only for `role=admin`; list renders; create dialog calls `POST`; self-row actions disabled; deactivate uses the in-app confirm modal; generated temp pw shown once. |

Reuse `backend/tests/api/conftest.py` (`AsyncClient` + `ASGITransport`, login helper, shared
transactional session) and the real-Postgres rollback fixture; add an **admin** and a
**non-admin** fixture user. Project coverage stays ≥ 85%; the new domain units are small and
fully covered.

**Rationale**: The "non-admin is 403 everywhere" and "sessions die on reset/deactivate" tests
are the security core (SC-003/SC-005); the guard tests pin SC-006; the audit test pins
SC-004/FR-013. Mirrors `tests/api/test_schedules_crud.py` and the Phase 7 reminder tests.

**Alternatives considered**:
- *Skip domain guard tests, cover via API only.* Rejected — the guards are the
  security-relevant units; no-HTTP domain tests pin them independently and cheaply.

---

## D9 — Docs, ADR & ER (FR-013 doc sweep, executed in implement phase)

**Decision**:
- **ADR-0014 — "In-app admin user management"** (`docs/adr/0014-…md`), Proposed → **Accepted**
  with the PR. Records: the `require_admin` gate, the `/api/v1/users` surface reusing the user
  domain, the last-admin/no-self guards, type-or-generate temp passwords with voluntary
  rotation, the successes-only `admin_audit_log`, and — explicitly — the **reversal of the
  glossary's "no admin web UI in v1"** stance (Governance: resolve the conflict in the same
  PR). Next free ADR number is **0014** (0013 is highest). Includes the Principle I threat note.
- **ER diagram** `docs/diagrams/er.md` — add `admin_audit_log` and its FKs to `users`.
- **Sequence diagram** `docs/diagrams/admin-deactivate-user.md` — resolve-by-id → guards →
  soft-delete → revoke-all-sessions → audit-write (Principle IV "key user flows").
- **Glossary** `docs/glossary.md` — rewrite the **Admin** entry (admins now manage users in-app
  *and* via the CLI; both share the domain) and add an **Audit log** term.
- **User stories** `docs/user_stories.md` — add an in-app admin management UC alongside the
  CLI-only UC-1 (which remains valid).
- **`CLAUDE.md`** — SPECKIT marker points at this plan; add a one-line "surprises" note
  (`/api/v1/users` behind `require_admin`; admin_audit_log is append-only/successes-only;
  self-row read-only; temp passwords shown once, voluntary rotation).
- **`checklists/security.md`** — required merge gate for this security-sensitive feature
  (Principle IV); generate with `/speckit-checklist`.

**Rationale**: Satisfies the constitution's "Documented decisions" and the spec's stated doc
sweep, and resolves the glossary conflict in the same change set (Governance rule). These are
documentation tasks scheduled in `/speckit-tasks`, not part of `/speckit-plan` output.

**Alternatives considered**:
- *Skip the ADR / just edit the glossary.* Rejected — reversing a recorded v1 scope decision is
  exactly what an ADR is for (Principle IV), and the glossary line cites the prior stance.
