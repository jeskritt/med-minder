# MedMinder — Diagrams

This directory accumulates architectural diagrams as the project
progresses. Each diagram is a Mermaid-rendered Markdown file.

## Diagram types

| Type | Purpose | Introduced in |
|------|---------|---------------|
| **ER (Entity-Relationship)** | Data model: tables, columns, relationships | Phase 1 — Data model & admin CLI |
| **Sequence** | Key user flows (login, mark-as-taken, etc.) | Phase 2 — Auth (login / logout) |
| **State** | Timer / reminder state machines | Phase 5 — Timer modes |

## Conventions

- **One diagram per file.** A file holds exactly one Mermaid block. If
  a diagram needs context, the prose lives above the block in the same
  file.
- **File-naming.**
  - ER: `er.md` (one ER diagram for the whole schema).
  - State diagrams: `state-<name>.md` — e.g.,
    `state-timer-count-down.md`, `state-reminder-lifecycle.md`. One file
    per state machine.
  - Sequence diagrams: `sequence-<name>.md` — e.g.,
    `sequence-login.md`, `sequence-mark-as-taken.md`,
    `sequence-reminder-dispatch.md`. One file per flow.
- **Mermaid syntax** so diagrams render natively in GitHub previews
  and VS Code's Markdown preview.
- **Update in-PR.** When a PR changes the behavior a diagram describes
  — schema, state machine, or flow — the diagram update is in the
  same PR. CI for the relevant phase fails if the diagram drifts.
- **No diagrams for things the code already shows clearly.** If a
  diagram would just be a worse-rendered version of a code snippet,
  the code wins.
