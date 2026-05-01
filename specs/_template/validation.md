# Phase N — <Title>: Validation

The phase is mergeable when **every** check below passes on a fresh
clone with the phase PR applied. Group checks by area; number them
continuously so reviewers can reference items by number.

Each check is concrete and mechanical — a reviewer should be able to
verify it without having to interpret intent. "Tests pass" is not a
check; "`just test` exits 0 and reports ≥ 85% coverage on
backend/src/" is.

## A. <First area, e.g., Migrations / Local dev / API>

1. …
2. …

## B. <Second area>

…

## Z. Documentation

N. Diagrams listed in `requirements.md` exist and reflect the
   committed implementation.
N+1. ADRs listed in `requirements.md` exist with the right `Status:`.
N+2. Deployment guide / README / glossary updated for any new
     operator-visible behavior.

## Z+1. Security

N+3. PR description has a "Security considerations" section per
     `requirements.md`.
N+4. Dependency audit (`pip-audit` / `pnpm audit`) reports no
     un-triaged high-severity findings on dependencies added in
     this phase.
N+5. No secrets in CI logs from this phase's jobs.

When every section above passes, Phase N is done and the PR can merge.
