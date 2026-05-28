# ADR-0014: In-app admin user management

## Status

Accepted

## Context

Every user-management action (create, edit, password reset, role change,
deactivate) has until now required the admin CLI (`medminder-admin user …`). In
production that means spinning up a one-shot job on the hosting service (Koyeb),
running one command, and tearing the job down — painful for routine account
changes. The capability is almost entirely already built: `domain.users` exposes
`create_user` / `update_user` / `soft_delete_user` / `list_users`, the
`users.role` column (`admin` | `user`) exists, `GET /me` returns the role, and
the session-revocation-on-password-change / on-delete pattern (ADR-0001) is wired
(`revoke_all_user_sessions`). What was missing was purely transport + UI.

This is **explicitly off-roadmap** and reverses the prior stance recorded in
`docs/glossary.md` ("there is no admin web UI in v1"). Because it adds a new
authenticated, privileged surface plus an audit table, it is security-relevant
(Constitution Principle I, NON-NEGOTIABLE) — hence this ADR (feature
`009-admin-user-management`).

## Decision

1. **`require_admin` gate.** A new FastAPI dependency wraps `get_current_user`
   and raises **403** for an authenticated non-admin (unauthenticated callers
   already get **401** from `get_current_user`). It gates the entire
   `/api/v1/users` surface server-side — the control does not depend on the UI
   hiding the nav entry (which it also does, for admins only).

2. **A new `/api/v1/users` router reusing the user domain (FR-012).** Endpoints
   are thin transport over the existing domain so in-app and CLI behaviour cannot
   diverge:
   - `GET /api/v1/users` — list active users.
   - `POST /api/v1/users` — create with a typed **or** generated temp password
     (exactly one). A generated password is returned **once** in
     `temporary_password` and never stored or logged (FR-004/FR-020).
   - `PATCH /api/v1/users/{id}` — edit name/email/role.
   - `POST /api/v1/users/{id}/password` — reset password (typed or generated;
     revokes the target's sessions).
   - `DELETE /api/v1/users/{id}` — deactivate (soft-delete + revoke sessions).
   - `GET /api/v1/users/audit-log` — read-only audit trail (declared **before**
     `/{id}` so the literal segment isn't parsed as a UUID).

   The REST surface is **id-keyed**; new `domain.users` orchestrators
   (`admin_update_user` / `admin_reset_password` / `admin_deactivate_user`)
   resolve the id (`get_user_by_id`), enforce the guards, then reuse the existing
   email-keyed `update_user` / `soft_delete_user`.

3. **Lockout-proof guards (FR-009/FR-010/SC-006).**
   - **Self-action guard** (`SelfActionError` → 403): an admin cannot edit, reset
     the password of, or deactivate *their own* account here — self-management is
     the profile editor's job (ADR-0011). This is the primary lockout prevention:
     because the acting admin is always a counted active admin, removing the
     *last* admin can only mean removing yourself, which is refused.
   - **Last-admin guard** (`LastAdminError` → 409): demoting or deactivating an
     admin checks `count_active_admins`, which takes a `FOR UPDATE` lock on the
     active-admin rows before counting so two concurrent last-admin removals
     **serialize** instead of both passing (FR-021). At the HTTP layer this is a
     defense for the concurrency edge; it is exercised directly in the domain
     tests where a sole-admin target with a distinct actor is constructible.

4. **Type-or-generate temp passwords, voluntary rotation (FR-004/FR-018).**
   `generate_temp_password()` uses the stdlib CSPRNG (`secrets.token_urlsafe`,
   ≥ 128 bits, comfortably over the 12-char minimum, which stays the single
   source of truth in `domain.passwords`). **No forced-rotation flag** is set —
   the created/reset user can sign in immediately and re-secure their password via
   the profile editor. No `users` schema change.

5. **Append-only, successes-only audit log (FR-013/FR-022).** A new
   `admin_audit_log` table records exactly one row per **successful** action
   (`create` / `update` / `role_change` / `password_reset` / `deactivate`),
   written in the same request transaction as the action (SC-004). `details` is
   JSONB carrying changed **field names** only — **never** passwords, hashes, or
   other secret values (FR-020). No `updated_at`/`deleted_at`, no edit/delete
   route, retained indefinitely in v1. FKs to `users` carry no `ON DELETE
   CASCADE` so history outlives a deactivated actor/target. Denied/blocked
   attempts are not recorded here (they stay in ordinary server logs).

6. **Email stays admin-managed for the *self* path; admins may set it here.** A
   regular user still cannot change their own email or role (`PATCH /me` is
   `extra="forbid"` → 422, FR-017, ADR-0011). The admin surface *can* edit another
   user's email/role — that is the point of this feature.

## Consequences

### Positive

- Routine provisioning and account maintenance no longer require a hosting
  one-shot job; the CLI remains for break-glass / scripted use and is unchanged.
- Reusing the domain layer means one implementation, one set of rules (12-char
  minimum, case-insensitive email uniqueness incl. soft-deleted, session
  revocation) shared by CLI and web.
- The audit log gives an attributable, tamper-resistant record of privileged
  actions that the CLI never produced.

### Negative

- A new authenticated privileged surface widens the attack surface; mitigated by
  the server-side `require_admin` gate, the lockout guards, never logging
  secrets, and the append-only audit trail. No brute-force/lockout on the surface
  itself in v1 (single-tenant, low-traffic) — noted as a future hardening item.

### Neutral

- Reverses the glossary's "no admin web UI in v1" line (updated accordingly).
- The last-admin 409 guard is largely defensive given the self-guard; it remains
  for the concurrency case (FR-021) and CLI/domain reuse.
- Restoring a deactivated user remains CLI/DB-only (no in-app un-delete, FR-016).
