# Phase 2 — Research

Phase 0 of the spec-kit workflow: resolve every open technical-context choice the spec deferred to the plan phase. Each block follows the canonical `Decision / Rationale / Alternatives considered` shape so reviewers can challenge any single decision in isolation.

The spec (`spec.md`) and ADR-0001 (server-side sessions over JWTs) constrain the design space; this document closes the remaining choices inside that envelope.

---

## D1 — Cookie signing library

**Decision**: Add `itsdangerous>=2.2.0,<3.0` to backend runtime dependencies and use `URLSafeTimedSerializer` to sign the cookie value.

**Rationale**: The constitution requires signed cookies (FR-003) but the project has no signing library yet. `itsdangerous` is a small, single-purpose, widely deployed library (it's a transitive dependency of Flask and is maintained by the Pallets team). `URLSafeTimedSerializer` is the right primitive — it signs an opaque string payload (the session token) with a server-side secret, returning a URL-safe value suitable for cookie use, and it ships with timestamp embedding which gives us a defense-in-depth check beyond the database-side `expires_at`. Pin with an upper bound per Constitution Principle V.

**Alternatives considered**:
- *Stdlib `hmac` + `hashlib`*: ~30 lines of in-house signing. Rejected — re-implements a well-known primitive with no benefit, and we would still need to test edge cases (e.g. constant-time comparison) the library already covers.
- *Starlette's `SessionMiddleware`*: stores the entire session payload inside the cookie (signed). Rejected — orthogonal to ADR-0001, which mandates server-side sessions; the middleware is for cookie-as-storage workflows.
- *PyJWT*: Rejected by ADR-0001 — no JWTs in v1.

---

## D2 — Session token format and database hash

**Decision**: Generate session tokens with `secrets.token_urlsafe(32)` (256 bits of entropy). Store `hashlib.sha256(token.encode()).hexdigest()` in the existing `sessions.token_hash` column. The plaintext token is never persisted; it is placed only inside the signed cookie.

**Rationale**: ADR-0001 D9b commits to SHA-256 over high-entropy random tokens (no KDF). `secrets.token_urlsafe(32)` is the stdlib idiom for generating cryptographically strong URL-safe tokens. SHA-256 is fast, deterministic for indexed lookup, and adequate when the input is already random — Argon2id would tax every authenticated request without adding security. FR-002 requires ≥ 256 bits of entropy and forbids persisting plaintext or logging tokens.

**Alternatives considered**:
- *Argon2id over the token*: Rejected — wrong tool. Argon2id resists offline cracking of low-entropy inputs (passwords). High-entropy tokens are not crackable; a slow KDF only adds latency.
- *UUIDv4*: Lower entropy (~122 bits). Rejected — does not meet FR-002.

---

## D3 — Cookie attributes

**Decision**: Cookie name `mm_session`. `HttpOnly` always. `SameSite=Lax` always. `Secure` set when `Settings.env != "development"`. `Path=/`. `Max-Age=2592000` (30 days), refreshed on every authenticated response so the cookie's client-side expiry tracks the server-authoritative `sessions.expires_at`.

**Rationale**: FR-003 fixes the security attributes. `Lax` is the strongest practical SameSite value while keeping top-level navigations from a phishing email still redirect-friendly; explicit CSRF tokens are deferred to Phase 10. `Secure` keyed on `env` matches the existing settings pattern and avoids a separate boolean flag. `Max-Age` is preferred over `Expires` because it is server-clock-relative, sidestepping client clock skew. The "refresh on each authenticated response" behavior keeps the cookie aligned with FR-009's rolling expiry — without it, the server-side row could be valid while the cookie has already expired in the browser.

**Alternatives considered**:
- *Session cookie (no Max-Age)*: Rejected by clarification — the user explicitly asked for persistence across browser restart.
- *`SameSite=Strict`*: Rejected — breaks the common case of clicking a link in an email and arriving authenticated.
- *Separate `SESSION_COOKIE_SECURE` env var*: Rejected — derivable from `env`; an extra knob with no upside increases configuration error rate.

---

## D4 — Rolling expiry implementation

**Decision**: Mutate `sessions.expires_at` in place on every authenticated request that successfully validates. Do not introduce a `last_seen_at` column or any other schema change.

**Rationale**: FR-009 fixes the externally observable behavior; the spec assumption section explicitly anticipates this implementation and notes "no Alembic migration is anticipated". The `sessions.expires_at` column already exists and is the single value the auth dependency reads; mutating it in place keeps the validity check ("`expires_at > now()`") atomic with the extension. The trade-off — losing the original creation-window expiry as a separate signal — is unimportant for Phase 2; if a future phase needs both creation-time and last-activity, it can add `last_seen_at` then.

**Alternatives considered**:
- *Add a `last_seen_at` column*: Rejected — costs a migration in this phase for no observable behavior gain.
- *Sliding-window TTL stored client-side*: Rejected — the server is the source of truth (FR-009 says expiry is database-authoritative).

---

## D5 — Timing-safe failure path

**Decision**: When `get_user_by_email(include_deleted=False)` returns `None` — i.e. unknown email or soft-deleted user — call `verify_password(DUMMY_HASH, password)` against a module-level dummy Argon2id hash and discard the result. Always run exactly one Argon2id verification per login attempt regardless of which failure mode is hit.

**Rationale**: FR-004 + SC-002 require that wrong-password, unknown-email, and soft-deleted-user paths be observationally indistinguishable in body, status, and timing (p95 delta ≤ 50 ms over 100 trials). Argon2id verification dominates login latency; a path that skips it would be observably faster and would re-introduce the user-enumeration oracle the spec explicitly forbids. Running one verification against a fixed module-level dummy hash keeps timing flat without a fragile `time.sleep`. This is the well-known industry idiom (Django's `authenticate`, OWASP guidance).

**Alternatives considered**:
- *`time.sleep(constant)`*: Rejected — fragile; the constant would need to track Argon2 parameter changes; sleep is observable through CPU vs. wall-clock divergence.
- *Hash a freshly generated random password*: Rejected — `_HASHER.hash` is a hash, not a verify; running it would have different timing characteristics than `verify`. We need to mirror the success path exactly.
- *Single artificial Argon2 verify only on the no-user branch*: Equivalent in effect to D5 and is what we adopt; the formulation above clarifies the dummy-hash constant.

---

## D6 — URL layout and `/api` prefix

**Decision**: Backend exposes routes at root paths: `/auth/login`, `/auth/logout`, `/me`. The Vite dev proxy already strips `/api` from frontend-side requests (`vite.config.ts:15–24`), so `/api/auth/login` from the browser maps to `/auth/login` on the backend. Production deployment exposes the backend at the same root paths and the frontend bundle prepends `/api` via the openapi-fetch base URL.

**Rationale**: Consistent with the Phase 0 wiring of `/healthz`. Keeps the OpenAPI document clean (no `/api/api/...` confusion), keeps backend route declarations short, and keeps the proxy/baseUrl as the single seam where the prefix is added or stripped.

**Alternatives considered**:
- *Backend routes under `/api/...`*: Rejected — introduces a coupling between frontend deployment shape and backend routes that the proxy was designed to absorb; would force changing every route prefix if the proxy ever changes.

---

## D7 — DB session FastAPI dependency

**Decision**: Add `backend/src/medminder/api/deps.py::get_session()`, an async-generator dependency that yields an `AsyncSession` from a per-app `async_sessionmaker` stored on `app.state`. The session factory is initialized in `create_app()` and disposed by FastAPI's lifespan.

**Rationale**: Phase 2 introduces the project's first HTTP-handler use of the database. There is no existing dependency to reuse — `medminder.db.session_scope` is a context manager intended for CLI-style code. A FastAPI-native dependency keeps request-scoped lifecycle (commit-on-success, rollback-on-exception) idiomatic and avoids leaking SQLAlchemy plumbing into route handlers. Storing the factory on `app.state` keeps creation off the request hot-path.

**Alternatives considered**:
- *Create a session per request inline in each route*: Rejected — duplicates lifecycle code in every handler, fights FastAPI's dependency model.
- *Use `session_scope` directly via `Depends(session_scope)`*: Awkward — `session_scope` is an async-context-manager; FastAPI's `Depends` wants a generator. Wrapping is what `get_session` does.

---

## D8 — Auth dependency

**Decision**: `backend/src/medminder/api/deps.py::get_current_user(request, response, session=Depends(get_session)) -> User`. It (a) reads `request.cookies[settings.session_cookie_name]`, (b) verifies the signature with `URLSafeTimedSerializer.loads`, (c) computes `hash_token(plaintext)`, (d) calls `domain.sessions.authenticate_token`, which checks expiry and extends `expires_at` in place, (e) on the outgoing response sets a refreshed `Set-Cookie` Max-Age, (f) returns the resolved `User`. Any failure raises `HTTPException(status_code=401)`. Missing-cookie and tampered-cookie cases are indistinguishable to the client.

**Rationale**: A single chokepoint serves FR-007 (401 on missing/tampered/expired), FR-009 (rolling extension), and FR-008 (the frontend reads "401" → "redirect"). Keeping the cookie-refresh inside the same dependency that read it keeps the read/extend/write triple atomic from the route handler's point of view — handlers depend on `get_current_user` and never touch cookies directly.

**Alternatives considered**:
- *Middleware*: Rejected — would have to apply globally and then opt-out per public route, which is the wrong default for a single-tenant app where almost every route is protected; FastAPI's dependency model already cleanly expresses "this route requires a user."
- *Two dependencies (auth + cookie-refresh)*: Rejected — splits an atomic operation, invites a future bug where one is registered without the other.

---

## D9 — Re-login while already authenticated (FR-016)

**Decision**: The login handler always deletes any pre-existing `sessions` row keyed by the cookie present on the inbound request (if any) before creating a new row. This happens before password verification, so a failed login does not delete the existing session. Successful login then creates a fresh row and overwrites the cookie.

**Rationale**: FR-016 requires that the new credentials determine the resulting identity — not the old cookie. Deleting the old row only on success guarantees that a wrong-password attempt does not log the user out. Idempotency under double-click is preserved because a second login submits the same body and the second-arriving call simply replaces the row again.

**Alternatives considered**:
- *Delete the old row before verification*: Rejected — a typo would log the user out, which is bad UX and a constitution-Principle-I problem (login is not supposed to be a destructive action on failure).
- *Reject login when a valid cookie is present*: Rejected — conflicts with FR-016 explicitly.

---

## D10 — CLI revocation hooks (FR-010, FR-011)

**Decision**: `medminder/cli/users.py::delete` and `medminder/cli/users.py::update` both invoke `domain.sessions.revoke_all_user_sessions(user_id)` inside the same `run_with_session` transaction. The `update` command only invokes it when `--password-stdin` was supplied (i.e. the password actually changed); name/role/email-only updates do not revoke sessions.

**Rationale**: Atomicity matters — if the soft-delete or password update commits but the revocation fails (or vice versa), an attacker holding an old cookie continues to have access. Sharing the transaction makes both operations succeed-or-fail together. The `revoke_all_user_sessions` helper is the same function the future "log out everywhere" UI will call (Principle III: no logic duplicated between transports).

**Alternatives considered**:
- *Database CASCADE / trigger on user updates*: Rejected — the existing `sessions.user_id` FK already cascades on user delete, but soft-delete (`UPDATE users SET deleted_at = now()`) is not a delete and would not fire a cascade. Triggers would couple business logic to schema in a way Phase 1 deliberately avoided.
- *Revoke unconditionally on every `user update`*: Rejected — surprising for the admin who only changed a name and would log every browser the user has out.

---

## D11 — Login-attempt logging (FR-019)

**Decision**: A single `logging.INFO` line per login attempt, emitted from `domain/auth.py`, carrying structured fields: `outcome` (one of `success`, `wrong_password`, `unknown_email`, `soft_deleted`), `user_id` (UUID or `None`), `source_ip`, `user_agent`. The email address, password material, and any session-token material (plaintext or hashed) are explicitly never included.

**Rationale**: FR-019 fixes the shape; Constitution Principle I forbids PII in logs. Using stdlib `logging` (not `print` or a third-party tracer) keeps the code consistent with FastAPI/uvicorn defaults and lets ops attach their preferred handler/formatter. Putting the emission point in `domain/auth.py` keeps the HTTP layer thin and lets unit tests use `caplog` without spinning up a server.

**Alternatives considered**:
- *Log inside the route handler*: Rejected — duplicates logic across success and failure branches, makes unit testing require an HTTP client.
- *Use `loguru` or another structured logger*: Rejected — out-of-scope dependency churn for this phase; existing `logging` is sufficient.

---

## D12 — Frontend route guard

**Decision**: Protected routes use TanStack Router's `beforeLoad` hook to issue a `GET /me` request via the openapi-fetch client. On 401, throw `redirect({ to: "/login" })`. The 401 path is also wired through a global openapi-fetch middleware that, on any 401 from a non-`/auth` endpoint, calls `queryClient.clear()` and `router.navigate({ to: "/login" })` — this catches expirations that happen mid-session.

**Rationale**: TanStack Router's idiomatic pattern for auth gating is `beforeLoad`; doing it there avoids flicker (the protected component never mounts when the user is unauthenticated). Combining it with a global 401 middleware covers two distinct failure modes: navigation (caught by `beforeLoad`) and in-flight queries (caught by the middleware). FR-008 is satisfied by the union.

**Alternatives considered**:
- *A single root-level auth check*: Rejected — would either over-protect public routes (`/login`) or require an explicit allow-list, both of which are easier to get wrong than per-route `beforeLoad`.
- *React-Query-only retry interceptor*: Rejected — would not catch direct `fetch`/openapi-fetch calls outside React Query.
