# Phase N — <Title>: Requirements

## Why this phase

One paragraph: what state is the project in before this phase, and
what state should it be in after? Anchor the answer in the constitution
(`specs/mission.md`, `specs/roadmap.md`) so the phase's existence is
justified, not assumed.

## Sub-phases (optional)

If this phase has sub-phases (1a, 1b, 5a/b/c), list them here with a
one-line description of each. Otherwise delete this section.

## In scope

- Bullet list of what this phase delivers. Concrete enough that a
  reviewer can spot a gap. Group by sub-phase if applicable.

## Out of scope (deferred)

- Bullet list of things a reviewer might reasonably expect this phase
  to deliver, that it intentionally does not. Each bullet names the
  phase that *will* deliver it (or "v2", or "ADR-XXXX").

## Decisions

Table of non-obvious decisions made for this phase. Each row gives
reviewers a single place to push back.

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | … | … | … |

## Constraints from the constitution

How does this phase honor the binding rules in `specs/mission.md`?
Type-checking, security, no-duplication, etc. If a rule does not
apply, say so explicitly.

## Security considerations for new surface area

For every new endpoint, CLI command, dependency, or stored field,
state the threat consideration: what could go wrong, what mitigation
is in place. This section is required even when the answer is "this
phase introduces no new surface area" — say that explicitly.
