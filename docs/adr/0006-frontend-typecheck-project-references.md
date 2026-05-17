# ADR 0006: Frontend type-check via `tsc -b` project references

## Status

Accepted — 2026-05 (Phase 5)

## Context

`just typecheck-frontend` ran `tsc --noEmit` against `frontend/tsconfig.json`,
which is `{ files: [], references: [tsconfig.app.json, tsconfig.node.json] }`.
Plain `tsc` (without `-b`) ignores project references and compiles the
root's `files` — empty — so the gate **type-checked nothing** and had
been green-by-doing-nothing since before Phase 5. The only real check
was the incidental `tsc -b` inside `pnpm build`.

Worse, `tsconfig.app.json` `include: ["src"]` pulled `src/__tests__/**`
into the app project, but its `types: ["vite/client"]` had no `node` or
Vitest/jest-dom globals — so once a real check ran, every test file
that used `node:*` imports or Vitest mock typing failed. Test and e2e
code had effectively never been type-checked.

## Decision

Type-check the frontend with **`tsc -b` over a four-project layout**:

- `tsconfig.app.json` — browser app; `exclude`s test/setup files so it
  stays browser-pure.
- `tsconfig.node.json` — `vite.config.ts` (unchanged).
- `tsconfig.test.json` — **new**; `extends` app, adds
  `["node", "vitest/globals", "@testing-library/jest-dom"]` types,
  `include: ["src"]` (superset, so route files pulled in via test
  imports still see `routeTree.gen.ts`'s module augmentation).
- `tsconfig.e2e.json` — **new**; Playwright/node only
  (`types: ["node"]`, no DOM/Vitest), covers `e2e/**` +
  `playwright.config.ts`.

Root `tsconfig.json` references all four. `package.json` `typecheck`
script changed `tsc --noEmit` → `tsc -b`, so `just typecheck-frontend`
and `pnpm build` use the same real gate. Surfaced ~4 latent test-file
type errors, fixed in the same PR.

## Consequences

### Positive

- The gate now actually type-checks app **and** test **and** e2e code;
  proven by inject-then-revert sanity checks.
- App project stays browser-pure (no `node`/test globals leak into
  app-code type space).
- Single command (`tsc -b`) covers all projects incrementally; no extra
  justfile recipes.

### Negative

- Four tsconfig files to keep coherent. The test project re-type-checks
  app source (superset `include`) — slightly redundant, but required so
  the router module augmentation is visible where tests import routes.

### Neutral

- CI behavior unchanged in spirit (`pnpm build` already ran `tsc -b`);
  this makes the *local* gate honest and matches it.

## Alternatives considered

- **Single tsconfig with widened `types`** — rejected; leaks
  `node`/Vitest globals into app-code type space, weakening the
  browser-only guarantee.
- **Exclude `__tests__` from tsc entirely** — rejected; test code would
  stay permanently unchecked (the original bug, just narrower).
- **Keep `tsc --noEmit`, fix the root `files`** — rejected; project
  references are the idiomatic Vite + Vitest + Playwright layout and
  `tsc -b` is the correct driver.

## References

- `frontend/tsconfig.{json,app,node,test,e2e}.json`
- `specs/roadmap.md` "Tooling backlog" (the item this ADR closed)
