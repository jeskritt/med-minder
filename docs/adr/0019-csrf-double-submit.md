# ADR-0019 — CSRF defense-in-depth: double-submit cookie token

## Status

**Accepted** (Phase 10 — Hardening). Supersedes the "explicit CSRF tokens are
deferred to the hardening phase" note in ADR-0017.

## Context

Until Phase 10 the app's only CSRF defense was the `SameSite=Lax` session cookie
plus the single-origin deployment (ADR-0017). That is effective — a
cross-site POST does not carry the `mm_session` cookie — but it is a single
control, and the Phase 10 review (G2) called for defense-in-depth: a second,
independent mechanism that also protects browsers with weak/again-changing
SameSite behavior.

Options considered:

- **Synchronizer token** — requires server-side per-session token storage; adds
  DB writes and state. Rejected (no shared store; ADR-0017).
- **Origin/Referer allowlist only** — `Referer` can be stripped and the dev
  Vite-proxy setup muddies the Origin; weak as a sole gate.
- **Double-submit cookie token** — no server state: issue a random token in a
  non-HttpOnly cookie, require it echoed in a header on unsafe requests, compare
  the two. Chosen.

A hard constraint: the **service worker** (`frontend/src/sw.ts`) makes
same-origin POSTs to `/api/v1/reminders/{id}/snooze` and `/take` from a
`notificationclick` and **cannot read `document.cookie`**.

## Decision

A global `CsrfMiddleware` (`api/csrf.py`) enforces, on unsafe methods only
(everything except GET/HEAD/OPTIONS/TRACE): `X-CSRF-Token` header **==**
`mm_csrf` cookie, compared with `secrets.compare_digest`. Mismatch/absence →
**403**.

- The **non-HttpOnly `mm_csrf` cookie** is issued alongside the session: freshly
  on login, and self-healed on any authenticated request
  (`get_current_user`). The SPA echoes it via a single `openapi-fetch`
  request middleware (`lib/api.ts`).
- **Exemptions**: `/auth/login` (pre-auth — no session to protect) and
  `/auth/logout` (idempotent, clears only the caller's own cookie); `/healthz`,
  `/docs`, `/openapi.json`, `/redoc`; the static SPA (GET/HEAD only).
- **Service-worker path**: the SW sends the header when the **Cookie Store API**
  (`self.cookieStore`) is available. As a fail-safe for browsers without it, the
  two reminder-action endpoints are **CSRF-exempt** — they are session-authed,
  user-scoped (404 if not yours), self-only mutations, and `SameSite=Lax`
  already blocks the cross-site POST CSRF would require, so the residual risk is
  negligible.

## Consequences

- **Positive**: a second, stateless CSRF control layered on SameSite; one
  enforcement point (middleware) rather than per-route opt-in; one attach point
  in the SPA client.
- **Negative / accepted**: the two reminder-action endpoints rely on
  SameSite-Lax alone where Cookie Store is unavailable (documented residual
  risk). The token is not session-bound (a plain random value), which is
  sufficient for double-submit and avoids server state.
- **Testing**: protection is disabled in the shared API test client (like
  `reminders_enabled`) so the broad mutation suite needn't plumb the header; a
  dedicated `test_csrf.py` builds its own client with protection enabled.
