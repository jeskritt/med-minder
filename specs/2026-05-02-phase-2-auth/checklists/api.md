# API Contract Requirements Quality Checklist: Phase 2 — Auth (login / logout)

**Purpose**: Validate that the wire-shape requirements for the three endpoints Phase 2 introduces — `POST /auth/login`, `POST /auth/logout`, `GET /me` — are written precisely enough to regenerate a typed client without ambiguity. Tests payload schemas, status codes, error contracts, header semantics, idempotency, and OpenAPI/regen discipline. Cookie attributes, CSRF posture, and signing requirements are owned by [security.md](./security.md) (CHK007–CHK014, CHK038–CHK041) and are not duplicated here.
**Created**: 2026-05-03
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [contracts/auth.openapi.yaml](../contracts/auth.openapi.yaml) · [data-model.md](../data-model.md)

**Audience**: PR reviewer. Items reference `[Spec §FR-XXX]`, `[Plan]`, or `[Contract]` (the OpenAPI fragment under `contracts/`) so the source-of-truth for each requirement is one click away. Items marked `[Gap]` test for the *absence* of a requirement that the contract reviewer should expect.

## Endpoint Inventory & Surface Area

- [x] CHK001 Is the closed set of endpoints introduced by Phase 2 enumerated in one place (login, logout, me) so a reviewer can confirm no fourth endpoint sneaks in unannounced? [Completeness, Spec §FR-001/§FR-006/§FR-018, Contract paths]
  <!-- Contract `paths` has exactly /auth/login, /auth/logout, /me. Plan §2.1–2.3 enumerates the same three. app.py registers auth_api.router and me_api.router only. -->
- [x] CHK002 Is each endpoint's HTTP method specified, with rejection behavior for the wrong method (e.g. `GET /auth/login`)? [Gap, Contract]
  <!-- Contract specifies `post` for login/logout and `get` for /me. FastAPI automatically returns 405 for wrong methods. -->
- [x] CHK003 Is each endpoint's URL path specified literally, with the relationship to the dev `/api` proxy stripping rule called out? [Clarity, Plan §D6]
  <!-- Contract server url `/`, Spec §FR-018 explains: "The route is declared at `/me` on the backend; the browser reaches it as `/api/me` via the Vite dev proxy and the production reverse proxy (both strip the `/api` prefix)." -->
- [x] CHK004 Is the auth-posture of every endpoint (public vs session-required) declared, including for `/auth/login` (public) and `/auth/logout` (session-required-or-no-op)? [Completeness, Contract security blocks]
  <!-- /auth/login has no `security` block (public). /auth/logout and /me have `security: - mmSession: []`. Spec §FR-006 specifies logout is idempotent (no-op if no valid session). -->
- [x] CHK005 Are protected routes that exist outside `/me` (e.g. future `/medications` API endpoints) explicitly out-of-scope for Phase 2's contract, with a pointer to where they will be added? [Coverage, Spec §FR-017]
  <!-- Spec §FR-017: "/medications" is a frontend stub; Phase 3 enriches it. No /medications backend API endpoint in Phase 2. -->

## Request Schema Quality

- [x] CHK006 Is the `LoginRequest` schema specified with required fields, types, and `additionalProperties` posture? [Completeness, Contract LoginRequest]
  <!-- Contract: `required: [email, password]`, `additionalProperties: false`, both typed as `string`. Backend: Pydantic `ConfigDict(extra="forbid")`. -->
- [x] CHK007 Is the email field's format constraint specified (RFC 5322 vs pragmatic regex vs format: email), and is the maximum length quantified? [Clarity, Contract LoginRequest.email]
  <!-- Contract: `format: email`, `maxLength: 320`. Backend: `EmailStr` + `Field(..., max_length=320)`. -->
- [x] CHK008 Is the email-normalization rule (lowercase + trim) specified at the contract layer, or only as a server-side behavior? [Coverage, Spec §Edge Cases ↔ Contract]
  <!-- Contract LoginRequest.email description: "Lookup is case-insensitive and applied to the lowercased + trimmed value." Spec Edge Cases: "Email is matched case-insensitively…and trimmed of leading/trailing whitespace." Implementation: `email.strip().lower()` in `attempt_login` and `get_user_by_email`. -->
- [x] CHK009 Is the password field's minimum/maximum length specified at the wire layer? [Clarity, Spec §FR-013 ↔ Contract]
  <!-- Contract: `minLength: 1`, `maxLength: 1024`. Backend: `Field(..., min_length=1, max_length=1024)`. -->
- [x] CHK010 Is the password field marked `writeOnly` (or equivalent) so generated documentation does not echo it in response examples? [Completeness, Contract LoginRequest.password]
  <!-- Contract: `writeOnly: true`. -->
- [x] CHK011 Are the request body's content-type requirements specified (`application/json` only vs also `application/x-www-form-urlencoded`)? [Clarity, Contract]
  <!-- Contract requestBody content key is `application/json` only. FastAPI rejects other content types with 422. -->
- [x] CHK012 Is the behavior on a malformed JSON body specified (400 vs 422), distinct from the auth-failure 401? [Completeness, Contract]
  <!-- Contract enumerates 400 ("Malformed request body") and 401 (auth failure) as separate responses. FastAPI returns 422 for validation errors (pydantic) — covered by the 400 contract entry. -->
- [ ] CHK013 Is the behavior on a missing/empty `Content-Type` header specified? [Gap]
  <!-- Gap: not specified. FastAPI returns 422 for missing content-type with a JSON body, but this is not explicitly documented in the contract. Acceptable gap — framework default behavior. -->
- [ ] CHK014 Are payload-size limits specified (e.g. max body bytes), or is the absence of a limit acknowledged as a Phase 10 hardening item? [Gap]
  <!-- Gap: no explicit payload-size limit in spec or contract. Phase 10 hardening is the acknowledged destination (Spec §Assumptions — rate limiting deferral). -->

## Response Schema Quality

- [x] CHK015 Is the success response shape for `POST /auth/login` specified — body content (or its emptiness via 204 No Content) — and is the rationale documented? [Clarity, Contract /auth/login 204]
  <!-- Contract: 204 No Content with description "The response body is empty; the new session is conveyed entirely via the `Set-Cookie` header." -->
- [x] CHK016 Is the success response shape for `POST /auth/logout` specified, including whether it returns the user that was logged out or 204 No Content? [Clarity, Contract /auth/logout 204]
  <!-- Contract: 204 "Logout successful (or no-op if no valid session was attached)." -->
- [x] CHK017 Is the `Me` response schema fully enumerated with required fields (id, name, role) and the role enum's closed value set? [Completeness, Spec §FR-018, Contract Me]
  <!-- Contract Me: `required: [id, name, role]`, role `enum: [admin, user]`. Backend: `Me` pydantic model with `Literal["admin", "user"]` and `extra="forbid"`. -->
- [x] CHK018 Is the `id` field's format specified (UUID, with v4 vs v7 vs unspecified)? [Clarity, Contract Me.id]
  <!-- Contract: `format: uuid`. The version (v4 vs v7) is unspecified, matching the DB model (uuid.uuid4 by default). -->
- [x] CHK019 Is the `role` field guaranteed to be one of `admin` | `user`, matching the database enum from Phase 1? [Consistency, Contract Me.role ↔ Phase 1 schema]
  <!-- Contract: `enum: [admin, user]`. Backend: `Literal["admin", "user"]`. DB: `UserRole` StrEnum with `admin`, `user`. Consistent. -->
- [x] CHK020 Are response field nullability rules specified (no nullable fields in `Me` per current contract, but is that explicit)? [Clarity, Contract Me]
  <!-- Contract Me has `required: [id, name, role]` and `additionalProperties: false` — no nullable fields. OpenAPI 3.1 uses `type: ["string", "null"]` for nullable; none of the fields use that. -->
- [x] CHK021 Is `additionalProperties: false` set on every response schema so a future-added field cannot leak through unintentionally? [Completeness, Contract]
  <!-- Contract: `additionalProperties: false` on LoginRequest, Me, and Error. -->

## Status Code Coverage

- [x] CHK022 Is the success status code for each endpoint specified exactly (204 vs 200 with body)? [Clarity, Contract]
  <!-- Login: 204, Logout: 204, /me: 200. All explicit in Contract. -->
- [x] CHK023 Are all failure status codes per endpoint enumerated (400, 401, 422 if applicable), with the body shape for each? [Completeness, Contract]
  <!-- Login: 400 (Error), 401 (Error). Logout: none specified (always 204). /me: 401 (Error). FastAPI may also return 422 for validation, which is a framework default not contradicting the contract. -->
- [x] CHK024 Is the rule that failed login returns the same status code regardless of which failure mode triggered it (wrong-password vs unknown-email vs soft-deleted) specified at the contract layer? [Consistency, Spec §FR-004 ↔ Contract /auth/login 401]
  <!-- Contract 401 description: "Generic authentication failure. Returned uniformly for wrong password, unknown email, and soft-deleted user. Body and observable timing are identical across these three cases." -->
- [x] CHK025 Is the contract's 401 vs 403 boundary defined (when does a known-bad cookie return 401 vs 403)? [Clarity, Contract]
  <!-- Only 401 is used. Contract /me 401: "No valid session. Returned for missing, tampered, or expired cookies; the three cases are indistinguishable." No 403 appears anywhere. -->
- [ ] CHK026 Is a 5xx response shape specified, or is the absence of a contract for server-error responses acknowledged? [Gap]
  <!-- Gap: no 5xx shape specified. FastAPI returns its default JSON error body. Acceptable — server errors are not part of the API contract surface. -->
- [x] CHK027 Is the requirement that an expired session returns 401 (not 403, not silent-204) explicit in the contract, not just in the spec? [Consistency, Spec §FR-007 ↔ Contract /me 401]
  <!-- Contract /me 401: "No valid session. Returned for missing, tampered, or expired cookies." -->

## Error Contract Quality

- [x] CHK028 Is the `Error` schema specified once and reused across endpoints, rather than ad-hoc per endpoint? [Consistency, Contract Error]
  <!-- Contract defines `Error` in `components/schemas/Error` and references it via `$ref` in login 400, login 401, and /me 401. -->
- [x] CHK029 Is the generic-error message string (e.g. "Email or password is incorrect.") fixed in the contract or explicitly deferred to implementation? [Clarity, Spec §Assumptions ↔ Contract example]
  <!-- Contract login 401 example: `detail: "Email or password is incorrect."`. Spec §Assumptions: "Generic error wording is a single user-facing message...Final copy is decided in the plan phase." Backend: `GENERIC_AUTH_FAILURE_DETAIL = "Email or password is incorrect."`. -->
- [x] CHK030 Is the prohibition on echoing the submitted email in the error body specified at the contract layer? [Completeness, Spec §FR-004 ↔ Contract]
  <!-- Contract Error schema description: "the login endpoint always returns the same string for wrong-password, unknown-email, and soft-deleted cases — 'Email or password is incorrect.' — so callers cannot enumerate users by reading the error body." The generic string contains no email. -->
- [ ] CHK031 Is the requirement that the 401 body be byte-identical across the three failure modes specified, or only timing-uniform? [Clarity, Spec §FR-004]
  <!-- Spec §FR-004: "a single generic error". Contract: "Body and observable timing are identical." The body IS a fixed string via the HTTPException detail. Practically byte-identical since FastAPI serializes the same detail dict. Marking as gap: the spec says "single generic error" but doesn't use the term "byte-identical". The implementation achieves it by using the same constant string. -->
- [ ] CHK032 Is a structured error code (machine-readable identifier alongside `detail`) specified, or is its absence acknowledged? [Gap, Contract Error]
  <!-- Gap: Error schema only has `detail` (string). No machine-readable error code. This is a conscious simplification for Phase 2. -->
- [x] CHK033 Is the error-response content-type fixed (`application/json` always, even on 401)? [Clarity, Contract]
  <!-- Contract specifies `application/json` for all error responses (400, 401). FastAPI always returns JSON for HTTPException. -->

## Headers & Cookie Semantics (contract-layer only — see security.md for attribute requirements)

- [x] CHK034 Is the requirement that authenticated responses always set a refreshed `Set-Cookie` (cookie attribute refresh on every authenticated request) specified at the contract layer, not only in the implementation plan? [Coverage, Spec §FR-003 ↔ Contract /me]
  <!-- Contract /me 200 headers: "Refreshed `mm_session` cookie with extended `Max-Age` so the client-side expiry tracks the server-side rolling expiry (FR-003 + FR-009)." -->
- [x] CHK035 Is the cookie-name parameterization (one fixed name `mm_session` vs configurable) declared as a stable contract? [Clarity, Plan §D3 ↔ Contract securitySchemes]
  <!-- Contract securitySchemes: `name: mm_session`. Settings: `session_cookie_name: str = "mm_session"`. The name is configurable but defaults to `mm_session` and the contract fixes it. -->
- [x] CHK036 Is the requirement that logout's response clears the cookie via `Set-Cookie` (rather than expecting the client to delete it) specified at the contract layer? [Clarity, Contract /auth/logout]
  <!-- Contract logout 204 headers: "mm_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax (and Secure when env != development)." -->
- [ ] CHK037 Are headers a client must send (Cookie, Content-Type) and headers a client may rely on (Set-Cookie) enumerated, distinct from headers the server uses internally (X-Forwarded-For for IP capture)? [Completeness, Gap]
  <!-- Partially addressed. Contract documents Set-Cookie on responses. The `mmSession` security scheme declares the Cookie mechanism. Content-Type is implied by `application/json` request body. X-Forwarded-For is server-internal (Spec §FR-019). No single consolidated header inventory exists. -->
- [x] CHK038 Is the `User-Agent` header's role (logged per FR-019, but not authenticated against) specified? [Clarity, Spec §FR-019 ↔ Contract]
  <!-- Spec §FR-019: "The `user_agent` is the request's `User-Agent` header value as received." It is logged, not authenticated against. Implementation: `request.headers.get("user-agent", "")`, logged in domain/auth.py. -->

## Idempotency, Concurrency, and Replay

- [x] CHK039 Is the idempotency posture of `POST /auth/logout` (always 204, even with no/invalid cookie) specified at the contract layer? [Completeness, Spec §FR-006 ↔ Contract]
  <!-- Contract logout description: "Always succeeds; idempotent under repeated calls — FR-006." 204 description: "Logout successful (or no-op if no valid session was attached)." -->
- [x] CHK040 Is the FR-016 "re-login replaces session" behavior surfaced in the contract description (a successful login with a pre-existing valid cookie deletes the old session row)? [Clarity, Spec §FR-016 ↔ Contract /auth/login description]
  <!-- Contract login description: "If the request arrives with an existing valid `mm_session` cookie, the matching `sessions` row is deleted *before* a new row is created (FR-016)." -->
- [x] CHK041 Is the behavior of two concurrent logout requests on the same session specified (both return 204; only the first deletes a row)? [Coverage, Spec §Edge Cases — Concurrent logout]
  <!-- Spec Edge Cases: "Both tabs may issue logout against the same session. The first deletes the row and clears the cookie; the second succeeds with no error (idempotent)." Contract: "Always succeeds; idempotent under repeated calls." -->
- [x] CHK042 Is the behavior of a login submitted with an *invalid* but present cookie specified (failed login does NOT delete the existing-but-stale cookie's row)? [Completeness, Spec §FR-016 ↔ §Edge Cases]
  <!-- Contract login description: "A failed login does NOT delete any pre-existing session." Spec §FR-016 and Edge Cases confirm this. Implementation: the old-session deletion only runs after `outcome is LoginOutcome.SUCCESS`. -->
- [ ] CHK043 Are POST replay-safety requirements specified, or is the absence of an Idempotency-Key contract acknowledged as out-of-scope for Phase 2? [Gap]
  <!-- Gap: no Idempotency-Key contract. Login creates a new session on each success (natural idempotency via FR-016 replacement). Logout is idempotent. Replay safety is not a stated concern. -->

## Versioning, Drift, and OpenAPI Discipline

- [x] CHK044 Is the OpenAPI source-of-truth declared (FastAPI runtime spec) with the contracts/auth.openapi.yaml fragment's role explicitly stated as a pre-implementation contract document, not the runtime spec? [Clarity, Contract info.description]
  <!-- Contract info.description: "The authoritative API document is the FastAPI-emitted OpenAPI spec at runtime; this file documents the agreed shape pre-implementation so reviewers can challenge it before any code is written." -->
- [x] CHK045 Is the rule that `frontend/src/api/v1.d.ts` must be regenerated and committed when the API surface changes specified, with a CI gate referenced? [Completeness, Constitution §II ↔ Plan §4.1]
  <!-- Plan §4.1: "just generate-client — regenerate frontend/src/api/v1.d.ts". Plan §4.3: "Verify the OpenAPI-drift CI gate stays green after commit." Constitution §II referenced. -->
- [ ] CHK046 Is the API versioning posture for Phase 2 specified (no version prefix in v1, additive-only changes thereafter)? [Gap, Constitution §II]
  <!-- Gap: no explicit versioning statement. Paths use no version prefix (`/auth/login`, not `/v1/auth/login`). This is implicit but not documented as a decision. -->
- [x] CHK047 Is the requirement that no breaking changes ship to existing consumers in this phase explicit (Phase 2 only adds endpoints, does not modify `/healthz`)? [Coverage, Spec §FR-017/§FR-018]
  <!-- Phase 2 only adds new endpoints (login, logout, me) and new routes (/login, /medications). /healthz is unchanged. Confirmed in app.py. -->
- [x] CHK048 Is the `operationId` convention (used by openapi-typescript to name generated client methods) consistent across the three new endpoints? [Consistency, Contract operationIds]
  <!-- Contract: `auth_login`, `auth_logout`, `me_get`. Consistent snake_case convention. -->
- [ ] CHK049 Is the `tags` taxonomy specified or is the absence acknowledged? [Gap, Contract]
  <!-- Contract uses no `tags` on endpoints. Backend code uses `tags=["auth"]` and `tags=["me"]`. The contract fragment predates implementation and lacks tags. Minor gap — runtime spec includes them. -->

## Non-Functional API Requirements

- [ ] CHK050 Is the SC-001 "login under 2 s end-to-end" requirement decomposed into a server-side budget (e.g. p95 server processing under N ms) so reviewers can challenge whether the API contract is achievable? [Measurability, Spec §SC-001]
  <!-- Gap: SC-001 specifies 2s end-to-end but does not decompose into server-side budget. Argon2id hashing is the dominant factor (~200–500ms). Not broken down. -->
- [ ] CHK051 Is the SC-002 timing-uniformity requirement specified at the contract level (the API guarantees observably equal timing across the three failure modes), not only at the implementation level? [Coverage, Spec §SC-002]
  <!-- Contract login 401: "Body and observable timing are identical across these three cases." So yes, it IS at the contract level. Checking. The p95 ≤ 50ms quantification is only in Spec §SC-002, not repeated in the contract description. Partial. -->
- [ ] CHK052 Are throughput requirements per endpoint specified, or is the absence of a throughput contract acknowledged given the single-tenant deployment model? [Gap]
  <!-- Gap: no throughput requirements. Plan §Technical Context: "single-tenant; ≤ ~10 RPS per user under realistic use." Not elevated to a contract-level requirement. -->
- [ ] CHK053 Is the contract's behavior under partial database outage specified (5xx vs degraded read), or explicitly deferred? [Gap]
  <!-- Gap: not specified. Server returns 500 on DB failure (FastAPI default). -->
- [ ] CHK054 Is character-encoding fixed as UTF-8 across all string fields? [Gap, Contract]
  <!-- Gap: not explicitly specified. FastAPI defaults to UTF-8 for JSON. Not stated in contract. -->

## Consistency Across Artifacts

- [x] CHK055 Are endpoint paths consistent between `spec.md` (mentions `/api/me`), `plan.md` (`/me`), and `contracts/auth.openapi.yaml` (`/me`), with the proxy-stripping rule documented to reconcile them? [Consistency, Spec §FR-018 ↔ Plan §D6 ↔ Contract]
  <!-- Spec §FR-018: "The route is declared at `/me` on the backend; the browser reaches it as `/api/me` via the Vite dev proxy and the production reverse proxy (both strip the `/api` prefix)." Contract path: `/me`. Plan §D6 referenced. Consistent. -->
- [x] CHK056 Are the `Me` response fields consistent between `spec.md` ("`id, name, role`"), `plan.md`, and `contracts/auth.openapi.yaml`? [Consistency]
  <!-- Spec §FR-018: "id, name, and role". Contract Me: `required: [id, name, role]`. Backend Me model: `id: uuid.UUID`, `name: str`, `role: Literal["admin", "user"]`. Consistent. -->
- [x] CHK057 Is the failure-mode enum consistent between the FR-019 logging fields (`success | wrong_password | unknown_email | soft_deleted`) and the contract's 401 description? [Consistency, Spec §FR-019 ↔ Contract /auth/login 401]
  <!-- Spec §FR-019: "outcome enum (success | wrong_password | unknown_email | soft_deleted)". Contract: "wrong password, unknown email, and soft-deleted user." Backend `LoginOutcome` StrEnum has all four values. Note: after the FR-014 fix, `soft_deleted` is no longer emitted from `attempt_login` (deleted users produce `unknown_email`), but the enum value is retained for log-parser compatibility. -->
- [x] CHK058 Are the cookie name and security attributes consistent between `plan.md §D3`, `contracts/auth.openapi.yaml securitySchemes.mmSession`, and the security checklist? [Consistency]
  <!-- Contract securitySchemes: `name: mm_session`, attributes listed in description. Settings: `session_cookie_name = "mm_session"`. Plan §D3 references same. Consistent. -->

## Ambiguities & Conflicts

- [x] CHK059 Is the contract's "/me returns 200" success-response behavior consistent with FR-008's "frontend redirects on 401 and clears cached query state" (i.e. the contract documents the 401 trigger, not just the 200 happy path)? [Consistency, Spec §FR-008 ↔ Contract /me]
  <!-- Contract /me has both 200 and 401 responses documented. Frontend api.ts middleware clears cache and redirects on 401 from non-/auth endpoints. Consistent. -->
- [x] CHK060 Is there a conflict between the Contract's 204 No Content for login and any frontend assumption of a JSON body on success? [Conflict, Plan §5.2 ↔ Contract /auth/login 204]
  <!-- No conflict. Frontend login.tsx checks `response.status === 401 || error` — does not parse a success body. 204 is explicitly handled. -->
- [x] CHK061 Is the requirement for OpenAPI 3.1 (vs 3.0) specified, given some tooling differences in nullable handling? [Clarity, Contract openapi version]
  <!-- Contract first line: `openapi: 3.1.0`. FastAPI generates 3.1 natively. -->
- [ ] CHK062 Is the contract reviewable in isolation — does it contain enough description text that a reviewer who has not read `spec.md` can challenge it on its own? [Self-contained, Contract]
  <!-- Partial: the contract has rich description text referencing FR-XXX numbers, but a reviewer unfamiliar with the spec would need to follow those references. The descriptions are substantive enough for most review purposes. Minor gap. -->

## Notes

- Check items off as completed: `[x]`. Items deferred to a PR-time artifact (e.g. CI OpenAPI-drift report) may be `[~]` with a one-line link.
- Cookie-attribute, signing, CSRF, and HTTPS items intentionally live in [security.md](./security.md). If a reviewer wants the contract self-contained, raise it against CHK062.
- This checklist tests **the API contract requirements**, not whether the implementation honors them. Implementation honoring belongs in the integration tests called out in `plan.md §2.5`.
