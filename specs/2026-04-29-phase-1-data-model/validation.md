# Phase 1 — Data Model & Admin CLI: Validation

The phase is mergeable when **every** check below passes on a fresh
clone with the Phase 1 PR applied.

## A. Migrations

1. `just migrate` against an empty Postgres 16 instance applies
   cleanly with no errors.
2. `alembic check` reports zero pending autogen changes after the
   migration is applied.
3. Downgrade-then-upgrade round-trip works: `alembic downgrade base`
   followed by `alembic upgrade head` succeeds without data loss
   warnings.
4. CI runs (1)–(3) on every PR via the new Postgres service container
   on the `backend-tests` job.

## B. Schema fidelity (per-table)

For each table, the migration creates exactly the columns and
constraints listed in `requirements.md` "Data schema":

5. **users** — UNIQUE on `LOWER(email)` enforced (insert
   `Foo@x.com` then `foo@X.COM` → second fails).
6. **users** — Argon2id hashes verify with `PasswordHasher.verify`
   round-trip; bcrypt or sha256 hashes are rejected by the verifier.
7. **sessions** — `token_hash` rejects duplicates; expired sessions
   remain queryable (cleanup is Phase 2's job).
8. **push_subscriptions** — UNIQUE `(user_id, endpoint)` enforced.
9. **medications** — `quantity_per_dose` stores `0.5` exactly via
   `Numeric(10, 3)`; `0.0` and negative values rejected.
10. **medications** — `times_per_day` independent of schedule count;
    no automatic reconciliation occurs.
11. **medication_interactions** — inserting `(A, B, 120)` then
    `(B, A, 60)` is rejected by the unordered-pair UNIQUE index.
12. **schedules** — `days_of_week = 128` rejected;
    `days_of_week = 0` accepted (a schedule with no active days is
    valid; UI may warn).
13. **schedule_medications** — duplicate `(schedule_id, medication_id)`
    rejected by the composite PK.
14. **doses** — inserting a dose where `doses.user_id` differs from
    `medications.user_id` is rejected by the cross-user-id trigger.
15. **doses** — `ON DELETE` of a referenced `medications` row is
    blocked (RESTRICT). Soft delete works instead.
16. **reminders** — CHECK rejects `(type='dose', medication_id=…,
    schedule_id=NULL)` and `(type='refill', medication_id=NULL,
    schedule_id=…)`.
17. **reminders** — CASCADE delete from `users` removes the user's
    reminders.

## C. Soft delete

18. Soft-deleting a user via the CLI sets `deleted_at` and leaves
    medications, schedules, and doses readable via the explicit
    `include_deleted=True` query path.
19. Default ORM queries (no `include_deleted`) exclude rows with
    `deleted_at IS NOT NULL`.
20. Doses written before a soft delete remain queryable for adherence
    reporting.

## D. Admin CLI

21. `medminder-admin --help` prints all subcommands. Installed as the
    `[project.scripts]` entry — running `python -m medminder.cli` and
    `medminder-admin` produce identical behavior.
22. `user add` rejects passwords shorter than 12 chars with a
    non-zero exit code.
23. `user add` reads passwords only via `--password-stdin`; no
    `--password` flag exists. Verify by `medminder-admin user add
    --help` not listing one.
24. `user add --email Foo@x.com` and a subsequent
    `user add --email FOO@X.COM` produces a duplicate-email error.
25. `user list` output columns are `id, email, name, role,
    created_at, deleted_at` in that order.
26. `user delete` sets `deleted_at` rather than removing the row;
    confirmed by querying the table directly in a follow-up test.
27. `user update --email user@x.com` with no mutating flags exits
    non-zero with "no changes specified".
28. Argon2id round-trip: a user added via the CLI can have their
    password verified by `medminder.domain.users.verify_password`
    (the same module the future Phase 2 auth code will call).

## E. Backup / restore

29. `db backup --out /tmp/backup.dump` creates a custom-format
    `pg_dump` file. On Unix, the file mode is `0600`. On Windows,
    the CLI emits an explicit ACL-warning line.
30. `db restore --in /tmp/backup.dump` refuses to run without
    `--yes`.
31. Round-trip: seed N users + M medications, `db backup`, drop the
    schema, `db restore --yes`, count rows — every count matches and
    every restored user's password still verifies via Argon2id.
32. Backup output contains password hashes (verify by grep on a
    text-extracted dump) — the CLI's PHI warning is therefore
    accurate.

## F. Code quality

33. `mypy --strict` clean over `backend/src/`. SQLAlchemy 2.0 typed
    `Mapped[...]` style, no `# type: ignore` without an inline
    rationale.
34. `ruff check` clean. `S` (bandit) rules pass — no hardcoded
    passwords or insecure shell calls in the `db backup|restore`
    subprocess invocations.
35. Coverage ≥ 85% across `backend/src/` per the `pytest-cov`
    threshold; no module sits below 70%.
36. No `TODO`/`FIXME` without a linked issue.

## G. Documentation

37. `docs/diagrams/er.md` exists, renders as a Mermaid `erDiagram` in
    GitHub preview, and includes every table and relationship from
    the migration. A reviewer can map each box and edge to a column
    in the spec.
38. `docs/deployment.md` reflects:
    - Backend boot runs `alembic upgrade head`.
    - First admin is bootstrapped via `medminder-admin user add` on a
      Koyeb one-shot job.
    - `medminder-admin db backup|restore` is the supported
      backup/restore path.
39. `backend/README.md` documents `medminder-admin` and the dual
    migration-vs-runtime DB roles.
40. `docs/adr/0001-sessions-over-jwts.md` exists with `Status:
    Accepted`, since Phase 1 commits to the `sessions` table shape.

## H. Security

41. PR description includes a "Security considerations" section
    naming new surface area (CLI, backup files, DB roles) and
    reviewing the decisions per `requirements.md` §"Security
    considerations for new surface area".
42. `pip-audit` (or `safety`) run on `backend/pyproject.toml` reports
    no known CVEs in the pinned versions of `argon2-cffi`,
    `sqlalchemy`, `alembic`, `psycopg`, `asyncpg`, `typer`.
43. No password, password hash, email, or DB connection string
    appears in CI logs from Phase 1 jobs (verified by spot-checking
    the latest CI run).

When A–H all pass, Phase 1 is done and the PR can merge.
