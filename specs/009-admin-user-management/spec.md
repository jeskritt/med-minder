# Feature Specification: In-App Admin User Management

**Feature Branch**: `009-admin-user-management`

**Created**: 2026-05-27

**Status**: Draft

**Input**: User description: "I would like to spec another off roadmap feature. I don't like having to use the CLI for every user. It's great for dev, but setting up oneshot jobs on the hosting service and then deleting them just for user management is a pain. Does it make sense to add a user management flow to the app for the admin accounts?"

## Clarifications

### Session 2026-05-27

- Q: Should an admin-set or generated temporary password force the user to change it at next login? → A: Voluntary — no forced change; rotation happens via the self-service profile editor (no "must change password" flag introduced, no schema change).
- Q: Should the audit log also record failed/denied privileged attempts, or only successful actions? → A: Successes only — denied/blocked attempts are not written to the audit log (they remain in ordinary server logs); the audit entity has no success/failure outcome field.
- Q: How should the acting admin's own account behave in the admin Users area? → A: Read-only self-row — the admin's own row is visible but not editable in the admin UI; self display-name/password changes route to the profile editor, while the no-self-deactivation and no-last-admin-removal guards still apply.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Provision and view users in-app (Priority: P1)

An administrator signs in to the app, opens a "Users" area, and sees the list of active
users (email, display name, role, created date). From there they create a new user by
entering an email, a display name, and a role, then either typing an initial password or
requesting a system-generated temporary password that is displayed exactly once. The new
user can immediately sign in.

**Why this priority**: This is the core pain point — provisioning a user today requires
spinning up a one-shot job on the hosting service, running a CLI command, and tearing the
job back down. Listing and creating users in-app eliminates that entire workflow and on its
own delivers the feature's primary value.

**Independent Test**: Sign in as an admin, open the Users area, create a new user, sign out,
and confirm the new user can log in with the password that was set. No hosting-console access
is required at any point.

**Acceptance Scenarios**:

1. **Given** an admin is signed in, **When** they open the Users area, **Then** they see all
   active users with email, display name, role, and created date.
2. **Given** an admin is creating a user, **When** they supply a unique email, a name, a role,
   and a password of at least 12 characters, **Then** the user is created and can sign in.
3. **Given** an admin is creating a user, **When** they request a generated password instead of
   typing one, **Then** a temporary password is displayed exactly once for them to relay.
4. **Given** an admin is creating a user, **When** the email matches an existing user (including
   a deactivated one), **Then** the request is rejected with a clear "email already exists"
   message and no user is created.

---

### User Story 2 - Edit a user and reset their password (Priority: P2)

An administrator selects an existing user and edits their display name, email, or role, or
resets their password (typed or generated). Resetting a password signs that user out of all
of their devices.

**Why this priority**: Routine maintenance — name corrections, role changes, and password
resets for locked-out users — is the second most common CLI chore. It depends on the listing
from US1 but is independently valuable.

**Independent Test**: As an admin, change a user's display name and role and confirm the change
persists; reset the user's password and confirm their previously active sessions no longer
authenticate.

**Acceptance Scenarios**:

1. **Given** an existing active user, **When** an admin changes their display name or role,
   **Then** the change is saved and reflected in the list.
2. **Given** an existing active user, **When** an admin changes their email to one not in use,
   **Then** the email is updated; **When** the new email collides with another user, **Then**
   the change is rejected with a clear message.
3. **Given** an existing user with active sessions, **When** an admin resets their password,
   **Then** the new password takes effect and all of that user's existing sessions are revoked.
4. **Given** a password reset, **When** the admin chooses to generate a password, **Then** a
   temporary password is shown exactly once and cannot be retrieved later.

---

### User Story 3 - Deactivate a user (Priority: P2)

An administrator deactivates (soft-deletes) a user through an in-app confirmation step. The
user is immediately signed out everywhere and no longer appears in the list. Safeguards prevent
the admin from deactivating their own account or removing the last remaining admin.

**Why this priority**: Offboarding is the remaining routine CLI chore. The safeguards are what
make it safe to expose in-app (a single fat-fingered click must not lock everyone out).

**Independent Test**: As an admin, deactivate a test user and confirm they disappear from the
list and can no longer authenticate; then attempt to deactivate your own account and to remove
the last admin, and confirm both are blocked.

**Acceptance Scenarios**:

1. **Given** an active non-self user, **When** an admin confirms deactivation, **Then** the user
   is soft-deleted, their sessions are revoked, and they no longer appear in the default list.
2. **Given** an admin viewing their own row, **When** they attempt to deactivate themselves,
   **Then** the action is blocked with an explanatory message.
3. **Given** exactly one admin exists, **When** an attempt is made to deactivate or demote that
   admin to a regular user, **Then** the action is blocked with an explanatory message.
4. **Given** a deactivated user, **When** an admin views the list, **Then** that user is not
   shown and there is no in-app way to restore them.

---

### User Story 4 - Audit trail of admin actions (Priority: P3)

Every create, edit, role change, password reset, and deactivation records an audit entry
capturing who performed the action, on whom, what changed, and when. Password values are never
recorded. An administrator can view this audit log in a read-only view.

**Why this priority**: Accountability for privileged actions strengthens the security posture,
but the recording itself (forensic value in the database) matters more than an in-app viewer,
so the read-only view is the lowest-priority slice and may ship after the rest.

**Independent Test**: Perform one of each qualifying action and confirm exactly one attributable
audit entry is recorded per action, with no password material present.

**Acceptance Scenarios**:

1. **Given** an admin performs a create / edit / role-change / password-reset / deactivation,
   **When** the action succeeds, **Then** exactly one audit entry is recorded with the acting
   admin, the target user, a summary of what changed, and a timestamp.
2. **Given** an audit entry for a password reset, **When** it is inspected, **Then** it contains
   no password value or hash.
3. **Given** recorded audit entries, **When** an admin opens the read-only audit view, **Then**
   they see the entries in reverse-chronological order.

---

### Edge Cases

- A non-admin (role `user`) who navigates to the admin route or calls a user-management endpoint
  directly is denied; the navigation entry point is hidden for non-admins.
- A duplicate email on create or edit — including a collision with a **deactivated** user's email
  — is rejected with a clear message and no change is made.
- A password shorter than 12 characters is rejected for both typed and (by construction) generated
  passwords.
- A generated temporary password is shown exactly once and is not retrievable afterward; if the
  admin loses it, they reset the password again.
- Deactivating a user or resetting their password takes effect within the same request — the
  target's active sessions are revoked immediately.
- An admin attempting to deactivate their own account, or to delete or demote the last remaining
  admin, is blocked with an explanatory message rather than silently failing.
- The acting admin's own row is shown read-only in the admin UI; to change their own display name
  or password they use the self-service profile editor.
- An operation targeting a non-existent or already-deactivated user id returns a clear not-found
  response. Because the entire surface is admin-only and admins can already enumerate all users, a
  not-found response discloses nothing to an unauthorized party.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Only users with role `admin` MUST be able to reach the user-management interface or
  invoke its operations; all other users MUST be denied.
- **FR-002**: Admins MUST be able to view a list of active users showing email, display name, role,
  and created date.
- **FR-003**: Admins MUST be able to create a user by providing an email, a display name, and a role.
- **FR-004**: When creating a user or resetting a password, the admin MUST be able to either enter a
  password directly or request a system-generated temporary password that is displayed exactly once.
  Exactly one of the two MUST be supplied per request — a request providing both, or neither, MUST be
  rejected as invalid. A system-generated temporary password MUST be produced with a
  cryptographically secure random generator and MUST satisfy the shared minimum (FR-005).
- **FR-005**: All passwords, whether typed or generated, MUST satisfy the shared 12-character minimum.
- **FR-006**: Admins MUST be able to edit an existing user's display name, email, and role.
- **FR-007**: Resetting a user's password MUST revoke all of that user's active sessions.
- **FR-008**: Deactivating (soft-deleting) a user MUST revoke all of that user's active sessions
  immediately.
- **FR-009**: The system MUST prevent an admin from deactivating their own account.
- **FR-010**: The system MUST prevent removing the last remaining admin, whether by deactivation or
  by demotion to a regular user.
- **FR-011**: Email uniqueness MUST be enforced case-insensitively, including against deactivated
  users; conflicts MUST be rejected with a clear message.
- **FR-012**: In-app user management MUST reuse the shared user-management business rules so that its
  behavior does not diverge from the existing admin CLI.
- **FR-013**: The system MUST record exactly one audit entry for each **successful** create, edit,
  role change, password reset, and deactivation, capturing the acting admin, the target user, a
  summary of what changed, and a timestamp. Password values MUST NOT be recorded. Denied or blocked
  privileged attempts (e.g., non-admin access, a blocked last-admin removal) are NOT written to the
  audit log — they remain in ordinary server logs — so the audit entity carries no success/failure
  outcome field.
- **FR-014**: Admins MUST be able to view the audit log in-app in a read-only view. *(P3 — may ship
  after the rest.)*
- **FR-015**: The admin entry point MUST appear in navigation only for admins.
- **FR-016**: Deactivated users MUST be hidden from the default list, and there MUST be no in-app
  mechanism to restore them.
- **FR-017**: Users MUST NOT be able to change their own email or role; those remain admin-only,
  consistent with the existing self-service profile editor.
- **FR-018**: A temporary or admin-set password MUST NOT force a change at next login; rotation is
  voluntary and performed by the user via the self-service profile editor. No "must change password"
  flag or schema change is introduced.
- **FR-019**: The acting admin's own account MUST appear in the list as read-only within the admin
  UI; changes to their own display name or password are made through the self-service profile
  editor. The no-self-deactivation (FR-009) and no-last-admin-removal (FR-010) guards still apply.
- **FR-020**: Password material MUST NOT be stored in plaintext or written to any log. Only a
  hash of the password is persisted. A generated temporary password is returned to the admin
  exactly once (FR-004) and is not retrievable afterward.
- **FR-021**: The last-admin (FR-010) and self-action (FR-009) guards MUST hold under concurrent
  requests: no interleaving of admin operations may reduce the number of active admins to zero.
- **FR-022**: The audit log MUST be append-only — recorded entries cannot be edited or deleted
  through any in-app interface.
- **FR-023**: On create and on edit, an email value MUST be a syntactically valid email address,
  and a display name MUST be 1–100 characters. Invalid values are rejected as validation errors.

### Key Entities *(include if feature involves data)*

- **User** (existing): the account being managed. Attributes: email (login identity, admin-managed),
  display name, role (`admin` or `user`), password (stored only as a hash), timezone, quiet hours,
  a deactivation timestamp (soft delete), and created/updated timestamps.
- **Audit log entry** (new, append-only): a record of one privileged action. Attributes: the acting
  admin, the action type (create / edit / role-change / password-reset / deactivate), the target
  user, a summary of what changed (field names only — never secret values), and a timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can provision a new user end-to-end in under 1 minute without touching the
  hosting console.
- **SC-002**: 100% of the routine user-management actions previously requiring a CLI one-shot job
  (create, password reset, role change, deactivate) are achievable in-app.
- **SC-003**: Non-admins achieve 0 successful user-management actions, whether through the UI or by
  calling the operations directly.
- **SC-004**: Every qualifying action produces exactly one audit entry attributable to the acting
  admin.
- **SC-005**: Deactivating a user or resetting their password signs that user out of all devices
  within the same request.
- **SC-006**: 0 admin lockouts occur: self-deactivation and removal of the last admin are impossible.

## Assumptions

- The single-tenant model is unchanged: no self-registration, no organizations/multi-tenancy, and no
  admin tiers beyond the binary `admin`/`user` role.
- The admin UI focuses on identity/access fields (email, display name, role, password). Timezone
  defaults to UTC at creation and remains user self-service; quiet hours remain user self-service.
  Both stay settable via the existing admin CLI as a fallback.
- Generated temporary passwords are shown exactly once, are never stored in plaintext or retrievable,
  and the user rotates the password voluntarily via the self-service profile editor — there is no
  forced "change password at next login" step (see FR-018).
- The existing server-side session-revocation pattern is reused for password reset and deactivation.
- This feature reverses the prior "no admin web UI in v1" stance; the decision will be recorded in a
  new ADR, accompanied by a documentation sweep (glossary, user stories, ER diagram).
- The audit log is append-only and not user-editable (FR-022). Entries are retained indefinitely
  in this version; no automatic purge or retention window is implemented (revisit if volume ever
  warrants it).

## Out of Scope

- Restoring or undeleting users.
- Caregiver-, clinician-, or third-party-facing views.
- Delegated or granular admin permissions beyond the binary `admin`/`user` role.
- Self-registration, email verification, or forgotten-password self-recovery.
- Third-party identity (OAuth/SAML).
- Editing other users' timezone or quiet hours from the admin UI.
