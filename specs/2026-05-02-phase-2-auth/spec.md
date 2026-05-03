# Feature Specification: Phase 2 — Auth (login / logout)

**Feature Branch**: `phase-2-auth`
**Created**: 2026-05-02
**Status**: Draft
**Input**: User description: "Phase 2 in @specs/roadmap.md"

## Clarifications

### Session 2026-05-02

- Q: What does Phase 2 redirect to on successful login, and what is the example protected endpoint that route-guard tests target? → A: Phase 2 introduces a stub `/medications` placeholder route (frontend) plus a protected `/api/me` whoami endpoint (backend). Login redirects to `/medications`; Phase 3 enriches the same route with real CRUD content.
- Q: What login events does Phase 2 log, and at what fidelity? → A: Every login attempt (successful and failed) is logged at INFO with an outcome enum (`success` / `wrong_password` / `unknown_email` / `soft_deleted`), `user_id` (nullable when the email did not match), source IP, and user agent. Email, password material, and token material are never logged.
- Q: Should Phase 2 lock an account after N failed login attempts? → A: No. Account lockout is deferred to Phase 10 alongside rate limiting. Phase 2 relies on Argon2id's per-attempt cost as the online-brute-force defense, with FR-019 audit logs as the detection signal.
- Q: Is the session cookie persistent across browser restart? → A: Yes — persistent cookie with `Max-Age = 30 days`, refreshed to "now + 30 days" on each authenticated request so the cookie expiry tracks the server-side rolling expiry in FR-009.
- Q: How many concurrent sessions may one user hold? → A: Unbounded. A user may have any number of concurrent sessions across devices; the constitution's revocation guarantees still hold via FR-010 and FR-011 deleting all of that user's sessions on admin password change or soft-delete.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Successful login (Priority: P1)

A registered user opens the app, enters their email and password on the login page, and is taken to a stub `/medications` page (which Phase 3 will fill with real medication content). A server-side session is established and a signed, HTTP-only cookie is placed in the browser so subsequent requests are authenticated automatically.

**Why this priority**: This is the gateway to every other feature. Without it, no persona — Granny, Billy, Molly, Harry, or Dan — can use the app at all. It is also the smallest credible auth slice; everything else in this phase builds on it.

**Independent Test**: Seed a user via `medminder-admin user add`, navigate to the login page, submit the seeded credentials, observe a redirect to the stub `/medications` page, observe a `sessions` row created for that user, and observe the response sets a signed `HttpOnly` `SameSite=Lax` cookie. Hitting `/api/me` with that cookie returns the authenticated user's `{ id, name, role }`; hitting `/api/me` without the cookie returns 401.

**Acceptance Scenarios**:

1. **Given** an active user with a known password, **When** the user submits matching email and password on the login page, **Then** the server creates one new `sessions` row, sets the signed session cookie on the response, and the browser is redirected to `/medications` (a stub page in Phase 2; enriched in Phase 3).
2. **Given** a successful login response, **When** the browser issues a request to `/api/me` with the cookie, **Then** the request is authenticated and the response contains the user's `id`, `name`, and `role`.

---

### User Story 2 — Logout (Priority: P1)

An authenticated user clicks the logout button. Their server-side session row is deleted, the cookie is cleared, and the browser is taken to the login page.

**Why this priority**: Logout is the user-facing half of revocation. It is required for shared-device safety and for the constitution's revocation guarantee. It is also the simplest write path on the auth surface, which makes it a good early gate for cookie handling.

**Independent Test**: From an authenticated browser, click logout. Confirm: the `sessions` row is gone from the database; the response clears the cookie; the user lands on the login page; subsequent requests with the (now-stale) cookie are rejected with 401.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a valid session cookie, **When** the logout endpoint is called, **Then** the matching `sessions` row is deleted, the response clears the session cookie, and the user is redirected to the login page.
2. **Given** the same logout endpoint, **When** it is called twice (e.g., double-clicked or two tabs logging out simultaneously), **Then** the second call succeeds idempotently with no error.

---

### User Story 3 — Failed login is timing-safe and uniform (Priority: P1)

A login attempt with a wrong password, an unknown email, or an email belonging to a soft-deleted user produces the same generic error and takes a comparable amount of time. No information about which condition occurred is leaked through the response body or its timing.

**Why this priority**: Without this, the login form is a user-enumeration oracle. The constitution makes user-enumeration prevention non-negotiable (Principle I), and the user stories (UC-2.2, UC-2.3) call for identical behavior across all three failure modes.

**Independent Test**: Submit (a) a wrong password for an existing user, (b) a password for an email that does not exist, and (c) a password for an email that exists but whose `deleted_at` is set. All three responses are identical in body and status, and their wall-clock response times do not allow an external observer to distinguish them.

**Acceptance Scenarios**:

1. **Given** a wrong password for an active user, **When** the login endpoint is called, **Then** the response is the same generic error message and no `sessions` row is created and no cookie is set.
2. **Given** an email that does not match any user, **When** the login endpoint is called, **Then** the response is identical to the wrong-password case in body, status, and observable timing.
3. **Given** an email that matches a soft-deleted user (`deleted_at` is set), **When** the login endpoint is called, **Then** the response is identical to the unknown-email case.

---

### User Story 4 — Auth-required route guards (Priority: P1)

Protected backend endpoints reject requests without a valid session with HTTP 401. Protected frontend routes redirect unauthenticated visitors to the login page. An expired session is treated as no session.

**Why this priority**: Login and logout are inert without enforcement. This story is the actual access-control boundary; without it the cookie does no work.

**Independent Test**: Hit `/api/me` (the example protected endpoint Phase 2 introduces for this purpose) with no cookie, with a tampered cookie, and with an expired session — each must return 401. Navigate to `/medications` without auth and observe a redirect to `/login`; with a valid session, `/medications` loads.

**Acceptance Scenarios**:

1. **Given** no session cookie, **When** the client requests a protected backend endpoint, **Then** the server returns 401 and does not perform the action.
2. **Given** a cookie whose signature does not verify, **When** the client requests a protected endpoint, **Then** the server returns 401 and treats the cookie as absent.
3. **Given** a session whose `expires_at` is in the past, **When** the client requests a protected endpoint, **Then** the server returns 401 and the expired row is not extended.
4. **Given** an unauthenticated browser, **When** the user navigates to a protected frontend route, **Then** the app redirects to `/login` and does not display protected content.

---

### User Story 5 — Forced logout on admin password change (Priority: P2)

When an admin uses the CLI to change a user's password, every existing session for that user is invalidated immediately. Any browser tab that was logged in as that user receives a 401 on its next request and is bounced to the login page.

**Why this priority**: This is half of the constitution's revocation requirement. It belongs in this phase because it is the canonical reason server-side sessions were chosen over JWTs in ADR-0001. Marked P2 because it depends on Stories 1, 2, and 4 being in place; the slice itself is small.

**Independent Test**: Log in user X in browser A. Run `medminder-admin user update <id> --password ...` in a terminal. From browser A, issue any authenticated request. Observe 401 and a redirect to the login page. Confirm that all `sessions` rows for user X have been removed.

**Acceptance Scenarios**:

1. **Given** user X is authenticated in one or more browsers, **When** the admin CLI changes user X's password, **Then** all `sessions` rows for user X are deleted and any subsequent request from those browsers receives a 401 and is redirected to the login page.

---

### User Story 6 — Forced logout on admin soft-delete (Priority: P2)

When an admin soft-deletes a user, every existing session for that user is invalidated immediately and the user can no longer log in.

**Why this priority**: The other half of the revocation requirement. Same dependency profile and same priority logic as Story 5.

**Independent Test**: Log in user X in browser A. Run `medminder-admin user delete <id>` in a terminal. Confirm: all of user X's `sessions` rows are gone; browser A receives 401 on its next request and is redirected to the login page; a fresh login attempt for user X's email returns the same generic error as an unknown email.

**Acceptance Scenarios**:

1. **Given** user X is authenticated, **When** the admin CLI soft-deletes user X, **Then** all `sessions` rows for user X are deleted, the next authenticated request from any of user X's browsers receives 401, and a fresh login attempt for that email returns the unknown-email generic error.

---

### User Story 7 — Rolling 30-day session expiry (Priority: P2)

A session is valid for 30 days from its creation. Each authenticated request extends the expiry to 30 days from "now". A session that has been idle for 30 days is rejected as expired.

**Why this priority**: Expiry is a hard constraint of the auth model and the spec must commit to a policy. P2 because Stories 1–4 are usable without it (sessions would simply never expire in dev), but production must not ship without a defined lifetime.

**Independent Test**: Create a session, advance the clock by 29 days, issue an authenticated request, observe the request succeeds and `expires_at` has been extended to 30 days from the new "now". Then advance the clock by another 31 days without any request, issue a request, observe 401 and that the row is treated as expired.

**Acceptance Scenarios**:

1. **Given** a session created at time T, **When** the client makes any authenticated request at time T + 29 days, **Then** the request is accepted and the session's `expires_at` is extended to "now + 30 days".
2. **Given** a session whose `expires_at` is in the past, **When** any request is made with that cookie, **Then** the server returns 401 and the session row is not extended.

---

### Edge Cases

- **Cookie missing vs cookie tampered**: A missing cookie and a cookie whose signature does not verify both produce 401 and are logged identically (no signal to attackers about whether they "almost had it").
- **Session row deleted out-of-band**: If the `sessions` row referenced by an otherwise-valid cookie has been deleted (forced logout, manual DB action), the next request returns 401 as if the cookie never existed.
- **Clock skew**: Expiry comparisons use database "now" (server-authoritative), not client clock. A client whose clock is wrong cannot extend or shorten its own session.
- **Concurrent logout from two tabs**: Both tabs may issue logout against the same session. The first deletes the row and clears the cookie; the second succeeds with no error (idempotent).
- **Login while already logged in**: If a valid session cookie is present when the login endpoint is called, the existing session is replaced with a fresh one (old row deleted, new row created). The user is not silently logged in as the old user if they submit different credentials.
- **Whitespace in credentials**: Email is matched case-insensitively (consistent with admin CLI per UC-1.1) and trimmed of leading/trailing whitespace; passwords are compared exactly with no normalization.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The login endpoint MUST accept email and password and, on success, create exactly one `sessions` row and set a session cookie on the response.
- **FR-002**: The session token MUST be a freshly generated random value at least 256 bits in size; the database MUST store only the SHA-256 hash of that token; the plaintext token MUST NOT be persisted or written to any log.
- **FR-003**: The session cookie MUST be signed, MUST have `HttpOnly`, MUST have `SameSite=Lax`, and MUST have `Secure` set in any non-development environment. The cookie MUST be persistent (i.e. set `Max-Age` so it survives browser restart) and its `Max-Age` MUST be refreshed to 30 days on each authenticated response so it stays in sync with the server-side rolling expiry in FR-009.
- **FR-004**: A failed login MUST return a single generic error and MUST NOT reveal whether the email exists, including via response timing observable to a remote attacker.
- **FR-005**: A login attempt against a soft-deleted user (`deleted_at IS NOT NULL`) MUST be treated identically to an unknown-email attempt.
- **FR-006**: The logout endpoint MUST delete the current `sessions` row, MUST clear the session cookie on the response, and MUST be idempotent under repeated calls.
- **FR-007**: Every protected backend endpoint MUST reject any request that does not present a valid, signed cookie matching an unexpired `sessions` row, with HTTP 401.
- **FR-008**: The frontend MUST redirect unauthenticated navigations to the login page and MUST clear cached query state when any authenticated request returns 401.
- **FR-009**: A `sessions` row MUST expire 30 days after its creation, and its expiry MUST be extended to 30 days from "now" on each authenticated request that successfully validates it (rolling expiry).
- **FR-010**: When the admin CLI changes a user's password, the system MUST delete every `sessions` row belonging to that user.
- **FR-011**: When the admin CLI soft-deletes a user, the system MUST delete every `sessions` row belonging to that user.
- **FR-012**: The login and logout flows MUST log only non-PII identifiers (user `id`, never email; never password material; never token material in plaintext or hashed form).
- **FR-013**: The login flow MUST reuse the existing `medminder.domain.passwords.verify_password` helper for password comparison; no parallel hashing or comparison implementation is permitted.
- **FR-014**: The login flow MUST reuse `medminder.domain.users.get_user_by_email` (with `include_deleted=False`) for user lookup.
- **FR-015**: A sequence diagram describing the login flow MUST be added under `docs/diagrams/` as part of this phase, per the per-phase exit criteria in the roadmap.
- **FR-016**: When a login is submitted while a valid session cookie is already present, the existing session MUST be replaced — the prior `sessions` row deleted and a new one created — so credentials submitted in the new attempt are the ones that determine the resulting identity.
- **FR-017**: Phase 2 MUST introduce a frontend route at `/medications` as a placeholder destination for successful login. The route MUST require authentication and MUST display content indicating the medication list is not yet populated. Phase 3 (Medications CRUD) enriches the same route; the redirect target does not change between phases.
- **FR-018**: Phase 2 MUST introduce a protected backend endpoint that, on a valid session, returns the authenticated user's `id`, `name`, and `role`, and on an invalid or missing session returns HTTP 401. The route is declared at `/me` on the backend; the browser reaches it as `/api/me` via the Vite dev proxy and the production reverse proxy (both strip the `/api` prefix). This endpoint serves as the canonical target for route-guard automated tests.
- **FR-019**: Every login attempt (successful and failed) MUST be logged at INFO level with an outcome enum (`success` | `wrong_password` | `unknown_email` | `soft_deleted`), the `user_id` if a matching user was found (otherwise `null`), the source IP, and the user agent. The `source_ip` MUST be derived server-side from the request's peer address, or — when the deployment terminates TLS at a trusted reverse proxy — from the leftmost entry of that proxy's forwarded-for header per the deployment's reverse-proxy configuration; it MUST NOT be a client-supplied header value accepted unconditionally. The `user_agent` is the request's `User-Agent` header value as received. The email address, the password (in any form), and any session token material MUST NOT appear in the log record.

### Key Entities

- **Session**: An authenticated browsing context for one user. Already represented by the existing `sessions` table introduced in Phase 1, with columns `id`, `user_id`, `token_hash`, `expires_at`, `created_at`. Phase 2 introduces no schema change to this table; if rolling expiry is implemented by writing to `expires_at` directly, no new column is needed. (Whether a separate `last_seen_at` column is introduced is an implementation choice for the plan phase.)
- **User**: Already represented by the existing `users` table from Phase 1. Phase 2 reads `email` (case-insensitive match), `password_hash` (via `verify_password`), and `deleted_at` (to apply FR-005). Phase 2 does not add fields to `users`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A registered user can complete login and reach the `/medications` page in under 2 seconds end-to-end on a typical home connection.
- **SC-002**: The wall-clock response-time difference between "wrong password", "unknown email", and "soft-deleted user" login attempts, measured at the 95th percentile across 100 trials, is under 50 ms.
- **SC-003**: Logout removes the targeted `sessions` row in 100 % of automated test runs and tolerates double invocation without error.
- **SC-004**: After an admin password change or soft-delete, zero subsequent requests on previously authenticated browsers are accepted; the next request from each such browser receives 401.
- **SC-005**: For every endpoint declared protected, an automated check confirms it returns 401 when called without a session cookie and 401 when called with a tampered cookie.
- **SC-006**: A scan of application logs and CI test-run logs from the merge build contains zero occurrences of password material, plaintext session tokens, or session token hashes.
- **SC-007**: The `docs/diagrams/` directory contains a login-flow sequence diagram that matches the implemented flow at merge time.

## Assumptions

- "Generic error" wording is a single user-facing message such as "Email or password is incorrect." Final copy is decided in the plan phase.
- Email match is case-insensitive (consistent with admin CLI behavior in UC-1.1) and trimmed of leading and trailing whitespace before lookup; password is compared exactly with no normalization.
- Rate limiting on the login endpoint is **out of scope** for this phase and deferred to Phase 10 (Hardening). The spec does not impose a rate-limit FR.
- Account lockout after N failed login attempts is **out of scope** for this phase and deferred to Phase 10. Argon2id's per-attempt cost is the online-brute-force defense in Phase 2; FR-019 logs are the detection signal an admin reviews.
- Password reset and email verification are **out of scope**. Per the mission, password recovery in v1 is the admin CLI path.
- Multi-factor authentication, "remember me", and a self-service "log out everywhere" UI are **out of scope** for this phase.
- Cross-site request forgery protection in this phase relies on `SameSite=Lax`; explicit CSRF tokens are deferred to Phase 10 (Hardening). The spec does not impose a CSRF-token FR.
- Whether rolling expiry is implemented by mutating `expires_at` on each authenticated request, or by introducing a separate `last_seen_at` column, is an implementation detail to be settled in the plan phase; FR-009 only fixes the externally observable behavior.
- The `sessions` table introduced in Phase 1 already has the columns this phase needs (`id`, `user_id`, `token_hash`, `expires_at`, `created_at`); no Alembic migration is anticipated.
- A user may hold an unbounded number of concurrent sessions across browsers and devices. There is no per-user session cap and no automatic eviction of older sessions when a new one is created on a different device. Same-browser re-login still replaces the prior session per FR-016.
