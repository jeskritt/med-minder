# ADR-0004 — Timer state machines: modeled where and evaluated when

## Status

**Accepted** (Phase 5a — count-up timer). Originally Proposed; promoted
by the US1 PR alongside the first state-machine implementation in
`backend/src/medminder/domain/timers.py::compute_timer_state` (count_up
branch). The companion Mermaid diagram lives at
`docs/diagrams/timer-count-up.md`. ADRs 5b (count_down) and 5c
(multi_sub_dose) follow when those modes land if a deviation is needed.

## Context

`specs/mission.md` defines four timer modes per medication:

- `none` — boolean "taken today" flag.
- `count_up` — time since last dose (Molly's interaction window).
- `count_down` — time until the next dose is permitted (Harry's PRN
  cooldown).
- `multi_sub_dose` — split timer bar for staggered sub-doses inside a
  single dosing window (Billy).

These are stateful: the answer to "what does this medication look
like *right now*?" depends on the latest `doses` row, the medication's
configuration, and wall-clock time.

The realistic options for *where* this state lives:

- **Server-side derivation only.** The frontend asks the API for the
  current state and renders it. Re-fetches on dose events and on a
  timer.
- **Client-side derivation only.** The API returns raw `doses` plus
  configuration; the client computes `count_up` / `count_down` /
  remaining sub-dose windows in the browser.
- **Hybrid.** Server returns canonical state at fetch time; client
  ticks the visible counter forward locally between fetches.

Constraints:

- Mission requires testable domain logic without a database or HTTP
  server (loose coupling, easily testable).
- Push-notification scheduling is server-side (Phase 7) — it must be
  able to compute "when is the next dose allowed?" independently.
- Drug-interaction enforcement (Phase 6) is server-side — it must
  reject a `mark-as-taken` action on the server, not just hide a
  button.

## Decision

The state machine is **modeled in the domain layer** as pure Python
functions taking `(medication_config, dose_history, now)` and
returning a `TimerState` value object. This module is the single
source of truth for timer semantics. It has no SQLAlchemy or FastAPI
imports.

Evaluation is **hybrid**:

- Server-side evaluation is authoritative. Every API response that
  describes a medication includes the current `TimerState` computed
  by the domain module.
- Client-side displays a *ticking* counter that derives from the
  server-supplied state plus a monotonically advancing local clock.
  The client never decides whether a dose is allowed — it asks the
  server before allowing the user to mark-as-taken.
- The TypeScript counter helper is generated from a declarative
  description of the same state machine (or is a thin port) so the FE
  and BE cannot disagree about, e.g., whether the count-down has
  reached zero.

ADRs follow when each timer mode lands (5a, 5b, 5c) if a sub-mode
forces a deviation from this approach.

## Consequences

### Positive
- **Single source of truth for timer rules.** Reused by:
  HTTP responses, APScheduler reminder calculations, drug-interaction
  enforcement, and tests.
- **Pure functions are trivially testable.** No DB, no clock
  injection beyond a `now: datetime` argument.
- **Authoritative server.** Clients can't bypass cooldowns by
  spoofing local time.

### Negative
- **Two implementations of the visible counter** (Python for
  server-side state, TypeScript for the smooth tick). Keeping them in
  sync requires intent — likely a small JSON description of the
  machine, or a TS port committed alongside Python tests that fix
  expected outputs.
- **More server round-trips than a fully-client-side approach.** Each
  mark-as-taken is a server call before the UI updates. Acceptable
  given mission scale.

### Neutral
- This decision does not pick a state-machine library
  (XState, transitions, etc.). The choice happens with Phase 5a, in
  a follow-up ADR if a library is introduced.
