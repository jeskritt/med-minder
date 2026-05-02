# Phase N — <Title>: Plan

Numbered task groups. Each group ends with something committable.
If the phase has sub-phases, structure groups under sub-phase
headings (1a.1, 1a.2, 1b.1, …).

## 0. Prerequisites & dependencies

0.1 Any new dependencies (pinned versions in `pyproject.toml` /
    `package.json`).
0.2 Any CI changes (service containers, new jobs, coverage thresholds).
0.3 Any one-time setup that the rest of the plan assumes.

## 1. <First task group>

1.1 …
1.2 …

## 2. <Second task group>

…

## N. Documentation

N.1 ADRs to author or move from Proposed → Accepted.
N.2 Diagrams to add or update under `docs/diagrams/`.
N.3 README / deployment guide updates if the phase changes operator
    behavior.

## N+1. Exit-criteria sweep

N+1.1 Verify every check in `validation.md` is green on the PR
      branch.
N+1.2 PR description summarizes the decisions from `requirements.md`
      so reviewers can challenge them in one place.
N+1.3 PR description includes the "Security considerations" section
      from `requirements.md`.
