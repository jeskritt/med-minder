# Implementation Plan: Medications CRUD

**Branch**: `2027-medications-crud` | **Date**: 2026-05-06 | **Spec**: `/specs/003-medications-crud/spec.md`
**Input**: Feature specification from `/specs/003-medications-crud/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Implement the core ability for users to manage their medications. Users can add, edit, soft-delete, and list medications, including specifying dosages, multi-dose schedules, and refill inventory thresholds. Schedules are managed inline with the medication form. A print stylesheet is included for physical sharing of medication records.

## Technical Context

**Language/Version**: Python 3.12 (Backend), TypeScript / Node 20+ (Frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, React 18, Vite, TanStack Router/Query, react-hook-form, zod
**Storage**: PostgreSQL 16 (via asyncpg / SQLAlchemy)
**Testing**: pytest, pytest-cov (Backend); Vitest, React Testing Library (Frontend)
**Target Platform**: Linux server (Backend), Browsers / PWA (Frontend)
**Project Type**: Web Application
**Performance Goals**: Standard CRUD performance
**Constraints**: Single-tenant by design. Soft-delete only on `medications`. No PII logged.
**Scale/Scope**: Phase 3 (Medications CRUD). Full-stack vertical slice including routing, DB models, API, and UI components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify the planned phase upholds each principle in
`.specify/memory/constitution.md`. Flag violations under "Complexity
Tracking" with explicit justification, or revise the plan.

- **I. Security-Conscious by Default** — does the phase introduce new
  surface area (endpoints, fields, dependencies, third-party calls,
  log lines)? If yes, a threat consideration must be drafted for the
  PR. Argon2id for credentials, server-side sessions, and least-
  privilege DB roles preserved.
- **II. Fully Typed Across the Stack** — `mypy --strict` and
  `tsc --noEmit` clean across changed code; OpenAPI client
  regenerated and committed when the API changes.
- **III. Loose Coupling, Testable Units** — domain logic for new
  features lives in modules testable without a DB or HTTP server;
  no duplicated logic between CLI and web transports.
- **IV. Documented Decisions** — phase has `requirements.md`,
  `plan.md`, `validation.md`. ADRs drafted for non-obvious decisions.
  ER / state / sequence diagrams updated when the data model, a
  state machine, or a key flow changes.
- **V. Cross-Platform Tooling Integrity** — new scripts are Python
  (no `.sh`/`.ps1` pairs); new dependencies pinned with upper bounds;
  CI gates green; no `continue-on-error: true` on required jobs.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

backend/
├── src/medminder/
│   ├── api/routes/medications.py
│   ├── db/models/medications.py
│   └── domain/medications.py
└── tests/
    └── test_medications_api.py

frontend/
├── src/
│   ├── routes/
│   │   ├── medications.tsx
│   │   ├── medications.new.tsx
│   │   └── medications.$id.edit.tsx
│   ├── components/
│   │   └── medications/
│   │       ├── MedicationForm.tsx
│   │       ├── MedicationList.tsx
│   │       └── ScheduleInput.tsx
│   └── api/
└── tests/
    └── components/medications/MedicationForm.test.tsx
```

**Structure Decision**: Using the Web Application structure separated into frontend React/Vite/TanStack App and backend Python/FastAPI service.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
