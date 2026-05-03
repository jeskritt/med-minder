# API Contract Requirements Quality Checklist: Phase 2 — Auth (login / logout)

**Purpose**: Validate that the wire-shape requirements for the three endpoints Phase 2 introduces — `POST /auth/login`, `POST /auth/logout`, `GET /me` — are written precisely enough to regenerate a typed client without ambiguity. Tests payload schemas, status codes, error contracts, header semantics, idempotency, and OpenAPI/regen discipline. Cookie attributes, CSRF posture, and signing requirements are owned by [security.md](./security.md) (CHK007–CHK014, CHK038–CHK041) and are not duplicated here.
**Created**: 2026-05-03
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [contracts/auth.openapi.yaml](../contracts/auth.openapi.yaml) · [data-model.md](../data-model.md)

**Audience**: PR reviewer. Items reference `[Spec §FR-XXX]`, `[Plan]`, or `[Contract]` (the OpenAPI fragment under `contracts/`) so the source-of-truth for each requirement is one click away. Items marked `[Gap]` test for the *absence* of a requirement that the contract reviewer should expect.

## Endpoint Inventory & Surface Area

- [ ] CHK001 Is the closed set of endpoints introduced by Phase 2 enumerated in one place (login, logout, me) so a reviewer can confirm no fourth endpoint sneaks in unannounced? [Completeness, Spec §FR-001/§FR-006/§FR-018, Contract paths]
- [ ] CHK002 Is each endpoint's HTTP method specified, with rejection behavior for the wrong method (e.g. `GET /auth/login`)? [Gap, Contract]
- [ ] CHK003 Is each endpoint's URL path specified literally, with the relationship to the dev `/api` proxy stripping rule called out? [Clarity, Plan §D6]
- [ ] CHK004 Is the auth-posture of every endpoint (public vs session-required) declared, including for `/auth/login` (public) and `/auth/logout` (session-required-or-no-op)? [Completeness, Contract security blocks]
- [ ] CHK005 Are protected routes that exist outside `/me` (e.g. future `/medications` API endpoints) explicitly out-of-scope for Phase 2's contract, with a pointer to where they will be added? [Coverage, Spec §FR-017]

## Request Schema Quality

- [ ] CHK006 Is the `LoginRequest` schema specified with required fields, types, and `additionalProperties` posture? [Completeness, Contract LoginRequest]
- [ ] CHK007 Is the email field's format constraint specified (RFC 5322 vs pragmatic regex vs format: email), and is the maximum length quantified? [Clarity, Contract LoginRequest.email]
- [ ] CHK008 Is the email-normalization rule (lowercase + trim) specified at the contract layer, or only as a server-side behavior? [Coverage, Spec §Edge Cases — Whitespace ↔ Contract]
- [ ] CHK009 Is the password field's minimum/maximum length specified at the wire layer? [Clarity, Spec §FR-013 ↔ Contract]
- [ ] CHK010 Is the password field marked `writeOnly` (or equivalent) so generated documentation does not echo it in response examples? [Completeness, Contract LoginRequest.password]
- [ ] CHK011 Are the request body's content-type requirements specified (`application/json` only vs also `application/x-www-form-urlencoded`)? [Clarity, Contract]
- [ ] CHK012 Is the behavior on a malformed JSON body specified (400 vs 422), distinct from the auth-failure 401? [Completeness, Contract]
- [ ] CHK013 Is the behavior on a missing/empty `Content-Type` header specified? [Gap]
- [ ] CHK014 Are payload-size limits specified (e.g. max body bytes), or is the absence of a limit acknowledged as a Phase 10 hardening item? [Gap]

## Response Schema Quality

- [ ] CHK015 Is the success response shape for `POST /auth/login` specified — body content (or its emptiness via 204 No Content) — and is the rationale documented? [Clarity, Contract /auth/login 204]
- [ ] CHK016 Is the success response shape for `POST /auth/logout` specified, including whether it returns the user that was logged out or 204 No Content? [Clarity, Contract /auth/logout 204]
- [ ] CHK017 Is the `Me` response schema fully enumerated with required fields (id, name, role) and the role enum's closed value set? [Completeness, Spec §FR-018, Contract Me]
- [ ] CHK018 Is the `id` field's format specified (UUID, with v4 vs v7 vs unspecified)? [Clarity, Contract Me.id]
- [ ] CHK019 Is the `role` field guaranteed to be one of `admin` | `user`, matching the database enum from Phase 1? [Consistency, Contract Me.role ↔ Phase 1 schema]
- [ ] CHK020 Are response field nullability rules specified (no nullable fields in `Me` per current contract, but is that explicit)? [Clarity, Contract Me]
- [ ] CHK021 Is `additionalProperties: false` set on every response schema so a future-added field cannot leak through unintentionally? [Completeness, Contract]

## Status Code Coverage

- [ ] CHK022 Is the success status code for each endpoint specified exactly (204 vs 200 with body)? [Clarity, Contract]
- [ ] CHK023 Are all failure status codes per endpoint enumerated (400, 401, 422 if applicable), with the body shape for each? [Completeness, Contract]
- [ ] CHK024 Is the rule that failed login returns the same status code regardless of which failure mode triggered it (wrong-password vs unknown-email vs soft-deleted) specified at the contract layer? [Consistency, Spec §FR-004 ↔ Contract /auth/login 401]
- [ ] CHK025 Is the contract's 401 vs 403 boundary defined (when does a known-bad cookie return 401 vs 403)? [Clarity, Contract]
- [ ] CHK026 Is a 5xx response shape specified, or is the absence of a contract for server-error responses acknowledged? [Gap]
- [ ] CHK027 Is the requirement that an expired session returns 401 (not 403, not silent-204) explicit in the contract, not just in the spec? [Consistency, Spec §FR-007 ↔ Contract /me 401]

## Error Contract Quality

- [ ] CHK028 Is the `Error` schema specified once and reused across endpoints, rather than ad-hoc per endpoint? [Consistency, Contract Error]
- [ ] CHK029 Is the generic-error message string (e.g. "Email or password is incorrect.") fixed in the contract or explicitly deferred to implementation? [Clarity, Spec §Assumptions ↔ Contract example]
- [ ] CHK030 Is the prohibition on echoing the submitted email in the error body specified at the contract layer? [Completeness, Spec §FR-004 ↔ Contract]
- [ ] CHK031 Is the requirement that the 401 body be byte-identical across the three failure modes specified, or only timing-uniform? [Clarity, Spec §FR-004]
- [ ] CHK032 Is a structured error code (machine-readable identifier alongside `detail`) specified, or is its absence acknowledged? [Gap, Contract Error]
- [ ] CHK033 Is the error-response content-type fixed (`application/json` always, even on 401)? [Clarity, Contract]

## Headers & Cookie Semantics (contract-layer only — see security.md for attribute requirements)

- [ ] CHK034 Is the requirement that authenticated responses always set a refreshed `Set-Cookie` (cookie attribute refresh on every authenticated request) specified at the contract layer, not only in the implementation plan? [Coverage, Spec §FR-003 ↔ Contract /me]
- [ ] CHK035 Is the cookie-name parameterization (one fixed name `mm_session` vs configurable) declared as a stable contract? [Clarity, Plan §D3 ↔ Contract securitySchemes]
- [ ] CHK036 Is the requirement that logout's response clears the cookie via `Set-Cookie` (rather than expecting the client to delete it) specified at the contract layer? [Clarity, Contract /auth/logout]
- [ ] CHK037 Are headers a client must send (Cookie, Content-Type) and headers a client may rely on (Set-Cookie) enumerated, distinct from headers the server uses internally (X-Forwarded-For for IP capture)? [Completeness, Gap]
- [ ] CHK038 Is the `User-Agent` header's role (logged per FR-019, but not authenticated against) specified? [Clarity, Spec §FR-019 ↔ Contract]

## Idempotency, Concurrency, and Replay

- [ ] CHK039 Is the idempotency posture of `POST /auth/logout` (always 204, even with no/invalid cookie) specified at the contract layer? [Completeness, Spec §FR-006 ↔ Contract]
- [ ] CHK040 Is the FR-016 "re-login replaces session" behavior surfaced in the contract description (a successful login with a pre-existing valid cookie deletes the old session row)? [Clarity, Spec §FR-016 ↔ Contract /auth/login description]
- [ ] CHK041 Is the behavior of two concurrent logout requests on the same session specified (both return 204; only the first deletes a row)? [Coverage, Spec §Edge Cases — Concurrent logout]
- [ ] CHK042 Is the behavior of a login submitted with an *invalid* but present cookie specified (failed login does NOT delete the existing-but-stale cookie's row)? [Completeness, Spec §FR-016 ↔ §Edge Cases]
- [ ] CHK043 Are POST replay-safety requirements specified, or is the absence of an Idempotency-Key contract acknowledged as out-of-scope for Phase 2? [Gap]

## Versioning, Drift, and OpenAPI Discipline

- [ ] CHK044 Is the OpenAPI source-of-truth declared (FastAPI runtime spec) with the contracts/auth.openapi.yaml fragment's role explicitly stated as a pre-implementation contract document, not the runtime spec? [Clarity, Contract info.description]
- [ ] CHK045 Is the rule that `frontend/src/api/v1.d.ts` must be regenerated and committed when the API surface changes specified, with a CI gate referenced? [Completeness, Constitution §II ↔ Plan §4.1]
- [ ] CHK046 Is the API versioning posture for Phase 2 specified (no version prefix in v1, additive-only changes thereafter)? [Gap, Constitution §II]
- [ ] CHK047 Is the requirement that no breaking changes ship to existing consumers in this phase explicit (Phase 2 only adds endpoints, does not modify `/healthz`)? [Coverage, Spec §FR-017/§FR-018]
- [ ] CHK048 Is the `operationId` convention (used by openapi-typescript to name generated client methods) consistent across the three new endpoints? [Consistency, Contract operationIds]
- [ ] CHK049 Is the `tags` taxonomy specified or is the absence acknowledged? [Gap, Contract]

## Non-Functional API Requirements

- [ ] CHK050 Is the SC-001 "login under 2 s end-to-end" requirement decomposed into a server-side budget (e.g. p95 server processing under N ms) so reviewers can challenge whether the API contract is achievable? [Measurability, Spec §SC-001]
- [ ] CHK051 Is the SC-002 timing-uniformity requirement specified at the contract level (the API guarantees observably equal timing across the three failure modes), not only at the implementation level? [Coverage, Spec §SC-002]
- [ ] CHK052 Are throughput requirements per endpoint specified, or is the absence of a throughput contract acknowledged given the single-tenant deployment model? [Gap]
- [ ] CHK053 Is the contract's behavior under partial database outage specified (5xx vs degraded read), or explicitly deferred? [Gap]
- [ ] CHK054 Is character-encoding fixed as UTF-8 across all string fields? [Gap, Contract]

## Consistency Across Artifacts

- [ ] CHK055 Are endpoint paths consistent between `spec.md` (mentions `/api/me`), `plan.md` (`/me`), and `contracts/auth.openapi.yaml` (`/me`), with the proxy-stripping rule documented to reconcile them? [Consistency, Spec §FR-018 ↔ Plan §D6 ↔ Contract]
- [ ] CHK056 Are the `Me` response fields consistent between `spec.md` ("`id, name, role`"), `plan.md`, and `contracts/auth.openapi.yaml`? [Consistency]
- [ ] CHK057 Is the failure-mode enum consistent between the FR-019 logging fields (`success | wrong_password | unknown_email | soft_deleted`) and the contract's 401 description? [Consistency, Spec §FR-019 ↔ Contract /auth/login 401]
- [ ] CHK058 Are the cookie name and security attributes consistent between `plan.md §D3`, `contracts/auth.openapi.yaml securitySchemes.mmSession`, and the security checklist? [Consistency]

## Ambiguities & Conflicts

- [ ] CHK059 Is the contract's "/me returns 200" success-response behavior consistent with FR-008's "frontend redirects on 401 and clears cached query state" (i.e. the contract documents the 401 trigger, not just the 200 happy path)? [Consistency, Spec §FR-008 ↔ Contract /me]
- [ ] CHK060 Is there a conflict between the Contract's 204 No Content for login and any frontend assumption of a JSON body on success? [Conflict, Plan §5.2 ↔ Contract /auth/login 204]
- [ ] CHK061 Is the requirement for OpenAPI 3.1 (vs 3.0) specified, given some tooling differences in nullable handling? [Clarity, Contract openapi version]
- [ ] CHK062 Is the contract reviewable in isolation — does it contain enough description text that a reviewer who has not read `spec.md` can challenge it on its own? [Self-contained, Contract]

## Notes

- Check items off as completed: `[x]`. Items deferred to a PR-time artifact (e.g. CI OpenAPI-drift report) may be `[~]` with a one-line link.
- Cookie-attribute, signing, CSRF, and HTTPS items intentionally live in [security.md](./security.md). If a reviewer wants the contract self-contained, raise it against CHK062.
- This checklist tests **the API contract requirements**, not whether the implementation honors them. Implementation honoring belongs in the integration tests called out in `plan.md §2.5`.
