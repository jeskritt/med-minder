# ADR-0003 — Types cross the FE/BE boundary via generated OpenAPI client

## Status

Accepted — implemented in Phase 0.

## Context

The MedMinder frontend (TypeScript, strict) and backend (Python,
Pydantic v2 strict) need to agree on the shape of every request and
response. The realistic options are:

- **Hand-maintained Zod schemas on the frontend** that mirror Pydantic
  models on the backend.
- **Generated TypeScript types from the FastAPI OpenAPI document**,
  consumed by a typed fetch wrapper.
- **A shared schema language** (e.g. Protobuf, JSON Schema authored
  separately) that both sides compile against.

The mission's "minimal duplication" principle excludes parallel
hand-maintained models on the FE and BE. That rules out the first
option. The third would force us to author a third language for
schemas; FastAPI already emits OpenAPI for free.

## Decision

The FastAPI OpenAPI document is the single source of truth for FE/BE
contract.

- A Python script (`scripts/generate_openapi_client.py`) boots the
  FastAPI app in-process, dumps the OpenAPI JSON, and shells out to
  `openapi-typescript` to write `frontend/src/api/`.
- The generated client is **committed** to the repository.
- CI runs the generator and fails on a diff (`git diff --exit-code
  frontend/src/api/`) — drift between the spec and committed types is
  a build failure.
- The frontend uses `openapi-fetch`, which natively consumes the
  generated types for type-safe requests.

Zod still appears on the frontend for **runtime form validation** —
forms validate user input before it leaves the browser. That use is
local to the form layer and does not duplicate the wire-format types.

## Consequences

### Positive
- **One source of truth.** Pydantic models drive both runtime
  validation and frontend types.
- **Drift is a build failure**, not a runtime bug.
- **No bespoke schema language.** OpenAPI is a tool we already get
  for free.

### Negative
- **Generator must run in CI.** Any CI environment that can't boot
  the FastAPI app (e.g. missing native deps) breaks client
  generation. Mitigated by keeping the generator's runtime
  requirements equal to the backend test suite's.
- **Generated code is committed.** PR diffs include client changes
  alongside backend schema changes. This is intentional — it surfaces
  the FE/BE contract change in review — but it makes some PRs
  visually larger.

### Neutral
- We could later swap `openapi-fetch` for another consumer (`orval`,
  `swr-openapi`, etc.) without changing the source-of-truth strategy.
