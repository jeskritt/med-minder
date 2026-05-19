# Security Checklist: Phase 6 — Drug-Interaction Cooldowns

**Purpose**: Merge gate for the security-sensitive surface introduced
by Phase 6 — the interaction-acknowledgment write path in
`create_dose`, the append-only `dose_interaction_overrides` audit
table, the three new rule-management endpoints, and the
`InteractionCooldownViolation` 409 body.

**Created**: 2026-05-18
**Walked**: 2026-05-18 (Phase 6 Polish, T042)
**Constitution principle**: I — Security-Conscious by Default (NON-NEGOTIABLE)

## Server-side enforcement (interaction guard)

- [x] The interaction conflict is detected inside `domain/doses.create_dose()` and runs **after** the non-overridable Phase 5 overdose guards; an unacknowledged conflict raises `MedicationInteractionConflictError` *before* the `Dose` row is `session.add()`-ed. — guard sits after the count_down / multi_sub_dose blocks and before `Dose(...)` construction.
- [x] An `interaction_acknowledged` request never weakens a Phase 5 `count_down` / `multi_sub_dose` 409 (FR-010). — `tests/domain/test_doses_interaction_guard.py::test_phase5_overdose_guard_still_wins_with_ack` (count_down 409 still raised with `interaction_acknowledged=True`).
- [x] An integration test issues `POST /api/doses` directly via `httpx.AsyncClient`, bypassing the frontend, and confirms HTTP 409 `interaction_cooldown_active` + the documented body, with **zero** `doses` rows written (FR-005 / SC-001). — `tests/api/test_doses_interaction_conflict.py::test_unacknowledged_conflict_409_no_dose_written` (asserts exact key set + `count(doses)==0`).
- [x] The detector reads only the requesting user's own medications and non-voided doses; cross-user dose history never arms a cooldown. — `create_dose` partner-name/last-dose queries filter `Medication.user_id == user.id` / `Dose.user_id == user.id` and the `not_(voided_exists)` NOT EXISTS pattern.

## Override audit (new write path)

- [x] An acknowledged dose over an active conflict writes the `doses` row and one `dose_interaction_overrides` row per active conflict in the **same transaction**. — `create_dose` adds the override rows after the dose flush within the one session; `tests/domain/test_doses_interaction_guard.py::test_acknowledged_records_dose_and_override` asserts the row exists.
- [x] `dose_interaction_overrides` is append-only; FKs are `ondelete=RESTRICT`. — model + migration `0004`; `tests/db/test_dose_interaction_overrides.py` proves RESTRICT on dose and medication delete + `(dose_id, conflicting_medication_id)` uniqueness.
- [x] The override row leaks no field beyond (dose, conflicting medication); attribution is via `doses.user_id`. — model has only `id, dose_id, conflicting_medication_id, created_at`.

## Cross-user isolation (FR-019)

- [x] `interaction_state` on today / list / detail is computed only from the logged-in user's own rules and doses; a cross-user negative test proves no leak. — `load_active_interaction_state` filters on `user_id` + `deleted_at IS NULL`; `tests/api/test_interaction_state.py::test_cross_user_isolation` (second user sees `items == []`, no leaked state).
- [x] A rule whose partner medication is soft-deleted produces no `interaction_state` and no enforcement error (FR-018). — `tests/api/test_interaction_state.py::test_soft_deleted_partner_no_state` and `tests/domain/test_doses_interaction_guard.py::test_soft_deleted_partner_does_not_conflict`.

## Rule-management endpoints (FR-020)

- [x] `POST/GET/DELETE /api/v1/medications/{medication_id}/interactions` reject any medication not owned by the session user with **404** (no existence leak). — `_owned_medication` folds unknown / other-user / soft-deleted to one 404; `tests/api/test_medication_interactions_api.py::test_cross_user_pairing_and_listing_isolated`.
- [x] Duplicate unordered pair → 409; self-pair / non-positive cooldown → 422. — `test_duplicate_pair_409`, `test_self_pair_422`, `test_non_positive_cooldown_422`.
- [x] No update endpoint exists (create + delete only). — router exposes only GET / POST / DELETE.

## Data minimisation

- [x] Exactly one new persisted table; no new columns on existing tables for detection. — migration `0004` adds only `dose_interaction_overrides`; `alembic check` → "No new upgrade operations detected."
- [x] `InteractionCooldownViolation` / `InteractionStateOut` carry only FR-required fields — no extra PII. — schemas use `extra="forbid"`; only ids, display names, elapse time, remaining seconds.

## Dependencies

- [x] No new runtime dependencies in `backend/pyproject.toml`. — Phase 6 added none.
- [x] No new runtime dependencies in `frontend/package.json`. — Phase 6 added none.
- [~] `pip-audit` / `pnpm audit` produce no new high-severity findings. — CI-runtime gate; Phase 6 introduced **zero** new runtime deps (the two boxes above), so it cannot introduce a new advisory. Runs in CI on the phase PR.

## Static-analysis & typing

- [x] `just typecheck` passes. — backend `mypy --strict` clean (49 files); frontend `tsc -b` clean.
- [x] `just lint` passes (ruff, eslint, prettier). — `ruff` "All checks passed!"; frontend lint clean.
- [x] `just test` passes; project coverage ≥ 85 %; `domain/interactions.py` ≥ 95 %; no module < 70 %. — **289 backend passed, project line-rate 96.09 %**; `domain/interactions.py` 95 % (full branch coverage; `MedicationInteractionConflictError.__init__` exercised by the guard suite); lowest module ≥ 94 %. Frontend **75 passed (14 files)**.

## PR description

- [~] Phase 6 PR description includes a Security considerations section covering the acknowledgment write path, override audit, and cross-user isolation (SC-008). — reuse the threat-model paragraph below verbatim in the PR (PR authorship is the user's; git is out of automation scope here).

## Threat-model note

The security-critical surface is the **interaction-acknowledgment
write path** inside `domain/doses.create_dose()` and the append-only
**override audit**. (a) The trust boundary is the API/DB edge: the
client is untrusted; the server is authoritative. The interaction
detector and the `interaction_acknowledged` decision execute
server-side at the single chokepoint through which every `doses` row
is created, *after* the non-overridable Phase 5 overdose guards so an
acknowledgment can never defeat an overdose 409 (FR-010). (b)
Client-side warning alone is insufficient: a determined or buggy
client can `POST /api/doses` directly (curl, script, stale tab) and
skip the UI's confirm step — only the server-side raise of
`MedicationInteractionConflictError` (→ 409
`interaction_cooldown_active`, distinct from the Phase 5 codes)
prevents a silent conflicting dose; demonstrated by
`tests/api/test_doses_interaction_conflict.py` issuing the request
through `httpx.AsyncClient` with no browser. (c) Every detection,
warning, rule-management and override-audit query filters on the
session `user_id` and excludes soft-deleted medications and voided
doses, so neither the conflict computation nor the audit can be
influenced by another user's data or a retracted dose; the
rule-management endpoints collapse not-found / other-user /
soft-deleted into one indistinguishable `404` so medication existence
is not leaked. (d) The only new persisted data is the append-only
`dose_interaction_overrides` table — attributable via `doses.user_id`,
never updated or deleted (`ondelete=RESTRICT`), consistent with the
ADR-0005 audit precedent — so Phase 6 adds an honest override record
without broadening the PII surface.

*(This paragraph is the canonical threat-model text; reuse verbatim in
the Phase 6 PR description.)*

## Notes

- Constitution checklist gating: every box must be `[x]` (satisfied)
  or `[~]` (CI-runtime, with a one-line link) before merge.
- ADR-0008 promoted `Proposed → Accepted` with this phase (T024);
  `MedicationInteractionConflictError` is a plain `Exception`
  (sibling of `timers.py`'s) — see research.md D1 / data-model.md.
