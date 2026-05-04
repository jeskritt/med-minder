# Security Requirements Quality Checklist: Phase 2 — Auth (login / logout)

**Purpose**: Validate that the security requirements written in `spec.md` (and elaborated in `plan.md` / `research.md` / `contracts/auth.openapi.yaml`) are complete, clear, consistent, measurable, and appropriately scoped before merge. This is a release-gate checklist — every item must be resolved (`[x]` answered or `[~]` deferred to a documented PR-time artifact) before the Phase 2 PR merges.
**Created**: 2026-05-02
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [research.md](../research.md) · [contracts/auth.openapi.yaml](../contracts/auth.openapi.yaml)

**Audience**: PR reviewer. Items reference spec sections (`Spec §FR-XXX`) wherever possible so a reviewer can locate the source-of-truth in one click. Items marked `[Gap]` test for the *absence* of a requirement that should exist.

## Authentication Requirement Completeness

- [x] CHK001 Are credential-input requirements (email format, password input shape, normalization rules) specified for every credential-handling endpoint? [Completeness, Spec §FR-001, §Edge Cases — whitespace]
- [x] CHK002 Is the password-comparison primitive specified by name, with a binding "no parallel implementation" rule? [Completeness, Spec §FR-013]
- [x] CHK003 Is the user-lookup primitive specified by name, including the `include_deleted` posture? [Completeness, Spec §FR-014]
  <!-- FR-014 specifies `include_deleted=False`. Implementation now uses `include_deleted=False` per the review fix. -->
- [x] CHK004 Are requirements for the example protected endpoint (`/me`) specified — including its response payload shape and the 401 contract? [Completeness, Spec §FR-018]
- [x] CHK005 Are requirements specified for the destination route after successful login (`/medications`), including its auth-required posture? [Completeness, Spec §FR-017]
- [x] CHK006 Are concurrent-session requirements specified (cap, eviction policy, behavior when one is created on a new device)? [Completeness, Spec §Clarifications 2026-05-02 Q5, §Assumptions]

## Session Token & Cookie Requirement Quality

- [x] CHK007 Is the session-token entropy floor quantified with a specific bit count? [Clarity, Spec §FR-002]
  <!-- "at least 256 bits"; implementation: `secrets.token_urlsafe(32)` = 256 bits. -->
- [x] CHK008 Is the database-stored representation of the token specified by algorithm name (not "a hash")? [Clarity, Spec §FR-002]
  <!-- "SHA-256 hash" in spec; `hashlib.sha256` in implementation. -->
- [x] CHK009 Is the prohibition on persisting or logging the plaintext token explicit, including the prohibition on logging the *hashed* form? [Completeness, Spec §FR-002, §FR-012]
- [x] CHK010 Are required cookie attributes — `HttpOnly`, `SameSite`, `Secure` (and the environment under which `Secure` toggles), `Max-Age`, persistence — each specified? [Completeness, Spec §FR-003]
- [x] CHK011 Is the cookie-signing requirement explicit (not just "cookie is set")? [Clarity, Spec §FR-003]
  <!-- "signed" in spec; `URLSafeTimedSerializer` in implementation. -->
- [ ] CHK012 Are `Path` and `Domain` requirements for the cookie specified, or is the absence of a constraint stated? [Gap, Spec §FR-003]
  <!-- Gap: spec says nothing about Path/Domain. Implementation sets `path="/"`. Domain defaults to the origin. -->
- [x] CHK013 Is the relationship between client-side cookie `Max-Age` and server-side `expires_at` defined unambiguously (one tracks the other on every authenticated response)? [Consistency, Spec §FR-003 ↔ §FR-009]
- [x] CHK014 Is "non-development environment" defined precisely enough that a reviewer can identify which deployments must set `Secure`? [Clarity, Spec §FR-003]
  <!-- Settings: `session_cookie_secure` returns `self.env != "development"`. -->

## User-Enumeration & Timing-Uniform Failure

- [x] CHK015 Are the three failure modes (wrong password, unknown email, soft-deleted user) explicitly enumerated as the set that must be observationally identical? [Completeness, Spec §FR-004, §FR-005, §US-3]
- [x] CHK016 Is the timing-uniformity requirement quantified with a specific metric and percentile? [Measurability, Spec §SC-002]
  <!-- "p95 across 100 trials, under 50 ms". -->
- [x] CHK017 Is the equivalence between "soft-deleted" and "unknown email" specified for *all* endpoints that take an email (login, future password reset), or only login? [Coverage, Spec §FR-005, §US-6]
  <!-- FR-005 is login-scoped. Password reset is out of scope (§Assumptions). -->
- [x] CHK018 Is the requirement consistent between body, status, and timing — i.e. is it explicit that all three dimensions must be uniform, not just the body? [Consistency, Spec §FR-004, §SC-002, §US-3 Independent Test]
- [x] CHK019 Is the user-enumeration prohibition tied back to a constitution principle so reviewers can challenge any deviation against the binding source? [Traceability, Spec §FR-004 → Constitution §I]

## Session Lifecycle & Revocation

- [x] CHK020 Are the events that delete a session row enumerated exhaustively (logout, admin password change, admin soft-delete, FR-016 re-login)? [Completeness, Spec §FR-006, §FR-010, §FR-011, §FR-016]
- [x] CHK021 Is logout's idempotency requirement explicit, with the failure mode it covers (double-click, two tabs)? [Clarity, Spec §FR-006, §US-2]
- [x] CHK022 Are revocation requirements specified to apply to *all* of a user's sessions, not just the current one, on admin password change? [Completeness, Spec §FR-010]
  <!-- "delete every `sessions` row belonging to that user." Implementation: `revoke_all_user_sessions`. -->
- [x] CHK023 Are revocation requirements specified to apply to *all* of a user's sessions on admin soft-delete? [Completeness, Spec §FR-011]
- [x] CHK024 Is the atomicity requirement between password-change/soft-delete and session-revocation specified (or is partial failure intentionally permitted)? [Gap, Spec §FR-010, §FR-011]
  <!-- Implementation: both `update_user` and `soft_delete_user` call `revoke_all_user_sessions` inside the same transaction (same `session.begin()` block). Atomic. Spec doesn't explicitly state atomicity but "MUST delete" implies it. -->
- [x] CHK025 Is the requirement that a failed login does NOT delete the existing session specified, distinct from FR-016's success-only replacement rule? [Clarity, Spec §FR-016, §Edge Cases — Login while already logged in]
  <!-- Contract: "A failed login does NOT delete any pre-existing session." Test: `test_failed_relogin_preserves_existing_session`. -->

## Rolling Expiry

- [x] CHK026 Is the session lifetime quantified with a specific duration? [Clarity, Spec §FR-009]
  <!-- "30 days". `SESSION_LIFETIME = timedelta(days=30)`. -->
- [x] CHK027 Is the trigger for extension specified (which class of request extends, which does not)? [Clarity, Spec §FR-009]
  <!-- "each authenticated request that successfully validates it". -->
- [x] CHK028 Is the source of "now" specified as server-authoritative, not client-supplied? [Clarity, Spec §Edge Cases — Clock skew]
- [x] CHK029 Is the "expired session" rejection requirement explicit about not extending the row on the failed read? [Completeness, Spec §FR-009 Acceptance Scenario 2]
  <!-- Test: `test_expired_session_not_extended` verifies `expires_at` unchanged. -->
- [x] CHK030 Is the implementation choice between mutating `expires_at` and adding `last_seen_at` correctly framed as out-of-scope for the spec (FR-009 only fixes observable behavior)? [Consistency, Spec §Assumptions, §Key Entities — Session]

## Logging & Audit Trail (FR-019)

- [x] CHK031 Is the set of login outcomes that must be logged enumerated as a closed enum? [Completeness, Spec §FR-019]
  <!-- `LoginOutcome` StrEnum: SUCCESS, WRONG_PASSWORD, UNKNOWN_EMAIL, SOFT_DELETED. -->
- [x] CHK032 Is the log fidelity (level, fields included) specified per attempt, not just per session? [Clarity, Spec §FR-019]
  <!-- "Every login attempt…MUST be logged at INFO level with an outcome enum, user_id, source IP, and user agent." -->
- [x] CHK033 Is the prohibition on logging the email, password material, and token material explicit, with token material covering both plaintext and hashed forms? [Completeness, Spec §FR-019, §FR-012]
- [x] CHK034 Are nullable fields (`user_id` when no user matched) specified explicitly so log consumers can rely on the schema? [Clarity, Spec §FR-019]
  <!-- "the `user_id` if a matching user was found (otherwise `null`)". Implementation logs "none". -->
- [x] CHK035 Are the source-IP and user-agent requirements specified to be captured server-side (not client-supplied via a header that could be spoofed unchallenged)? [Gap, Spec §FR-019]
  <!-- FR-019: "derived server-side from the request's peer address, or…from the leftmost entry of that proxy's forwarded-for header per the deployment's reverse-proxy configuration; it MUST NOT be a client-supplied header value accepted unconditionally." Implementation: `_client_ip` with `trusted_proxy_count`. User-agent logged as actual value per review fix. -->
- [x] CHK036 Is the SC-006 verification mechanism (log scan for forbidden tokens) specified concretely enough to be automated? [Measurability, Spec §SC-006]
  <!-- "A scan of application logs and CI test-run logs from the merge build contains zero occurrences of password material, plaintext session tokens, or session token hashes." Test: `test_attempt_login_log_lines_are_pii_free`. -->
- [ ] CHK037 Are logout and `/me` requests covered by any logging requirement, or is logging intentionally limited to login attempts? [Coverage, Gap]
  <!-- Gap: FR-019 only covers login attempts. No logging requirement for logout or /me. Intentional scope limitation. -->

## Cross-Site & Transport Security

- [x] CHK038 Is the CSRF posture specified as `SameSite=Lax` with a statement that explicit CSRF tokens are deferred, naming the destination phase? [Completeness, Spec §Assumptions — CSRF]
  <!-- "deferred to Phase 10 (Hardening)". -->
- [x] CHK039 Is the residual CSRF risk under `SameSite=Lax` (top-level GET navigations from third-party sites) acknowledged, given that login/logout are POST? [Coverage, Gap, Spec §Assumptions — CSRF]
  <!-- Login and logout are POST-only. SameSite=Lax blocks cross-site POST. Residual risk is GET navigations, but all state-changing endpoints are POST. -->
- [x] CHK040 Is HTTPS-only transport implicit from the constitution or restated in the phase requirements? [Traceability, Constitution §I — Encrypt in transit]
  <!-- FR-003: "`Secure` set in any non-development environment". Constitution §I referenced in plan. -->
- [x] CHK041 Are CORS requirements for cookie-bearing requests specified (or is the absence of cross-origin auth explicit)? [Gap, Spec §FR-003]
  <!-- app.py: `allow_credentials=True`, `allow_origins=settings.cors_origins`. Settings default: `["http://localhost:5173"]`. Same-origin in production. -->

## Phase 10 Deferrals — Documented & Justified

- [x] CHK042 Is the rate-limit deferral named with the destination phase and the residual-risk mitigation Phase 2 relies on (Argon2id per-attempt cost + FR-019 audit log)? [Completeness, Spec §Assumptions — Rate limiting, §Clarifications Q3]
- [x] CHK043 Is the account-lockout deferral named with the destination phase and the residual-risk mitigation? [Completeness, Spec §Assumptions — Lockout, §Clarifications Q3]
- [x] CHK044 Is the explicit-CSRF-token deferral named with the destination phase? [Completeness, Spec §Assumptions — CSRF]
- [x] CHK045 Is the password-reset deferral named, with the v1 admin-CLI fallback path? [Completeness, Spec §Assumptions — Password reset]
- [x] CHK046 Is the multi-factor-authentication / "remember me" / "log out everywhere" deferral named (or stated as never-in-v1)? [Completeness, Spec §Assumptions]
- [x] CHK047 For each deferral, can a reviewer locate the destination phase in `specs/roadmap.md` without ambiguity? [Traceability, §Assumptions ↔ specs/roadmap.md]
  <!-- Phase 10 — Hardening is clearly defined in roadmap.md. -->

## Acceptance Criteria Quality

- [x] CHK048 Is SC-001 ("login under 2 s") quantified with the network condition under which it must hold? [Clarity, Spec §SC-001]
  <!-- "on a typical home connection". -->
- [x] CHK049 Is SC-002 ("p95 timing delta ≤ 50 ms over 100 trials") accompanied by an unambiguous trial-construction rule (paired vs independent samples)? [Clarity, Spec §SC-002]
  <!-- "measured at the 95th percentile across 100 trials". Plan §2.5: "100 paired trials per failure-mode pair". -->
- [x] CHK050 Is SC-005 ("every endpoint declared protected") backed by a definition of which endpoints are "protected" so the automated check has a knowable target list? [Clarity, Spec §SC-005]
  <!-- Phase 2 protected endpoints: /me. /medications is frontend-only. /auth/logout is session-required-or-no-op. -->
- [x] CHK051 Are the acceptance scenarios in US-3 (failed login) symmetric with the FR-004/§FR-005 obligations (no body, status, *or* timing leak)? [Consistency, Spec §US-3 ↔ §FR-004 ↔ §FR-005]
- [x] CHK052 Is each Functional Requirement (FR-001…FR-019) covered by at least one Success Criterion or Acceptance Scenario? [Coverage, Traceability]

## Threat-Consideration Coverage

- [x] CHK053 Does the spec / plan name the new surface area introduced by Phase 2 in a single enumerable list (endpoints, cookie, log line, dependency, setting)? [Completeness, Constitution §I]
  <!-- Plan Constitution Check §I lists: "POST /auth/login, POST /auth/logout, GET /me, a signed session cookie, a structured login-attempt log line (FR-019), the itsdangerous dependency, and a SESSION_SECRET setting." -->
- [x] CHK054 Is a threat consideration written for each item of new surface area, per the constitution's "every new surface area requires explicit threat consideration" rule? [Coverage, Constitution §I]
- [x] CHK055 Is the cookie-tampering threat explicitly covered, including the requirement that tampered and missing cookies are indistinguishable to the client? [Coverage, Spec §Edge Cases — Cookie missing vs tampered]
- [x] CHK056 Is the out-of-band session deletion threat covered (row deleted, cookie still present)? [Coverage, Spec §Edge Cases — Session row deleted out-of-band]
- [ ] CHK057 Is the threat of `SESSION_SECRET` rotation/leak considered in the requirements (recovery procedure, blast radius)? [Gap]
  <!-- Gap: Settings docstring mentions "Rotating the value invalidates every outstanding cookie on next request — by design" but no formal recovery procedure is documented. -->
- [x] CHK058 Is the threat of Argon2id parameter drift between user creation and login considered (verify path must tolerate older parameters)? [Gap, Spec §FR-013]
  <!-- argon2-cffi's `PasswordHasher.verify` handles parameter drift natively (encoded in the hash string). -->

## Dependencies & Assumptions

- [x] CHK059 Are external library additions (signing library) named, with a version-pinning constraint per Constitution §V? [Completeness, Constitution §V]
  <!-- pyproject.toml: `itsdangerous>=2.2.0,<3.0`. Plan: "itsdangerous ≥2.2,<3.0". -->
- [x] CHK060 Is the dependency on Phase 1's `users` and `sessions` tables stated as an assumption, with confirmation that no schema change is anticipated? [Completeness, Spec §Key Entities, §Assumptions]
- [x] CHK061 Is the dependency on Phase 1's `medminder.domain.passwords` and `medminder.domain.users` modules stated, with the no-fork constraint? [Completeness, Spec §FR-013, §FR-014]
- [x] CHK062 Is the dependency on `docs/diagrams/` (sequence diagram delivery) stated as a hard exit criterion? [Completeness, Spec §FR-015, §SC-007, Constitution §IV]
  <!-- `docs/diagrams/login-sequence.md` exists. -->

## Ambiguities & Conflicts

- [x] CHK063 Is the "generic error" final wording either fixed in the spec or explicitly deferred to plan/implementation? [Clarity, Spec §Assumptions]
  <!-- Spec: "such as 'Email or password is incorrect.' Final copy is decided in the plan phase." Implementation uses that exact string. -->
- [x] CHK064 Is the case-insensitive email match consistent with Phase 1's `users.email` `LOWER()` unique index, and is this consistency stated? [Consistency, Spec §FR-014, §Edge Cases — Whitespace, §Assumptions]
  <!-- `get_user_by_email` uses `func.lower(User.email) == normalized` where `normalized = email.strip().lower()`. Consistent with the LOWER() index. -->
- [x] CHK065 Are there conflicting requirements between FR-016 ("re-login replaces session") and the Edge Case on "concurrent logout from two tabs" (idempotent logout)? Are both reachable from the same handler without contradiction? [Conflict, Spec §FR-016 ↔ §Edge Cases]
  <!-- No conflict. FR-016 is login-handler logic (delete old, create new). Concurrent logout is logout-handler logic (idempotent delete). Different handlers. -->
- [x] CHK066 Is the requirement-traceability scheme (FR-NNN, SC-NNN, USx) used consistently between `spec.md`, `plan.md`, and the contracts? [Traceability]

## Notes

- Check items off as completed: `[x]`. Items deferred to a PR-time artifact (e.g. test results from CI, log scan output) may be `[~]` with a one-line link.
- Add comments or findings inline below the item.
- An unresolved item is a merge-blocker. The PR author should resolve by either (a) updating the spec/plan to add or clarify the requirement and re-running the affected check, (b) explicitly recording an out-of-scope deferral with a destination phase, or (c) opening a follow-up tracked issue and citing it in the item.
- This checklist tests **the requirements**, not the implementation. Items that ask "does the code work?" belong in `validation.md` or the PR review, not here.
