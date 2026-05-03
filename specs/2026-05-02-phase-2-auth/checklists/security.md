# Security Requirements Quality Checklist: Phase 2 — Auth (login / logout)

**Purpose**: Validate that the security requirements written in `spec.md` (and elaborated in `plan.md` / `research.md` / `contracts/auth.openapi.yaml`) are complete, clear, consistent, measurable, and appropriately scoped before merge. This is a release-gate checklist — every item must be resolved (`[x]` answered or `[~]` deferred to a documented PR-time artifact) before the Phase 2 PR merges.
**Created**: 2026-05-02
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [research.md](../research.md) · [contracts/auth.openapi.yaml](../contracts/auth.openapi.yaml)

**Audience**: PR reviewer. Items reference spec sections (`Spec §FR-XXX`) wherever possible so a reviewer can locate the source-of-truth in one click. Items marked `[Gap]` test for the *absence* of a requirement that should exist.

## Authentication Requirement Completeness

- [ ] CHK001 Are credential-input requirements (email format, password input shape, normalization rules) specified for every credential-handling endpoint? [Completeness, Spec §FR-001, §Edge Cases — whitespace]
- [ ] CHK002 Is the password-comparison primitive specified by name, with a binding "no parallel implementation" rule? [Completeness, Spec §FR-013]
- [ ] CHK003 Is the user-lookup primitive specified by name, including the `include_deleted` posture? [Completeness, Spec §FR-014]
- [ ] CHK004 Are requirements for the example protected endpoint (`/me`) specified — including its response payload shape and the 401 contract? [Completeness, Spec §FR-018]
- [ ] CHK005 Are requirements specified for the destination route after successful login (`/medications`), including its auth-required posture? [Completeness, Spec §FR-017]
- [ ] CHK006 Are concurrent-session requirements specified (cap, eviction policy, behavior when one is created on a new device)? [Completeness, Spec §Clarifications 2026-05-02 Q5, §Assumptions]

## Session Token & Cookie Requirement Quality

- [ ] CHK007 Is the session-token entropy floor quantified with a specific bit count? [Clarity, Spec §FR-002]
- [ ] CHK008 Is the database-stored representation of the token specified by algorithm name (not "a hash")? [Clarity, Spec §FR-002]
- [ ] CHK009 Is the prohibition on persisting or logging the plaintext token explicit, including the prohibition on logging the *hashed* form? [Completeness, Spec §FR-002, §FR-012]
- [ ] CHK010 Are required cookie attributes — `HttpOnly`, `SameSite`, `Secure` (and the environment under which `Secure` toggles), `Max-Age`, persistence — each specified? [Completeness, Spec §FR-003]
- [ ] CHK011 Is the cookie-signing requirement explicit (not just "cookie is set")? [Clarity, Spec §FR-003]
- [ ] CHK012 Are `Path` and `Domain` requirements for the cookie specified, or is the absence of a constraint stated? [Gap, Spec §FR-003]
- [ ] CHK013 Is the relationship between client-side cookie `Max-Age` and server-side `expires_at` defined unambiguously (one tracks the other on every authenticated response)? [Consistency, Spec §FR-003 ↔ §FR-009]
- [ ] CHK014 Is "non-development environment" defined precisely enough that a reviewer can identify which deployments must set `Secure`? [Clarity, Spec §FR-003]

## User-Enumeration & Timing-Uniform Failure

- [ ] CHK015 Are the three failure modes (wrong password, unknown email, soft-deleted user) explicitly enumerated as the set that must be observationally identical? [Completeness, Spec §FR-004, §FR-005, §US-3]
- [ ] CHK016 Is the timing-uniformity requirement quantified with a specific metric and percentile? [Measurability, Spec §SC-002]
- [ ] CHK017 Is the equivalence between "soft-deleted" and "unknown email" specified for *all* endpoints that take an email (login, future password reset), or only login? [Coverage, Spec §FR-005, §US-6]
- [ ] CHK018 Is the requirement consistent between body, status, and timing — i.e. is it explicit that all three dimensions must be uniform, not just the body? [Consistency, Spec §FR-004, §SC-002, §US-3 Independent Test]
- [ ] CHK019 Is the user-enumeration prohibition tied back to a constitution principle so reviewers can challenge any deviation against the binding source? [Traceability, Spec §FR-004 → Constitution §I]

## Session Lifecycle & Revocation

- [ ] CHK020 Are the events that delete a session row enumerated exhaustively (logout, admin password change, admin soft-delete, FR-016 re-login)? [Completeness, Spec §FR-006, §FR-010, §FR-011, §FR-016]
- [ ] CHK021 Is logout's idempotency requirement explicit, with the failure mode it covers (double-click, two tabs)? [Clarity, Spec §FR-006, §US-2]
- [ ] CHK022 Are revocation requirements specified to apply to *all* of a user's sessions, not just the current one, on admin password change? [Completeness, Spec §FR-010]
- [ ] CHK023 Are revocation requirements specified to apply to *all* of a user's sessions on admin soft-delete? [Completeness, Spec §FR-011]
- [ ] CHK024 Is the atomicity requirement between password-change/soft-delete and session-revocation specified (or is partial failure intentionally permitted)? [Gap, Spec §FR-010, §FR-011]
- [ ] CHK025 Is the requirement that a failed login does NOT delete the existing session specified, distinct from FR-016's success-only replacement rule? [Clarity, Spec §FR-016, §Edge Cases — Login while already logged in]

## Rolling Expiry

- [ ] CHK026 Is the session lifetime quantified with a specific duration? [Clarity, Spec §FR-009]
- [ ] CHK027 Is the trigger for extension specified (which class of request extends, which does not)? [Clarity, Spec §FR-009]
- [ ] CHK028 Is the source of "now" specified as server-authoritative, not client-supplied? [Clarity, Spec §Edge Cases — Clock skew]
- [ ] CHK029 Is the "expired session" rejection requirement explicit about not extending the row on the failed read? [Completeness, Spec §FR-009 Acceptance Scenario 2]
- [ ] CHK030 Is the implementation choice between mutating `expires_at` and adding `last_seen_at` correctly framed as out-of-scope for the spec (FR-009 only fixes observable behavior)? [Consistency, Spec §Assumptions, §Key Entities — Session]

## Logging & Audit Trail (FR-019)

- [ ] CHK031 Is the set of login outcomes that must be logged enumerated as a closed enum? [Completeness, Spec §FR-019]
- [ ] CHK032 Is the log fidelity (level, fields included) specified per attempt, not just per session? [Clarity, Spec §FR-019]
- [ ] CHK033 Is the prohibition on logging the email, password material, and token material explicit, with token material covering both plaintext and hashed forms? [Completeness, Spec §FR-019, §FR-012]
- [ ] CHK034 Are nullable fields (`user_id` when no user matched) specified explicitly so log consumers can rely on the schema? [Clarity, Spec §FR-019]
- [ ] CHK035 Are the source-IP and user-agent requirements specified to be captured server-side (not client-supplied via a header that could be spoofed unchallenged)? [Gap, Spec §FR-019]
- [ ] CHK036 Is the SC-006 verification mechanism (log scan for forbidden tokens) specified concretely enough to be automated? [Measurability, Spec §SC-006]
- [ ] CHK037 Are logout and `/me` requests covered by any logging requirement, or is logging intentionally limited to login attempts? [Coverage, Gap]

## Cross-Site & Transport Security

- [ ] CHK038 Is the CSRF posture specified as `SameSite=Lax` with a statement that explicit CSRF tokens are deferred, naming the destination phase? [Completeness, Spec §Assumptions — CSRF]
- [ ] CHK039 Is the residual CSRF risk under `SameSite=Lax` (top-level GET navigations from third-party sites) acknowledged, given that login/logout are POST? [Coverage, Gap, Spec §Assumptions — CSRF]
- [ ] CHK040 Is HTTPS-only transport implicit from the constitution or restated in the phase requirements? [Traceability, Constitution §I — Encrypt in transit]
- [ ] CHK041 Are CORS requirements for cookie-bearing requests specified (or is the absence of cross-origin auth explicit)? [Gap, Spec §FR-003]

## Phase 10 Deferrals — Documented & Justified

- [ ] CHK042 Is the rate-limit deferral named with the destination phase and the residual-risk mitigation Phase 2 relies on (Argon2id per-attempt cost + FR-019 audit log)? [Completeness, Spec §Assumptions — Rate limiting, §Clarifications Q3]
- [ ] CHK043 Is the account-lockout deferral named with the destination phase and the residual-risk mitigation? [Completeness, Spec §Assumptions — Lockout, §Clarifications Q3]
- [ ] CHK044 Is the explicit-CSRF-token deferral named with the destination phase? [Completeness, Spec §Assumptions — CSRF]
- [ ] CHK045 Is the password-reset deferral named, with the v1 admin-CLI fallback path? [Completeness, Spec §Assumptions — Password reset]
- [ ] CHK046 Is the multi-factor-authentication / "remember me" / "log out everywhere" deferral named (or stated as never-in-v1)? [Completeness, Spec §Assumptions]
- [ ] CHK047 For each deferral, can a reviewer locate the destination phase in `specs/roadmap.md` without ambiguity? [Traceability, §Assumptions ↔ specs/roadmap.md]

## Acceptance Criteria Quality

- [ ] CHK048 Is SC-001 ("login under 2 s") quantified with the network condition under which it must hold? [Clarity, Spec §SC-001]
- [ ] CHK049 Is SC-002 ("p95 timing delta ≤ 50 ms over 100 trials") accompanied by an unambiguous trial-construction rule (paired vs independent samples)? [Clarity, Spec §SC-002]
- [ ] CHK050 Is SC-005 ("every endpoint declared protected") backed by a definition of which endpoints are "protected" so the automated check has a knowable target list? [Clarity, Spec §SC-005]
- [ ] CHK051 Are the acceptance scenarios in US-3 (failed login) symmetric with the FR-004/§FR-005 obligations (no body, status, *or* timing leak)? [Consistency, Spec §US-3 ↔ §FR-004 ↔ §FR-005]
- [ ] CHK052 Is each Functional Requirement (FR-001…FR-019) covered by at least one Success Criterion or Acceptance Scenario? [Coverage, Traceability]

## Threat-Consideration Coverage

- [ ] CHK053 Does the spec / plan name the new surface area introduced by Phase 2 in a single enumerable list (endpoints, cookie, log line, dependency, setting)? [Completeness, Constitution §I]
- [ ] CHK054 Is a threat consideration written for each item of new surface area, per the constitution's "every new surface area requires explicit threat consideration" rule? [Coverage, Constitution §I]
- [ ] CHK055 Is the cookie-tampering threat explicitly covered, including the requirement that tampered and missing cookies are indistinguishable to the client? [Coverage, Spec §Edge Cases — Cookie missing vs tampered]
- [ ] CHK056 Is the out-of-band session deletion threat covered (row deleted, cookie still present)? [Coverage, Spec §Edge Cases — Session row deleted out-of-band]
- [ ] CHK057 Is the threat of `SESSION_SECRET` rotation/leak considered in the requirements (recovery procedure, blast radius)? [Gap]
- [ ] CHK058 Is the threat of Argon2id parameter drift between user creation and login considered (verify path must tolerate older parameters)? [Gap, Spec §FR-013]

## Dependencies & Assumptions

- [ ] CHK059 Are external library additions (signing library) named, with a version-pinning constraint per Constitution §V? [Completeness, Constitution §V]
- [ ] CHK060 Is the dependency on Phase 1's `users` and `sessions` tables stated as an assumption, with confirmation that no schema change is anticipated? [Completeness, Spec §Key Entities, §Assumptions]
- [ ] CHK061 Is the dependency on Phase 1's `medminder.domain.passwords` and `medminder.domain.users` modules stated, with the no-fork constraint? [Completeness, Spec §FR-013, §FR-014]
- [ ] CHK062 Is the dependency on `docs/diagrams/` (sequence diagram delivery) stated as a hard exit criterion? [Completeness, Spec §FR-015, §SC-007, Constitution §IV]

## Ambiguities & Conflicts

- [ ] CHK063 Is the "generic error" final wording either fixed in the spec or explicitly deferred to plan/implementation? [Clarity, Spec §Assumptions]
- [ ] CHK064 Is the case-insensitive email match consistent with Phase 1's `users.email` `LOWER()` unique index, and is this consistency stated? [Consistency, Spec §FR-014, §Edge Cases — Whitespace, §Assumptions]
- [ ] CHK065 Are there conflicting requirements between FR-016 ("re-login replaces session") and the Edge Case on "concurrent logout from two tabs" (idempotent logout)? Are both reachable from the same handler without contradiction? [Conflict, Spec §FR-016 ↔ §Edge Cases]
- [ ] CHK066 Is the requirement-traceability scheme (FR-NNN, SC-NNN, USx) used consistently between `spec.md`, `plan.md`, and the contracts? [Traceability]

## Notes

- Check items off as completed: `[x]`. Items deferred to a PR-time artifact (e.g. test results from CI, log scan output) may be `[~]` with a one-line link.
- Add comments or findings inline below the item.
- An unresolved item is a merge-blocker. The PR author should resolve by either (a) updating the spec/plan to add or clarify the requirement and re-running the affected check, (b) explicitly recording an out-of-scope deferral with a destination phase, or (c) opening a follow-up tracked issue and citing it in the item.
- This checklist tests **the requirements**, not the implementation. Items that ask "does the code work?" belong in `validation.md` or the PR review, not here.
