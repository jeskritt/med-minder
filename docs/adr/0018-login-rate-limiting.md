# ADR-0018 — Login rate-limiting: in-process sliding window, dual-keyed

## Status

**Accepted** (Phase 10 — Hardening).

## Context

`POST /auth/login` had no brute-force protection. The only friction on a
password-guessing or account-enumeration attack was the Argon2id verification
cost (~tens of ms) and the deliberately generic failure response. The Phase 10
security review (`docs/security-review-2026-05.md`, G1) flagged this as a
medium-severity gap.

Constraints from existing decisions:

- The app runs as a **single instance** with no Redis or shared cache
  (ADR-0017): a process-local limiter is sufficient and avoids a new dependency.
- The login path is **timing-uniform** (`domain/auth.py` always runs one Argon2
  verification) and must stay that way.
- Tests run over `ASGITransport` and must remain deterministic.

## Decision

A pure, dependency-free **sliding-window** limiter
(`domain/rate_limit.py::SlidingWindowLimiter`) wrapped by `LoginRateLimiter`,
instantiated once on `app.state` and reached via a FastAPI dependency. The clock
is injected (`now`, monotonic seconds) so the logic is unit-testable without
sleeps.

- **Dual-keyed**: a request is blocked when *either* the client IP (resolved via
  the existing `_client_ip` + `trusted_proxy_count`) or the normalized email is
  over threshold — so neither one IP spraying many emails nor one email hammered
  from many IPs can exceed the limit.
- **Threshold**: 5 failures per key per rolling 15-minute window → **429** with
  a `Retry-After` header and an identical generic body for any email (never
  reveals whether an account exists).
- The check runs **before** `attempt_login`, so it adds no crypto timing. Only
  failures are recorded; a **successful login resets** both keys.
- Memory is bounded by lazy per-key eviction plus an opportunistic full sweep
  past a key-count cap.

## Consequences

- **Positive**: real throttling on guessing/enumeration with zero new
  infrastructure; fully typed and unit-tested; no change to the timing-uniform
  guarantee.
- **Negative / accepted**: state is **process-local and lost on restart** — a
  free-tier cold start resets counters. Acceptable: brute force is still bounded
  by Argon2 cost and the generic-failure design, and the single-instance deploy
  means there is no second process to coordinate with. If the deploy ever scales
  out, this must move to a shared store.
- A locked-out client cannot distinguish a real account from a fake one (the 429
  precedes any lookup), preserving the enumeration resistance.
