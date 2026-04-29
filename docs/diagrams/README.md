# MedMinder — Diagrams

This directory will accumulate architectural diagrams as the project
progresses. Each diagram is a Mermaid-rendered Markdown file.

## Diagram types

| Type | Purpose | Introduced in |
|------|---------|---------------|
| **ER (Entity-Relationship)** | Data model: tables, columns, relationships | Phase 1 — Data model & migrations |
| **State** | Timer / reminder state machines | Phase 6 — Timer modes |
| **Sequence** | Key user flows (login, mark-as-taken, etc.) | Phase 3 — Auth (login / logout) |

## Conventions

- One `.md` file per diagram (e.g., `er.md`, `state-timer-countdown.md`).
- Use Mermaid syntax so diagrams render in GitHub and VS Code.
- Update diagrams in the same PR that changes the behavior they describe.
