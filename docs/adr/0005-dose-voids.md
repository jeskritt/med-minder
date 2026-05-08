# ADR 0005: Compensating-row pattern for un-take ("dose_voids")

## Status

Accepted — 2026-05-07 (Phase 4)

## Context

Phase 1a decision D6 made `doses` append-only: the application never
`UPDATE`s or `DELETE`s a dose row. Phase 4 ships an "un-take" action
so users can correct a misclick on the Today view. We need a way to
mark a previously-recorded dose as no-longer-effective without
violating D6.

## Decision

Add a `dose_voids` table with a `UNIQUE` foreign key to `doses.id`. A
dose is **effective** iff no matching `dose_voids` row exists. Readers
(Today view, future adherence and inventory) `LEFT JOIN dose_voids`
and filter `dv.id IS NULL`.

`POST /api/doses/{dose_id}/void` inserts a row. The original `doses`
row is never touched.

## Consequences

### Positive

- Honors D6 literally: dose rows are never updated.
- Double-void surfaces as a database `UNIQUE` violation, mapped to
  HTTP `409` — no application-level race window.
- Audit history is preserved for compliance and adherence reporting.
- The void event itself is attributable (`voided_by_user_id`,
  `voided_at`) for future audit needs.

### Negative

- Every reader must remember the `LEFT JOIN dose_voids` filter.
  Encapsulated in `medminder.domain.doses.today_view` and reused by
  Phase 7+ inventory and Phase 9 adherence.
- Two-table state machine for "is this dose effective?" is slightly
  harder to reason about than a single `deleted_at` column.

### Neutral

- The void can never be "un-voided"; re-taking the medication records
  a fresh `doses` row. This matches user intent (a void is a
  correction, not a state to flip).

## Alternatives considered

- **`doses.deleted_at` soft-delete column** — rejected; mutates a
  dose row and breaks D6's literal shape. Also complicates
  "history of corrections" reporting since the prior `taken_at` would
  be hidden behind a soft-delete filter on the same table.
- **Insert a negative-quantity compensating row in `doses`** —
  rejected; conflicts with the existing `CHECK (quantity > 0)`
  constraint (D7) and conflates "took -1 pill" with "voided the
  previous take."
- **Hard `DELETE` of the dose** — rejected; loses audit history and
  cannot answer "did the user intend this taken at one point?" The
  honest adherence record the mission promises depends on this.

## References

- `specs/004-mark-as-taken/data-model.md`
- `specs/004-mark-as-taken/research.md` §"Undo via compensating row, not `DELETE`"
- Phase 1a decision D6
