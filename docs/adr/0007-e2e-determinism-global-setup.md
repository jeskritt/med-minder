# ADR 0007: E2E determinism via Playwright global-setup + shared login

## Status

Accepted — 2026-05 (Phase 5)

## Context

The Phase-4 `granny-smoke.spec.ts` and the Phase-5 `timer-modes.spec.ts`
scenarios were all skip-gated and effectively dead. When run, every
spec inlined the same login sequence: fill credentials, click "Sign
in", then immediately `page.goto(...)`. `login.tsx` logs in via an
async mutation that, on success, `navigate({ to: "/medications" })`
and sets the session cookie. The bare `goto` raced that round-trip —
the destination route's `beforeLoad` `/me` check 401'd before the
cookie landed and redirected to `/login`, so assertions failed.

Two further issues surfaced once login worked: the specs depended on
seeded users / medication fixtures that nothing provisioned, and they
created same-named meds every run against the shared long-lived dev DB,
so name-scoped locators matched accumulated duplicates. The investigation
also uncovered a **real product defect**: `useTakeDose` only invalidated
the today query cache, so marking a dose from the medications list or
detail views never refreshed them — fixed alongside.

## Decision

Make the e2e suite deterministic, locally runnable, and isolated from
shared state:

- **`e2e/helpers.ts` shared `login(page, email, password)`** that
  awaits the app's own success signal (`toHaveURL(/\/medications$/)`)
  before returning — kills the race.
- **`e2e/global-setup.ts`** (wired via `playwright.config.ts`
  `globalSetup`): idempotently provisions the demo + granny users
  (`medminder-admin user add`, then `user update --password-stdin` on
  duplicate so the password is deterministic) and the granny `none`-mode
  medication via the authenticated API.
- **Unique per-run med names** (`${name} ${Date.now()}`) in
  `timer-modes.spec.ts` so locators target this run's med regardless of
  dev-DB accumulation; assertions scoped to the detail `<main>`.
- **Await the real refetch** for the no-optimistic-update
  multi_sub_dose path (`Promise.all([waitForResponse(detail GET), click])`)
  instead of racing a bare text wait.

Specs remain `E2E_RUN_*`-gated only because CI does not yet stand the
docker stack up (tracked separately as a Phase 10 candidate).

## Consequences

### Positive

- All three smokes are green and deterministic on repeat runs.
- The login race is fixed in one shared place; future specs reuse
  `login()`.
- Forced discovery + fix of the `useTakeDose` cache-invalidation defect
  (a genuine user-facing bug).

### Negative

- `global-setup.ts` shells out to `docker compose exec` for user
  creation (no public signup endpoint) — couples e2e setup to the
  docker stack, acceptable since the suite requires it anyway.
- Unique per-run names accumulate throw-away meds in the dev DB
  (harmless; the DB is disposable). Chosen over global-setup teardown
  to keep setup simple and side-effect-light.

### Neutral

- The skip gates stay until CI runs the stack; this ADR makes the specs
  *reliable*, not yet *CI-enforced*.

## Alternatives considered

- **Per-spec inline login (status quo)** — rejected; the race was
  copy-pasted in every spec with no single place to fix.
- **`global-setup.ts` DB teardown of test meds** — rejected for now;
  unique per-run names achieve state-independence with less machinery
  and no destructive cleanup logic.
- **Ephemeral per-run database** — rejected as disproportionate for a
  skip-gated local suite; revisit if/when e2e runs in CI.

## References

- `frontend/e2e/{helpers,global-setup}.ts`,
  `frontend/playwright.config.ts`
- `frontend/src/hooks/useTakeDose.ts` (the cache-invalidation fix)
- `specs/005-timer-modes/checklists/security.md` (T064 live-green note)
- `specs/roadmap.md` "Tooling backlog" (run e2e in CI — Phase 10)
