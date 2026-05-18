# Implementation Plan: Phase 6 — Drug-Interaction Cooldowns

**Branch**: `006-drug-interaction-cooldowns` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-drug-interaction-cooldowns/spec.md`

## Summary

Phase 6 turns the dormant `medication_interactions` table (shipped
Phase 1) into a working **warn + explicit-confirm + audited-override**
flow on the mark-as-taken write path, plus a read-side warning surface
and end-user rule management — enforcement model fixed by **ADR-0008**
(advisory, always overridable; distinct from the non-overridable
Phase 5 overdose 409s). The work is: one new pure-Python domain module
(`domain/interactions.py`), an `interaction_acknowledged` parameter +
interaction guard inside `create_dose()`, one new append-only table
(`dose_interaction_overrides`) with one Alembic revision, one new
structured 409 error (`InteractionCooldownViolation`, distinct `code`),
`interaction_state` added to `TodayItem` / `MedicationOut` /
`MedicationDetailOut`, a new rule-management router
(create/list/delete — **no update**), a "Conflicts with" section on the
medication form, a "take anyway" confirm modal, a live cooldown
indicator reusing the Phase 5 client counter, one Mermaid sequence
diagram, and the promotion of **ADR-0008 `Proposed → Accepted`** with
the Phase 6 PR. The three ADR-0008-deferred decisions are resolved in
`research.md` (D1/D2/D4).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 (strict), React 19, TanStack Router/Query, openapi-fetch — **no new runtime deps**
**Storage**: PostgreSQL 17 — **one Alembic revision** (new `dose_interaction_overrides` table); detection itself needs no schema change
**Testing**: pytest + pytest-asyncio + httpx `AsyncClient`/`ASGITransport` (backend, real Postgres via the rollback fixture); vitest + Testing Library + jsdom (frontend); Playwright (E2E)
**Target Platform**: PWA — desktop Chrome / Firefox, iOS Safari, Android Chrome
**Project Type**: Web monorepo — `backend/` (FastAPI) + `frontend/` (Vite/React)
**Performance Goals**: active interaction visible on the today view within 2s of opening (SC-004); displayed remaining time matches wall-clock truth within 5s over a 10-minute window and survives reload (SC-004)
**Constraints**: server-authoritative detection per ADR-0008 (a manipulated client clock cannot clear a conflict); event-driven refetch only — **no periodic polling** (FR-013); UTC arithmetic, user `timezone` honoured in display strings; Phase 5 overdose guards run first and are never weakened by an interaction acknowledgment (FR-010); constitution per-module 70% coverage floor preserved
**Scale/Scope**: single-tenant per user; tens of medications, tens of doses/med/day; no multi-tenant fan-out

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Compliance plan |
|---|---|---|
| **I — Security-Conscious by Default (NON-NEGOTIABLE)** | **PASS** | Detection, warnings, rule management and the override audit are scoped to the logged-in user; a cross-user negative test proves no rule/dose/conflict/override leaks (FR-019). Rule inputs validated at the boundary — both meds owned & non-deleted, bounded positive cooldown (FR-020). New surface (the dose-create acknowledgment write path, the override-audit table, three new rule endpoints) gets a "Security considerations" section in the PR. No new PII fields; users referenced by `id`. Merge gate: `checklists/` (security-sensitive — a `security.md` is added alongside `requirements.md`). |
| **II — Fully Typed Across the Stack** | **PASS** | New `domain/interactions.py`, the new model, schemas and router satisfy `mypy --strict`; the override table is SQLAlchemy 2.0 typed `Mapped[...]`; Pydantic strict. New TS (`InteractionConfirmModal`, hooks, form section) satisfies `tsc --noEmit` strict. OpenAPI is the single source of truth: `just generate-client` regenerates `frontend/src/api/v1.d.ts`; CI fails on drift. No array/JSON columns (D2) keeps typing clean. |
| **III — Loose Coupling, Testable Units** | **PASS** | `domain/interactions.py` has no SQLAlchemy/FastAPI imports — enforced by `tests/domain/test_interactions_no_db_imports.py` (mirrors the Phase 5 analogue). Pure detector exhaustively unit-tested. The guard inside `create_dose()` and the read-side warning surface both call the one detector — no duplicated logic between the write and read transports. |
| **IV — Documented Decisions** | **PASS** | ADR-0008 graduates `Proposed → Accepted` with the Phase 6 PR (FR-023). One Mermaid sequence diagram `docs/diagrams/sequence-drug-interaction-check.md` (FR-023); `docs/diagrams/README.md` updated. Full spec-kit artifact set in `specs/006-drug-interaction-cooldowns/`. `docs/user_stories.md` UC-4.3 reconciled with ADR-0008 (spec Assumptions / FR-023). No new ADR needed — ADR-0008 governs; the deferred decisions are recorded in `research.md`/`data-model.md`. |
| **V — Cross-Platform Tooling Integrity** | **PASS** | No `.sh`/`.ps1` pairs; no `scripts/` changes (the existing Python `scripts/generate_openapi_client.py` is reused). Dependency manifests unchanged (pinned, lockfiles committed). CI runs the existing pipeline (lint → typecheck → unit → integration → E2E → OpenAPI drift → build); the Phase 6 migration keeps `alembic upgrade head && alembic check` green. |

**No violations.** Complexity Tracking section below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-drug-interaction-cooldowns/
├── plan.md                       # This file
├── spec.md                       # Feature spec (/speckit-specify + /speckit-clarify)
├── research.md                   # Phase 0 — decisions D1–D7 (incl. the 3 ADR-0008 deferrals)
├── data-model.md                 # Phase 1 — existing reads + new dose_interaction_overrides
├── quickstart.md                 # Phase 1 — kickoff gate + per-story verification recipes
├── contracts/
│   └── interactions.openapi.yaml # Phase 1 — pre-implementation API contract
├── checklists/
│   ├── requirements.md           # Specify-stage merge gate (already green)
│   └── security.md               # NEW — Phase 6 security merge gate
└── tasks.md                      # Phase 2 output (/speckit-tasks; NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/medminder/
│   ├── domain/
│   │   ├── interactions.py        # NEW — pure detector + value objects + MedicationInteractionConflict (plain Exception, sibling of timers.py's)
│   │   └── doses.py               # MODIFIED — interaction_acknowledged param + guard in create_dose(); write override rows
│   ├── db/models/
│   │   └── dose_interaction_overrides.py  # NEW — append-only audit table (mirrors dose_voids.py)
│   ├── alembic/versions/
│   │   └── 0004_phase_6_dose_interaction_overrides.py  # NEW — one revision
│   ├── api/
│   │   ├── doses.py               # MODIFIED — pass interaction_acknowledged; add 409 model
│   │   ├── medications.py         # MODIFIED — interaction_state on list + detail
│   │   ├── schedules.py           # MODIFIED — interaction_state on TodayItem
│   │   ├── medication_interactions.py     # NEW — rule create/list/delete router
│   │   ├── schemas/
│   │   │   ├── interactions.py     # NEW — InteractionStateOut + to_interaction_state_out + rule schemas
│   │   │   ├── errors.py           # MODIFIED — InteractionCooldownViolation
│   │   │   ├── medications.py      # MODIFIED — interaction_state field
│   │   │   └── today.py            # MODIFIED — interaction_state field
│   │   └── ...
│   └── app.py                     # MODIFIED — register MedicationInteractionConflict handler; mount new router
└── tests/
    ├── domain/
    │   ├── test_interactions.py                  # NEW — pure detector, ≥95%
    │   ├── test_interactions_no_db_imports.py    # NEW — Principle III
    │   └── test_doses_interaction_guard.py       # NEW — guard in create_dose()
    ├── api/
    │   ├── test_doses_interaction_conflict.py    # NEW — 409 + override rows via direct API (FR-005)
    │   ├── test_interaction_state.py             # NEW — state on today/list/detail + cross-user (FR-019)
    │   └── test_medication_interactions_api.py   # NEW — rule CRUD-minus-update + validation (FR-020)
    └── db/
        └── test_dose_interaction_overrides.py    # NEW — FK RESTRICT + pair uniqueness

frontend/
├── src/
│   ├── api/v1.d.ts                # REGENERATED — DoseCreate.interaction_acknowledged, InteractionCooldownViolation, interaction_state, rule endpoints
│   ├── lib/timers.ts              # REUSED — tickFrom / formatRemaining for the live cooldown
│   ├── hooks/
│   │   ├── useMedicationInteractions.ts  # NEW — list/create/delete rules
│   │   └── useTakeDose.ts         # MODIFIED — InteractionConflictError; retry with interaction_acknowledged
│   ├── components/
│   │   ├── InteractionConfirmModal.tsx   # NEW — "take anyway" (mirrors UntakeConfirmModal)
│   │   └── medications/
│   │       ├── MedicationForm.tsx        # MODIFIED — "Conflicts with" section
│   │       ├── medicationFormSchema.ts   # MODIFIED — Zod + .refine()
│   │       └── MedicationList.tsx        # MODIFIED — interaction indicator
│   ├── routes/
│   │   ├── today.tsx              # MODIFIED — interaction indicator + take-anyway flow
│   │   ├── medications.new.tsx    # MODIFIED — sequence med POST → rule POSTs (partial-success)
│   │   └── medications.$id.edit.tsx # MODIFIED — diff rules → create/delete
│   └── __tests__/
│       ├── InteractionConfirmModal.test.tsx      # NEW
│       ├── medicationForm.conflicts.test.tsx     # NEW
│       └── interactionIndicator.test.tsx         # NEW
└── e2e/
    └── drug-interaction.spec.ts   # NEW — Playwright: warn → take anyway → clears

docs/
├── adr/
│   └── 0008-drug-interaction-enforcement.md  # MODIFIED — Status Proposed → Accepted (with Phase 6 PR)
├── diagrams/
│   ├── sequence-drug-interaction-check.md     # NEW — Mermaid sequence
│   └── README.md                              # MODIFIED — list the new diagram
└── user_stories.md                            # MODIFIED — reconcile UC-4.3 with ADR-0008
```

**Structure Decision**: Existing web-monorepo layout (`backend/` +
`frontend/`). Phase 6 follows established conventions: domain logic in
`backend/src/medminder/domain/`, the new persistent model under
`db/models/` mirroring `dose_voids.py`, API schemas under
`api/schemas/`, the rule router beside the other `api/` routers,
frontend tests mirroring the source tree, and a single Mermaid
sequence diagram under `docs/diagrams/`.

## Implementation Phasing

Sequenced for independently shippable slices (US1 → US2 → US3 per the
spec priorities); the warning surface (C) depends on the detector (B);
rule management (D/E) is a committed deliverable, not cuttable.

- **Phase A — Baseline sanity gate (FIRST):** `just generate-client`
  (PowerShell-direct: `python scripts/generate_openapi_client.py`) and
  `cd backend && python -m alembic check` must both be clean before any
  Phase 6 change, so later drift is unambiguously Phase 6's. Re-run
  `just migrate` → `alembic check` → `just generate-client` after the
  new migration. (See `quickstart.md` Phase A.)
- **Phase B — Backend detector + write path** (US1, FR-001–010):
  `domain/interactions.py`; `create_dose` guard +
  `interaction_acknowledged`; `dose_interaction_overrides` model +
  migration; `InteractionCooldownViolation`; `app.py` handler.
- **Phase C — Backend warning surface** (US2, FR-011): `interaction_state`
  on the three summary endpoints via `to_interaction_state_out`.
- **Phase D — Backend rule management** (US3, FR-015–018): the new
  router (create/list/delete only).
- **Phase E — Frontend**: regenerate client; "Conflicts with" form
  section + Zod; create/edit route orchestration;
  `useMedicationInteractions`; interaction indicator (reuse
  `lib/timers.ts`); `InteractionConfirmModal` + `useTakeDose`
  acknowledgment retry.
- **Phase F — Cross-cutting** (FR-019–023): tests (detector ≥95%,
  direct-API bypass, cross-user negative), sequence diagram, ADR-0008
  → Accepted, UC-4.3 reconciliation, typing/lint/coverage gates.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

(no entries — all gates passed)
