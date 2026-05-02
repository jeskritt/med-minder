# ADR-0001 — Server-side sessions over JWTs for v1 auth

## Status

Accepted — Phase 1 commits to the `sessions` table shape; the
middleware that consumes it lands in Phase 2.

## Context

MedMinder needs an authentication mechanism for a single-tenant,
admin-provisioned user base. The two realistic options are:

- **Server-side sessions** with a signed HTTP-only cookie carrying an
  opaque session ID, backed by a `sessions` table.
- **JWTs** (signed bearer tokens), typically with short-lived access
  tokens and longer-lived refresh tokens.

The product context shapes the trade-off:

- No public sign-up, low session volume per user.
- Users may need to be force-logged-out (admin disables an account,
  user changes password, suspected device theft).
- The frontend is a same-origin PWA, not a federation of services.
- Mission-level security stance prefers revocable, short-lived state
  over long-lived bearer tokens.

## Decision

Use server-side sessions stored in the `sessions` table introduced in
Phase 1. Cookies are signed, HTTP-only, `SameSite=Lax`, and bound to
a session row whose `expires_at` is checked on every request. Logout,
password change, and admin "disable user" all delete or expire the
session row immediately.

Session token hashing uses **SHA-256** of the random token bytes (not
Argon2id or bcrypt). Session tokens are high-entropy random values, so
a slow KDF would tax every authenticated request without adding
security against offline cracking.

No JWTs in v1.

## Consequences

### Positive
- **Instant revocation.** Deleting a row in `sessions` is enough to
  log a user out — no waiting for a token to expire.
- **Smaller attack surface.** No JWT signing-key rotation problem, no
  algorithm-confusion vulnerabilities (`alg: none`, RS256↔HS256), no
  refresh-token storage decision.
- **Simpler reasoning.** A request is authenticated iff a row exists
  and isn't expired. That's it.
- **Aligns with single-tenant architecture.** We have no
  federation use case where bearer tokens would help.

### Negative
- **Stateful.** Every authenticated request reads the `sessions`
  table. Mitigated by an index on `token_hash` and the modest user
  volume.
- **Harder to scale to multi-region.** If/when MedMinder ever needed
  multi-region replication, session reads become cross-region. Not a
  v1 concern.

### Neutral
- The `sessions` schema is established in Phase 1 even though the
  middleware that consumes it lands in Phase 2.
