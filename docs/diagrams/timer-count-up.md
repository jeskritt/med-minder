# Timer state diagram: count_up

The `count_up` mode reports time since the most-recent **non-voided** dose.
Voided doses (Phase 4 `dose_voids` rows) are filtered at the SQL boundary
(`load_non_voided_history_for_meds`); the state machine sees only the
filtered history.

```mermaid
stateDiagram-v2
    [*] --> no_doses
    no_doses --> ticking : first dose recorded
    ticking --> ticking : new dose recorded\n(window reseeds from server)
    ticking --> ticking_from_prior : most-recent dose voided\n(prior non-voided dose surfaces)
    ticking --> no_doses : last remaining dose voided
    ticking_from_prior --> ticking : new dose recorded
    ticking_from_prior --> no_doses : last remaining dose voided

    note right of no_doses
        elapsed_seconds = null
        UI: "no doses recorded yet"
    end note

    note right of ticking
        elapsed_seconds = int(now − last_dose_at)
        Server uncapped (FR-003)
        UI caps display at "over 24h ago"
        Client ticks locally between refetches
        (monotonic clock seeded from as_of)
    end note
```

## Invariants

1. `last_dose_at` always refers to the **newest non-voided** dose.
2. `elapsed_seconds` on the wire is **never capped** — Phase 6 drug-interaction
   logic depends on full precision (FR-003).
3. The display cap at "over 24h ago" is a frontend-only concern
   (`frontend/src/lib/timers.ts::formatElapsed`).
4. Voiding the most recent dose collapses to `ticking_from_prior` (or to
   `no_doses` if no other non-voided dose remains).
