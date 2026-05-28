# Security Requirements Quality Checklist: In-App Admin User Management

**Purpose**: Merge-gate validation of the *security requirements' quality* — completeness,
clarity, consistency, measurability, and coverage — for this security-sensitive feature
(Constitution Principle I, NON-NEGOTIABLE). This tests whether the spec's security requirements
are well-written, NOT whether the implementation works.
**Created**: 2026-05-28
**Feature**: [spec.md](../spec.md)

## Authorization & Access Control

- [x] CHK001 Is the authorization rule for the admin surface stated as a requirement (who is permitted), and is the denial response for an authenticated non-admin distinguished from an unauthenticated caller? [Clarity, Spec §FR-001]
- [x] CHK002 Is it explicit that access control is enforced server-side independent of the UI, so hiding the nav entry is not relied on as the control? [Consistency, Spec §FR-001/§FR-015]
- [x] CHK003 Are the requirements clear on whether any admin may create or promote another admin (no tiered/delegated admin), and is that boundary stated rather than implied? [Completeness, Spec §Assumptions]
- [x] CHK004 Is admin-only access specified for the audit view as well as for the user-management operations? [Coverage, Spec §FR-014/§FR-001]

## Authentication & Session Lifecycle

- [x] CHK005 Are session-revocation requirements defined consistently for both password reset and deactivation? [Consistency, Spec §FR-007/§FR-008]
- [x] CHK006 Is the timing of session revocation specified in measurable terms (e.g., effective within the same request)? [Measurability, Spec §SC-005]
- [x] CHK007 Is it specified whether changing a user's email or role has any session effect, or is the absence of a session effect intentional and stated? [Gap, Spec §FR-006]
- [x] CHK008 Is it explicit that revocation affects all of the target's sessions (every device), not just the requesting one? [Clarity, Spec §FR-007/§FR-008]

## Credential & Secret Handling

- [x] CHK009 Is the one-time nature of a generated temporary password stated as a requirement (shown once, not retrievable later)? [Completeness, Spec §FR-004/§FR-020/§Edge Cases]
- [x] CHK010 Is "never stored in plaintext and never logged" stated as a requirement rather than only as an assumption? [Resolved → Spec §FR-020]
- [x] CHK011 Are randomness/entropy requirements for generated temporary passwords specified beyond the 12-character minimum? [Resolved → Spec §FR-004 (cryptographically secure RNG)]
- [x] CHK012 Is the 12-character minimum specified to apply to both typed and generated passwords? [Consistency, Spec §FR-005]
- [x] CHK013 Is credential-at-rest protection (hashing) a stated requirement, or only inherited implicitly via "reuse the domain"? [Resolved → Spec §FR-020 ("only a hash is persisted")]
- [x] CHK014 Is the behavior specified when a create/reset request supplies BOTH a typed password and the generate option, or neither? [Resolved → Spec §FR-004 (exactly one; both/neither rejected)]

## Privilege-Escalation & Lockout Guards

- [x] CHK015 Is "last remaining admin" defined precisely (active, non-deactivated admins) in the requirement text? [Clarity, Spec §FR-010]
- [x] CHK016 Does the last-admin guard requirement cover both removal paths — deactivation and demotion to user? [Completeness, Spec §FR-010]
- [x] CHK017 Are the self-action restrictions enumerated consistently (deactivate, password reset, and name/email/role edit) rather than only "deactivate"? [Consistency, Spec §FR-009/§FR-019]
- [x] CHK018 Are concurrent-action scenarios addressed in requirements (e.g., two admins acting so the last two admins are removed simultaneously, racing the guard)? [Resolved → Spec §FR-021]
- [x] CHK019 Can the no-lockout guarantee be objectively verified (zero successful self-deactivations and zero last-admin removals)? [Measurability, Spec §SC-006]

## Audit Logging

- [x] CHK020 Is the audit log specified to record exactly one entry per successful action, and is that count objectively measurable? [Measurability, Spec §FR-013/§SC-004]
- [x] CHK021 Is the exclusion of secret values (passwords/hashes) from audit content stated as a requirement? [Completeness, Spec §FR-013]
- [x] CHK022 Is the successes-only scope explicit, and is the handling of denied/blocked attempts (where they are recorded instead) specified? [Clarity, Spec §Clarifications]
- [x] CHK023 Is the audit log's append-only / non-editable property stated as a requirement, not only in the entity description? [Resolved → Spec §FR-022]
- [x] CHK024 Are audit-entry retention requirements (how long entries are kept) specified? [Resolved → Spec §Assumptions (retained indefinitely in v1; no purge)]
- [x] CHK025 Are the fields each audit entry must capture (actor, target, action, change summary, timestamp) fully enumerated and unambiguous? [Completeness, Spec §FR-013/§Key Entities]

## Data Protection & Disclosure

- [x] CHK026 Are logging requirements for the new admin endpoints aligned with the no-PII-in-logs rule (reference users by id; no emails/passwords)? [Traceability, Constitution P-I, Spec §Assumptions]
- [x] CHK027 Is the not-found vs forbidden response behavior specified so it does not unintentionally disclose account existence? [Resolved → Spec §Edge Cases (admin-only surface; not-found leaks nothing)]
- [x] CHK028 Are email-handling requirements consistent (admin-managed; case-insensitive uniqueness including soft-deleted users) across create and edit? [Consistency, Spec §FR-011/§FR-017]

## Input Validation & Bounds

- [x] CHK029 Are field-bound requirements (email format, name length, the allowed role set) specified for both create and edit? [Resolved → Spec §FR-023 (valid email, name 1–100); role set via FR-003/§FR-006]
- [x] CHK030 Is the rejected behavior for a duplicate email specified consistently for both create and edit? [Consistency, Spec §FR-011]

## Scenario & Edge Coverage

- [x] CHK031 Is the intended handling of a deactivated user's email reuse specified (rejected, with no in-app reactivation path)? [Coverage, Spec §FR-011/§FR-016]
- [x] CHK032 Is a recovery path specified when an admin loses a one-time temporary password (reset again)? [Recovery, Spec §Edge Cases]

## Dependencies, Assumptions & Conflicts

- [x] CHK033 Is the conflict with the prior "no admin web UI in v1" stance (glossary) explicitly reconciled in the requirements/assumptions? [Conflict, Spec §Assumptions]
- [x] CHK034 Is a threat consideration for the new surface (admin endpoints + audit table) required and traceable to an ADR/PR security note? [Traceability, Constitution P-I, Spec §Assumptions]
- [x] CHK035 Is the assumption that the existing server-side session-revocation pattern is sufficient stated and validated? [Assumption, Spec §Assumptions]

## Notes

- Check items off as the spec is confirmed/strengthened: `[x]` (satisfied) or `[~]` (resolved at PR/CI-runtime with a one-line link), per the constitution's merge-gate rule.
- Items marked `[Gap]` / `[Ambiguity]` / `[Conflict]` flag places where the **spec** may need a sentence added before implementation — they are requirement-quality findings, not test cases.
- **Resolved 2026-05-28** (folded into spec.md): CHK009–CHK011, CHK013, CHK014 (→ FR-004, FR-020),
  CHK018 (→ FR-021), CHK023 (→ FR-022), CHK024 (→ Assumptions: indefinite retention), CHK027
  (→ Edge Cases: admin-only surface, not-found leaks nothing).
- **Confirmed 2026-05-28 (at implementation)** — the remaining reviewer-confirmation items are
  now satisfied by **ADR-0014** + the shipped code/tests:
  - Authorization & sessions (CHK001–CHK008): `require_admin` (403 non-admin / 401 anon) gates the
    whole `/api/v1/users` surface incl. the audit view; reset and deactivate both revoke *all* of
    the target's sessions within the same request (`test_users_password.py` /
    `test_users_delete.py`); name/email/role edits intentionally have no session effect.
  - Lockout (CHK015–CHK017, CHK019): self-action guard (403) + last-admin guard (409, `FOR UPDATE`
    count) cover demote **and** deactivate; verified in `test_admin_guards.py` and the API self
    tests (`SC-006`).
  - Audit (CHK020–CHK022, CHK025, CHK026): exactly one append-only row per successful action, no
    secret values, referenced by id; `test_admin_audit.py` / `test_users_audit.py`.
  - Validation & disclosure (CHK028, CHK030–CHK032): EmailStr + case-insensitive uniqueness incl.
    soft-deleted on create **and** edit (409); lost temp password → reset again.
  - Dependencies/conflict (CHK033–CHK035): the "no admin web UI in v1" reversal is recorded in
    ADR-0014 and the glossary; the threat note lives in ADR-0014 §Consequences; the ADR-0001
    revoke pattern is reused as-is.
