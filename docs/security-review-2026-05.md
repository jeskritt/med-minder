# MedMinder — Comprehensive Security Review (Phase 10)

_Date: 2026-05-31 · Scope: full application as of this review · Author: maintainer_

This is the **final, comprehensive security review** required by the Phase 10
exit criteria (`specs/roadmap.md`). It builds on the per-phase reviews already
folded into each PR and covers the six areas the roadmap calls out: **session
handling, CSRF, push-key handling, input validation, dependency audit, and a
sweep of audit logging.**

It is both an assessment and a record of remediation: the gaps it identified
(G1–G7) were fixed in the same change set, and each non-trivial decision has its
own ADR (0018–0020).

## Methodology

A read of every security-relevant surface: `api/` routers and dependencies,
`domain/` logic, `settings.py`, `db/models/`, the Alembic migrations, the
frontend `lib/api.ts` + service worker, CI workflow, and deployment docs. Claims
were verified against code, not assumed from comments.

## Summary

MedMinder was already **strong** on most axes. The review confirmed the controls
below and closed a defined set of gaps.

### Verified-good (unchanged)

| Area | Finding |
|------|---------|
| Session tokens | `secrets.token_urlsafe(32)`; **SHA-256** hashed in `sessions` with a unique index (no replay); plaintext only in the signed cookie. |
| Session cookie | `itsdangerous`-signed; `HttpOnly` + `SameSite=Lax` + env-gated `Secure`; rolling 30-day expiry. |
| Session lifecycle | Login revokes the prior session **only on success**; logout is idempotent and best-effort; password change revokes **all** sessions and re-issues the current device's cookie. |
| AuthZ | `get_current_user` → 401, `require_admin` → 403; self-action and last-admin guards (the latter with a `FOR UPDATE` lock). |
| Secrets | `SESSION_SECRET` and the VAPID private key are env-only; a `model_validator` refuses to boot outside dev with the fallback secret; the VAPID private key is never logged or returned. |
| Input validation | Pydantic `extra="forbid"` + field constraints throughout; UUID path params validated by FastAPI; timezone validated against `zoneinfo`; **no raw/concatenated SQL** (the two `text()` uses are static partial-index predicates). |
| Errors / debug | `/docs` gated to dev, ReDoc off; structured 409 handlers; generic 401/403/404 with no stack traces or enumeration. |
| Audit log | `admin_audit_log` is append-only, successes-only, field-names-only (never secrets), atomic with the action, gated by `require_admin`. |

### Gaps found and remediated

| # | Gap | Severity | Resolution |
|---|-----|----------|------------|
| G1 | No login rate-limiting / brute-force protection | Medium | In-process dual-keyed sliding window → 429 (ADR-0018) |
| G2 | CSRF defense was SameSite + same-origin only | Medium | Added double-submit `mm_csrf` token middleware (ADR-0019) |
| G3 | Push `p256dh`/`auth` stored plaintext at rest | Medium | Fernet encryption with env-only key (ADR-0020) |
| G4 | No dependency audit in CI | Medium | `pip-audit` + `pnpm audit` job + Dependabot |
| G5 | CORS `allow_methods=["*"]` / `allow_headers=["*"]` | Low | Restricted to the methods/headers actually used |
| G6 | No security-headers middleware | Low | `SecurityHeadersMiddleware` (nosniff, frame-deny, Referrer-Policy, CSP, HSTS) |
| G7 | CLI admin actions bypassed the audit log | Medium | CLI now writes audit rows (`actor_id` nullable, `via: cli`) |

## Findings by area

### 1. Session handling — verified good
See the table above. No changes. The `Secure` flag derives from `ENV != development`;
deployments must ensure non-dev environments are actually HTTPS (they are, behind
Render's TLS).

### 2. CSRF — remediated (G2, G5, G6)
SameSite=Lax + single-origin (ADR-0017) was the sole control. Added a stateless
**double-submit** token (ADR-0019): a non-HttpOnly `mm_csrf` cookie issued with
the session and required, echoed in `X-CSRF-Token`, on every unsafe request via a
global middleware. The service worker — which cannot read `document.cookie` —
sends the token via the Cookie Store API where available, with the two
reminder-action endpoints CSRF-exempt as a documented SameSite-backed fail-safe.
CORS was tightened (G5) and security headers added (G6), including a conservative
CSP for the production single-service origin.

### 3. Push-key handling — remediated (G3)
The VAPID private key was already env-only and never exposed. The at-rest
subscription secrets (`p256dh`/`auth`) are now Fernet-encrypted (ADR-0020);
`endpoint` stays plaintext as the lookup/unique key. Legacy plaintext rows
self-heal via re-subscribe.

### 4. Input validation — verified good
Comprehensive Pydantic validation with `extra="forbid"`; no SQL injection vectors;
generic 404s avoid resource enumeration. No changes needed.

### 5. Dependency audit — remediated (G4)
CI had no dependency scanning. Added a `security-audit` job (`pip-audit --strict`
for backend; `pnpm audit --audit-level high` for frontend) and `.github/dependabot.yml`
for pip, npm, and GitHub Actions. `cryptography` is now explicitly pinned.

### 6. Audit-logging sweep — remediated (G7)
The web admin path logged correctly; the **CLI bypassed the audit log entirely**.
The CLI now appends one `admin_audit_log` row per action with `actor_id = NULL`
(no authenticated principal) and `details = {"via": "cli", ...}`, recording
changed field names only. User-initiated, non-admin actions (dose record/void,
reminder snooze/dismiss, profile edits, CSV export) remain intentionally
un-audited — consistent with the single-tenant threat model (ADR-0014); the audit
log is specifically the privileged-admin trail.

## Residual risks (accepted)

- **Rate-limit state is process-local** and resets on restart (free-tier cold
  start). Bounded by Argon2 cost + generic failures; revisit if the deploy scales
  out (ADR-0018).
- **Reminder snooze/take are CSRF-exempt** for the service-worker path on
  browsers lacking the Cookie Store API; SameSite=Lax still blocks the cross-site
  POST, and the endpoints are self-only (ADR-0019).
- **Rotating `PUSH_ENCRYPTION_KEY` orphans subscriptions**, which self-heal via
  re-subscribe (ADR-0020).
- **CSP** is conservative but keeps `style-src 'unsafe-inline'`; tightening it
  needs build-time nonces (out of scope).

## Out of scope (other Phase 10 items)

Accessibility pass, Lighthouse/bundle budgets, and the full Playwright suite are
tracked separately under Phase 10 and the tooling backlog; this review covers the
security slice only.
