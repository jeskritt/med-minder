# Security Checklist: Self-Service Profile Editor

**Purpose**: Security merge gate for this credential-touching feature (Constitution
Principle I). Every item must be `[x]` (verified) or `[~]` (PR/CI-runtime, with a link)
before merge.
**Created**: 2026-05-23
**Feature**: [spec.md](../spec.md) · Decision: [ADR-0011](../../../docs/adr/0011-self-service-credential-management.md)

## Authentication & authorization

- [x] Password change requires the **current password**, verified server-side via
  `domain.passwords.verify_password` (FR-003) — `tests/domain/test_change_own_password.py`,
  `tests/api/test_me_password.py::test_wrong_current_password_returns_403`.
- [x] A wrong current password returns **403**, distinct from 422 (too-short) and never
  **401** (which the client treats as session-expired) — `tests/api/test_me_password.py`.
- [x] Both endpoints require an authenticated session; unauthenticated → **401**
  (`test_me_password.py::test_unauthenticated_returns_401`,
  `test_me_profile.py::test_patch_me_unauthenticated`).

## Scope / cross-user isolation

- [x] `change_own_password` and `PATCH /me` operate on the **authenticated `User`** /
  the caller's own email — no parameter selects another user (FR-006). Structurally
  enforced by signature; no id/email is accepted from the client.
- [x] Email and role are **not** editable via the editor — `extra="forbid"` rejects them
  (422) — `test_me_profile.py::test_patch_me_rejects_extra_fields` (FR-010).

## Session handling

- [x] A successful password change revokes **all** of the user's sessions and re-issues a
  fresh (rotated) cookie for the current device; other devices are logged out (FR-005) —
  `test_me_password.py::test_change_password_keeps_this_device_revokes_others`.
- [x] A display-name change has **no** session effects (FR-009) — covered by the existing
  `test_session_revocation.py::test_update_user_name_does_not_revoke_sessions`.

## Secret handling

- [x] Raw passwords (current/new) are never logged and never returned: `POST /me/password`
  responds `204` with no body; `PATCH /me` returns only `{id, name, role}` (FR-012).
- [x] The 12-char minimum lives once in `domain.passwords` (mapped to 422); not duplicated
  in the API schema — single source of truth with the CLI/login (FR-004).

## Data / migration

- [x] No new table or column; `alembic check` is an empty diff (no audit store in v1) —
  verified in the gate run (T028).

## PR

- [~] The PR description includes a **Security considerations** section covering the
  current-password re-auth, the 403/422/never-401 transport, revoke-all-then-reissue
  session handling, and the no-audit-in-v1 decision (link on merge).
