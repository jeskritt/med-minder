<!--
Sync Impact Report — 2026-05-03

Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR — expanded Principle IV and the
"Phase spec triplet" / "Validation file" workflow bullets to
recognize the spec-kit artifact set adopted from Phase 2 onward
(blessed in CLAUDE.md). No principle removed or redefined; Phases 0
and 1 retain the legacy triplet shape, so existing artifacts remain
compliant.

Templates / docs requiring updates:
- ✅ checked, no changes needed: `CLAUDE.md` already documents the
  Phase 2+ convention switch.
- ✅ checked, no changes needed: `.specify/templates/plan-template.md`
  Constitution Check section.
- ✅ updated: `specs/2026-05-02-phase-2-auth/plan.md` —
  Constitution Check §IV no longer carries an "out of scope"
  deferral now that the constitution recognizes the new shape.

Follow-up TODOs: none.
-->

<!--
Sync Impact Report — 2026-05-02

Version change: (template, unfilled placeholders) → 1.0.0
Bump rationale: Initial ratification. The previous file was an
identical copy of `.specify/templates/constitution-template.md` with
every `[PLACEHOLDER]` token unfilled. This is the first concrete fill,
distilled from the existing long-form sources at `specs/mission.md`,
`specs/tech-stack.md`, and `specs/roadmap.md`.

Principles (initial creation, no prior versions):
- I. Security-Conscious by Default (NON-NEGOTIABLE)
- II. Fully Typed Across the Stack
- III. Loose Coupling, Testable Units
- IV. Documented Decisions
- V. Cross-Platform Tooling Integrity

Added sections:
- Security & Data Constraints
- Development Workflow & Quality Gates
- Governance (concrete amendment, versioning, and review rules)

Removed sections: none.

Templates / docs requiring updates:
- ✅ updated: `.specify/templates/plan-template.md` — Constitution
  Check gates replaced with concrete principle-by-principle checks.
- ✅ updated: `README.md` — added a link to the constitution at the
  top of the Documentation list.
- ✅ checked, no changes needed: `.specify/templates/spec-template.md`,
  `.specify/templates/tasks-template.md`, `.specify/templates/checklist-template.md`
  (no constitution-specific references; principles apply transitively
  via the plan template's Constitution Check).
- ✅ checked, no changes needed: `specs/mission.md`,
  `specs/tech-stack.md`, `specs/roadmap.md` — the constitution is a
  distillation of these; they remain the long-form references and are
  still consistent with the principles below.

Follow-up TODOs: none.
-->

# MedMinder Constitution

## Core Principles

### I. Security-Conscious by Default (NON-NEGOTIABLE)

MedMinder stores personal medication records. Treat that data as
protected health information regardless of regulatory classification.

- Encrypt in transit (HTTPS only). Secrets live in env vars and CI
  secret stores, never in the repo.
- Hash credentials with Argon2id; hash session tokens with SHA-256.
- Prefer revocable, server-side sessions over long-lived bearer
  tokens. No JWTs in v1 (see ADR-0001).
- Apply least privilege: separate migration and runtime DB roles;
  reference users by `id` in logs (no PII).
- Minimize data collection. Every new field requires justification in
  the corresponding phase `requirements.md`.
- New surface area (endpoint, dependency, third-party call, data
  field, log line) requires an explicit threat consideration in the
  relevant ADR or PR description.

When security and convenience conflict, security wins.

**Rationale**: A medication tracker that leaks user data fails its
mission, however usable it is.

### II. Fully Typed Across the Stack

- Python code MUST pass `mypy --strict`.
- TypeScript code MUST pass `tsc --noEmit` with `strict: true`.
- SQLAlchemy models MUST use the 2.0 typed `Mapped[...]` style.
- Pydantic models MUST run in strict mode.
- `# type: ignore` is permitted only with an inline rationale.

Wire-format types are derived, never hand-maintained: the FastAPI
OpenAPI document is the single source of truth, and the TypeScript
client is generated from it and committed under `frontend/src/api/`.
CI MUST fail when the committed client drifts from the spec
(see ADR-0003).

**Rationale**: Types catch a meaningful share of bugs before review.
Generated wire types eliminate the parallel-model maintenance bug
class entirely.

### III. Loose Coupling, Testable Units

- Domain logic (e.g., `medminder.domain.users`) MUST be testable
  without a database or HTTP server.
- The CLI and the web app share one domain layer. No duplicated
  logic between transports.
- Functions and files stay reasonably small. Deeply nested code,
  deeply nested data, and clever indirection are non-goals. Apply
  SOLID, KISS, DRY, and YAGNI at every boundary.
- Unused code MUST be deleted, not commented out.
- `TODO` / `FIXME` comments MUST cite a tracked issue.

**Rationale**: Small, testable units make the phase-by-phase delivery
model viable. Single-source-of-truth domain modules prevent the
duplication-between-transports bug class.

### IV. Documented Decisions

- Non-obvious decisions MUST be captured as ADRs under `docs/adr/`.
- The data schema MUST be reflected in `docs/diagrams/er.md`.
- State machines (timer modes, reminder lifecycle) MUST have state
  diagrams.
- Key user flows MUST have sequence diagrams.
- Each delivery phase MUST commit a complete artifact set under
  `specs/<YYYY-MM-DD>-phase-<N>-<name>/` BEFORE implementation
  begins. Phases 2 and onward use the spec-kit set: `spec.md` (what
  & why, with Clarifications), `plan.md` (how, with the spec-kit
  Constitution Check), `research.md`, `data-model.md`,
  `quickstart.md`, and `contracts/`. Phases 0 and 1 used the legacy
  triplet (`requirements.md` + `plan.md` + `validation.md`) and are
  not retro-converted. Every phase MUST also commit at least one
  merge-gate checklist under `checklists/` (typically
  `requirements.md`; phases with security-sensitive surface area
  also commit `security.md`). The phase merges only when every item
  in the merge-gate checklist(s) is `[x]` or `[~]` (PR/CI-runtime,
  with a one-line link). For Phases 0 and 1, `validation.md`
  continues to play this role.

**Rationale**: Spec-first delivery makes scope reviewable, decisions
challengeable, and "done" mechanical rather than negotiable.

### V. Cross-Platform Tooling Integrity

- Development happens on Windows; deployment runs on Linux.
- Anything under `scripts/` MUST be Python. No parallel `.sh` /
  `.ps1` pairs. Bash is permitted only inside Linux containers
  (Dockerfile `RUN` steps, GitHub Actions Linux jobs).
- Dependencies MUST be pinned with upper bounds (Python and Node).
  Lockfiles MUST be committed.
- Pre-commit hooks (ruff, mypy, eslint, prettier, `tsc --noEmit`)
  MUST pass before commit.
- CI MUST run lint → typecheck → unit tests → integration tests
  (against a real Postgres service container, from Phase 1) → E2E
  (from Phase 4) → OpenAPI drift check → build. No required job may
  carry `continue-on-error: true`.
- Dependency audit (`pip-audit` / `pnpm audit`) runs on every PR;
  un-triaged high-severity findings block merge.

**Rationale**: The dev/prod platform split is structural. The policy
makes it visible rather than letting it leak into ad-hoc per-platform
scripts.

## Security & Data Constraints

These constraints are derived from Principle I and apply to every
phase:

- **Single-tenant by design.** No public sign-up. Users are
  provisioned via the `medminder-admin` CLI.
- **Soft delete only** on `users`, `medications`, and `schedules`.
  `doses` are append-only — adherence history MUST NOT cascade-delete.
- **Server-side sessions only** (signed HTTP-only cookies,
  `SameSite=Lax`). Logout, password change, and admin "disable user"
  expire the session row immediately.
- **Backups** flow through `medminder-admin db backup|restore` only.
  Backup files contain password hashes and medication records — the
  CLI prints a "treat as PHI" warning and chmods to `0600` on Unix.
- **Dual DB roles.** Migrations run under a privileged role; the
  runtime app role gets `SELECT/INSERT/UPDATE/DELETE` only. Both
  roles are documented in `docs/deployment.md`.
- **No raw passwords, password hashes, emails, or DB connection
  strings** in CI logs or application logs.

## Development Workflow & Quality Gates

- **Phase-based delivery.** `specs/roadmap.md` enumerates phases.
  Each phase ends with something runnable, typed, tested, and
  documented.
- **Phase spec set.** Phases 2+ commit the spec-kit set
  (`spec.md`, `plan.md`, `research.md`, `data-model.md`,
  `quickstart.md`, `contracts/`). Phases 0 and 1 use the legacy
  `requirements.md` + `plan.md` + `validation.md` triplet and are
  not retro-converted.
- **Coverage gate.** `pytest-cov` enforces ≥ 85% across
  `backend/src/` from Phase 1 onward; no module sits below 70%.
- **Merge gate.** For Phases 0 and 1, `validation.md` is the merge
  gate. For Phases 2+, the merge gate is the union of the
  `checklists/` files (at minimum `checklists/requirements.md`;
  security-sensitive phases also commit `checklists/security.md`).
  Every item MUST be `[x]` or `[~]` (PR/CI-runtime, with a one-line
  link) before merge.
- **Security note in the PR.** Every phase PR description MUST
  include a "Security considerations" section enumerating new
  surface area and the decisions made about it, per Principle I.
- **SpecKit templates.** Slash-command workflows under
  `.specify/templates/` (plan, spec, tasks, checklist) MUST stay
  aligned with this constitution; divergence requires either a
  template update or an explicit deviation note in the phase plan.

## Governance

This constitution supersedes other engineering practices in this
repository. Where it conflicts with a longer-form document
(`specs/mission.md`, `specs/tech-stack.md`, `specs/roadmap.md`,
phase specs, ADRs), the conflict MUST be resolved in the same PR —
either by amending the constitution or by updating the conflicting
document. Silent divergence is a violation.

**Amendment procedure.** Amendments are made via a PR that:

1. Updates `.specify/memory/constitution.md`.
2. Bumps the version per the policy below and updates "Last Amended".
3. Records the rationale in the Sync Impact Report at the top of
   `constitution.md`.
4. Propagates the change to dependent artifacts: phase-spec templates
   under `.specify/templates/`, ADRs the change supersedes, and any
   `specs/` document the amendment touches.

**Versioning policy.**

- **MAJOR** (X.0.0) — backward-incompatible governance or principle
  removal/redefinition.
- **MINOR** (1.X.0) — new principle or section added; materially
  expanded guidance.
- **PATCH** (1.0.X) — clarifications, wording, typo fixes, non-
  semantic refinements.

**Compliance review.** Every phase PR's reviewer MUST verify that
the phase's merge-gate artifact (Phases 0/1: `validation.md`;
Phases 2+: the `checklists/` set) covers each principle that the
phase touches (typing, tests, coverage, security note, ADRs,
diagrams). The phase merges only when the gate is green per
Principle IV.

**Runtime guidance.** Day-to-day delivery context lives in:

- `specs/mission.md` — vision, target users, scope, non-goals.
- `specs/tech-stack.md` — authoritative tech choices.
- `specs/roadmap.md` — phase order and exit criteria.
- `docs/adr/` — non-obvious decisions.

This constitution distills the binding rules from those documents;
the documents themselves remain the long-form references.

**Version**: 1.1.0 | **Ratified**: 2026-05-02 | **Last Amended**: 2026-05-03
