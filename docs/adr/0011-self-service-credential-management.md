# ADR-0011: Self-service credential management (profile editor)

## Status

Accepted

## Context

Until now the only way to set or change a user's password was the admin CLI
(`medminder-admin user update … --password-stdin`). That means an admin
necessarily knows every user's password — they set it. For a single-tenant
medication tracker that is workable but undesirable: the user cannot hold a
secret the admin does not, and there is no in-app way to rotate a credential.

We want a **self-service profile editor**: a signed-in user clicks their name in
the nav bar and changes their **display name** and **password** themselves. This
touches credentials and sessions, so the decision is security-relevant and
governed by Constitution Principle I (security-conscious by default) — hence this
ADR (feature `007-profile-editor`).

The login identity is the **email**; there is no separate username. `Me` exposes
`{id, name, role}`. Sessions are server-side, signed HTTP-only cookies
(ADR-0001); `domain.users.update_user` already revokes *all* sessions on a
password change, and `domain.passwords` is the single source of the Argon2id hash
and the 12-character minimum.

## Decision

1. **Editable fields: display name + password only.** The login **email stays
   admin-managed** (CLI), keeping the login identity stable. The editor offers no
   email/role field, and the request models are `extra="forbid"` so an email/role
   field is rejected (422).
2. **Two endpoints on the existing `me` router:**
   - `PATCH /me` `{name}` → `200 Me` — display name only; no re-auth, no session
     effects. Reuses `update_user(email=user.email, new_name=…)`.
   - `POST /me/password` `{current_password, new_password}` → `204` — verifies the
     current password, sets the new one, and re-issues this device's session cookie.
3. **Current-password re-auth.** Changing the password requires the current
   password, verified server-side via `domain.passwords.verify_password`. A wrong
   current password is **HTTP 403** ("current password is incorrect"), kept
   **distinct from 422** (too-short new password) and **never 401** — `401` is the
   client's "session expired → bounce to login" signal (`lib/api.ts`), which would
   be the wrong UX for an authenticated user mistyping their old password.
4. **Keep this device signed in; revoke the rest.** A new domain function
   `change_own_password(user, current, new)` verifies, sets the hash, and calls the
   existing `revoke_all_user_sessions`. The `POST /me/password` handler then mints a
   fresh session and sets its cookie (mirroring `POST /auth/login`), so the current
   device stays signed in (on a **rotated** token) while every other device is
   logged out. The 12-char minimum stays in `domain.passwords` (mapped to 422),
   never hardcoded in the API schema.
5. **No audit record in v1.** Profile/credential changes are not written to an
   audit trail; reliance is on session revocation to limit blast radius and on never
   logging raw secrets. No new table or column — `alembic check` stays clean. A
   future hardening pass may revisit.
6. **Forgotten-password recovery uses the existing CLI.** No new admin tooling: an
   admin sets a temporary password via `user update … --password-stdin`; the user
   signs in and immediately re-secures it via `POST /me/password`.

## Consequences

### Positive

- Users own their password; the admin no longer knows it after the user changes it.
- The 403/422/never-401 split gives the editor clean per-field errors and keeps the
  client's session-expiry handling intact.
- Re-issue-after-revoke reuses `revoke_all_user_sessions` + `create_session` + the
  login cookie path — no new session-domain code, and the token rotates (a mild
  security plus). No schema change.

### Negative

- A password change silently signs the user out of all *other* devices. This is the
  intended security behavior but may surprise multi-device users; documented in
  `CLAUDE.md` and the editor's success message.

### Neutral

- Email remains CLI-only; a future feature could add verified self-service email
  change (out of scope here).
- No brute-force/lockout on the current-password check in v1 (single-tenant,
  low-traffic); noted as a future hardening item.
