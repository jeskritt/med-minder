# Feature Specification: Self-Service Profile Editor

**Feature Branch**: `007-profile-editor`
**Created**: 2026-05-23
**Status**: Draft
**Input**: User description: "a simple profile editor for the user — click their name
in the nav bar to bring it up; change user name and password so admin doesn't know
their password; check the CLI has a user password reset in case they forget; will
require a document sweep."

## Clarifications

### Session 2026-05-23

- Q: Which fields can the user edit? → A: **Display name + password only.** The login
  email stays admin-managed (not editable in the self-service UI). The app has no
  separate "username"; login identity is the email.
- Q: Must a sensitive change require re-authentication? → A: **Yes — changing the
  password requires re-entering the current password.**
- Q: What happens to sessions after a successful password change? → A: **Keep the
  current device signed in (re-issue its session); revoke all other active sessions.**
  This deliberately refines the existing domain behavior, which revokes every session
  including the current one.
- Q: Does the admin CLI need a new "reset password" command for forgotten passwords?
  → A: **No.** `medminder-admin user update --email <e> --password-stdin` already sets
  a new password. Recovery = admin sets a temporary password, user then changes it via
  this editor. Story is verify + document only.
- Q: How does the profile editor surface in the UI? → A: As a **modal dialog** opened
  from the nav-bar name (an overlay on the current page); not a dedicated routed page.
- Q: What validation does the display name have? → A: **Required, trimmed, maximum 100
  characters.**
- Q: How is a wrong *current* password reported by the API? → A: **HTTP 403** with a
  clear "current password is incorrect" field message — distinct from the **422**
  returned for a too-short new password, and never **401** (reserved for
  unauthenticated / expired sessions, which the client auto-bounces to login).
- Q: Are successful profile/credential changes recorded in an audit trail? → A: **No
  audit record in v1** — rely on session revocation to limit blast radius and never log
  raw secrets; no new table or column. (A future hardening pass may revisit.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Change my own password without the admin knowing it (Priority: P1)

A signed-in user opens the profile editor from their name in the nav bar, enters their
current password and a new password, and saves. The current password is verified before
any change. On success their password is updated, they remain signed in on the current
device, and every other active session is signed out. The admin never learns the
user-chosen password.

**Why this priority**: This is the entire point of the feature — moving password
ownership from the admin to the user. It is the smallest slice that delivers the value
("admin doesn't know their password") and is independently shippable.

**Independent Test**: Sign in, open the editor, submit a new password with the correct
current password → password changes, current session still works, a second pre-existing
session for the same user is rejected on its next request. Submit with a wrong current
password → rejected, password unchanged.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they submit a new password (≥12 chars) with the
   correct current password, **Then** the password is updated and the response keeps the
   current device authenticated.
2. **Given** the conditions in scenario 1, **When** the change succeeds, **Then** all of
   the user's *other* active sessions are revoked, while the current session remains
   valid (no forced re-login on this device).
3. **Given** a signed-in user, **When** they submit a new password with an *incorrect*
   current password, **Then** the change is rejected with a clear message and the stored
   password is unchanged.
4. **Given** a signed-in user, **When** they submit a new password shorter than 12
   characters, **Then** it is rejected with the same minimum-length message used
   everywhere else, and nothing changes.
5. **Given** an unauthenticated request to the password-change operation, **When** it is
   made, **Then** it is rejected as unauthorized and changes nothing.
6. **Given** user A is signed in, **When** A attempts to change a password, **Then** only
   A's own credentials can be affected — there is no path to change another user's.

---

### User Story 2 — Change my display name (Priority: P2)

A signed-in user opens the profile editor and updates the display name shown in the nav
bar (and anywhere else their name appears). The change takes effect immediately without a
manual page reload. Changing the name does not require the current password and does not
affect any sessions.

**Why this priority**: A natural, low-risk part of "a simple profile editor" and the
second half of the user's literal request ("change user name"). Useful but not the
safety/ownership core, so it sequences after the password story.

**Independent Test**: Sign in, open the editor, change the display name and save → the
nav bar reflects the new name on the next refetch with no reload, and the name change
required no password entry and left sessions intact.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they submit a non-empty new display name, **Then**
   it is saved and reflected in the nav bar / current-user view without a manual reload.
2. **Given** a signed-in user, **When** they submit an empty or whitespace-only name,
   **Then** it is rejected with a clear message and nothing changes.
3. **Given** a signed-in user, **When** they change only the display name, **Then** no
   current-password entry is required and no sessions are revoked.

---

### User Story 3 — Recover a forgotten password via the admin (Priority: P3)

If a user forgets their password, the admin sets a temporary password using the existing
admin CLI, communicates it out-of-band, and the user immediately changes it to a private
one via the editor (User Story 1). No new admin tooling is built; this story confirms the
recovery path exists and is documented.

**Why this priority**: A safety net for the self-service model, not the model itself. The
capability already exists in the CLI, so this is a verification-and-documentation slice.

**Independent Test**: Using the existing CLI, set a new password for a user; confirm the
user can sign in with it and then change it via the editor; confirm the admin's temporary
password no longer grants access after the user changes it.

**Acceptance Scenarios**:

1. **Given** a user who forgot their password, **When** an admin sets a temporary password
   via the existing CLI command, **Then** the user can sign in with it.
2. **Given** the user signed in with the temporary password, **When** they change it via
   the editor (User Story 1), **Then** the temporary password no longer works and only the
   user knows the new one.

### Edge Cases

- **Wrong current password** → password change rejected, nothing mutated, no session
  effects.
- **New password too short (<12)** → rejected with the project-wide minimum-length
  message; no change.
- **Empty / whitespace display name** → rejected; no change.
- **Display name longer than 100 characters** → rejected with a clear message; no
  change.
- **Unauthenticated request** to any profile operation → unauthorized, no change.
- **Cross-user attempt** → a request can only ever affect the logged-in user's own
  record; no parameter selects another user.
- **Email is never editable here** → any attempt to change the login email through this
  surface is out of scope and not offered.
- **Current session continuity** → after a password change, the current device must not be
  bounced to the login screen; other devices must be.
- **Raw passwords** (current or new) MUST never be logged or echoed back in any response.

## Requirements *(mandatory)*

### Functional Requirements

#### Editor access & UX

- **FR-001**: The user's name in the nav bar MUST become an interactive control that opens
  the profile editor; it MUST be available only to an authenticated user and MUST NOT
  appear on the login screen. The editor surfaces as a **modal dialog** opened from the
  nav-bar name (an overlay on the current page), not a separate routed page.
- **FR-002**: The editor MUST show the current display name and provide a way to change the
  display name and to change the password.

#### Password change (User Story 1)

- **FR-003**: Changing the password MUST require the user's current password, verified
  server-side using the existing password-verification function; an incorrect current
  password MUST reject the change and mutate nothing. An incorrect current password MUST
  be rejected with **HTTP 403** and a field-specific "current password is incorrect"
  message — distinct from the **422** used for a too-short new password — and MUST NOT
  use **401**, which is reserved for unauthenticated/expired sessions and triggers the
  client's bounce-to-login.
- **FR-004**: A new password MUST satisfy the existing project minimum (12 characters),
  enforced by the existing shared validation, surfacing the same message used by the CLI
  and login flows.
- **FR-005**: On a successful password change, the current device's session MUST remain
  valid (re-issued as needed) and ALL of the user's other active sessions MUST be revoked.
- **FR-006**: The password-change operation MUST be server-authoritative and scoped to the
  logged-in user; there MUST be no parameter or path that lets it affect another user.

#### Display name change (User Story 2)

- **FR-007**: The user MUST be able to change their own display name; the name MUST be
  non-empty after trimming and at most **100 characters**.
- **FR-008**: After a successful name change, the nav bar / current-user view MUST reflect
  the new name on the next refetch without a manual page reload.
- **FR-009**: A display-name change MUST NOT require the current password and MUST NOT
  revoke any sessions.

#### Email scope

- **FR-010**: The self-service editor MUST NOT change the login email; email remains
  admin-managed via the CLI and is not offered as an editable field.

#### Forgotten-password recovery (User Story 3)

- **FR-011**: A forgotten password MUST be recoverable by an admin using the existing CLI
  password-set command (`medminder-admin user update … --password-stdin`); no new admin
  tooling is required. After recovery the user changes the password via FR-003–FR-005, so
  the admin's temporary password does not persist as the user's real password.

#### Cross-cutting (security, typing, coverage, docs)

- **FR-012** (security): All profile operations MUST be scoped to the logged-in user and
  validated at the boundary; raw current/new passwords MUST never be logged or returned in
  any response.
- **FR-013** (typing): New backend code MUST satisfy `mypy --strict`; new frontend code
  MUST satisfy `tsc --noEmit` strict.
- **FR-014** (coverage): Project coverage MUST stay ≥85%; no module falls below the 70%
  per-module floor.
- **FR-015** (docs — the requested "document sweep"): A documentation sweep MUST update all
  affected docs to reflect self-service credential management — at minimum `CLAUDE.md`
  (user-facing behavior notes), the OpenAPI contracts / generated client for any new
  endpoint, and any glossary / data-flow doc that describes how passwords are set. A new
  ADR (next number **0011**) MUST capture the security decision — self-service password
  change with current-password re-auth and revoke-others-keep-current session handling —
  per the constitution's "Documented decisions" principle.
- **FR-016** (docs — README quickstart): The **root `README.md` Quickstart** MUST gain a
  step covering the admin CLI for **creating the first user** and **setting/resetting a
  password** (`medminder-admin user add … --password-stdin` and `user update …
  --password-stdin`), so a newcomer who runs `just dev` has a documented path to a working
  login. Today the root Quickstart has no user-creation step (only the *backend* README
  documents the CLI). The new step MUST also point users at the self-service editor for
  changing their own password after first sign-in. The minimum-length and
  stdin-only-password conventions already documented in `backend/README.md` MUST be kept
  consistent (no contradictory duplication).

### Key Entities

- **User** *(existing table)*: only `name` (display) and `password_hash` are mutated by
  this feature. `email` is **not** mutated here. No new columns required.
- **Session** *(existing table)*: on a password change, every session for the user **except
  the current one** is revoked; the current one is re-issued/kept valid. No new columns
  required.
- *No new persistent tables or columns are anticipated.*

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in user can change their own password end-to-end with zero admin
  involvement, and the admin has no record of the user-chosen password.
- **SC-002**: A password change with an incorrect current password is rejected 100% of the
  time, with no mutation to the stored credential.
- **SC-003**: After a successful password change, the current device stays signed in
  (no forced re-login) and every other active session for that user is rejected on its next
  request, 100% of the time.
- **SC-004**: A display-name change is reflected in the nav bar within 2 seconds / on the
  next refetch, with no manual page reload.
- **SC-005**: The forgotten-password recovery path (admin sets temp password → user signs in
  → user changes it) works on a deployed build, and the temporary password stops working
  once the user changes it.
- **SC-006**: No raw password (current or new) appears in any log line or API response, as
  verified by review/test.
- **SC-007**: A newcomer following only the root `README.md` Quickstart can go from a fresh
  clone to a working login — including creating the first user and knowing how to
  set/change a password — without reading source or other docs.

## Assumptions

- The existing session auth (Phase 2), the password domain (Argon2 + 12-char minimum), and
  the admin CLI are reused as-is; this feature adds a self-service surface on top.
- Login email change is out of scope (admin-managed). The app has no separate "username";
  "user name" in the request means the display name.
- Display name is required, trimmed, and capped at **100 characters** (confirmed
  2026-05-23).
- The existing `update_user` revokes ALL sessions on password change; the agreed UX
  ("stay signed in here") requires keeping/re-issuing the current session — the exact
  mechanism (a "revoke all except current" variant, or revoke-then-reissue) is a
  `/speckit-plan` decision.
- The endpoint/transport shape (a single profile-update endpoint vs. separate
  name/password operations) is deferred to `/speckit-plan`; the wrong-current-password
  status is fixed at 403 (see FR-003).
- This is a single-tenant, low-traffic deployment; advanced brute-force protection /
  lockout on the current-password check is out of scope for v1 (a note for a future
  hardening pass).
- No audit/event record is written for profile or credential changes in v1 (out of
  scope); reliance is on session revocation and never logging secrets.
- A new ADR (0011) will record the security decision; whether any other ADR is touched is
  settled during the doc sweep at plan/implement time.

## Dependencies

- Phase 2 — auth: the `sessions` table, login/logout, `get_current_user`, the `/me`
  current-user endpoint, and session-cookie issuance.
- Existing `domain/users.py` (`update_user`) and `domain/passwords.py`
  (`verify_password`, `password_too_short`) reused for the write path and validation.
- Existing admin CLI `user update --password-stdin` for the recovery story.
- The nav bar (`frontend/src/components/NavBar.tsx`) where the user's name is rendered as
  the editor entry point.
