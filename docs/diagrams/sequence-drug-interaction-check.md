# Drug-interaction warn / acknowledge / record

The Phase 6 mark-as-taken flow when an interaction cooldown is active
(ADR-0008: warn + explicit confirm + audited override; always
overridable; distinct from the non-overridable Phase 5 overdose 409s).

```mermaid
sequenceDiagram
    participant Browser
    participant API
    participant Domain as create_dose / detector
    participant DB as Database

    Note over Browser,DB: 1. First dose of the pair (medication A) — no warning
    Browser->>API: POST /api/doses {medication_id: A}
    API->>Domain: create_dose(A, interaction_acknowledged=false)
    Domain->>DB: rules touching A? partner last non-voided dose?
    DB-->>Domain: rule A↔B (120m); B has no non-voided dose
    Domain-->>API: detect → no conflict
    API->>DB: INSERT doses (A)
    API-->>Browser: 201 Created

    Note over Browser,DB: 2. Conflicting dose (B) without acknowledgment
    Browser->>API: POST /api/doses {medication_id: B}
    API->>Domain: create_dose(B, interaction_acknowledged=false)
    Domain->>Domain: Phase 5 overdose guards (run first, non-overridable)
    Domain->>DB: rules touching B? partner (A) last non-voided dose?
    DB-->>Domain: rule A↔B (120m); A taken 10m ago (own, non-voided, non-deleted)
    Domain->>Domain: detect_interaction_conflict → active (≈110m remaining)
    Domain-->>API: raise MedicationInteractionConflict
    API-->>Browser: 409 {code: "interaction_cooldown_active", conflicts:[A], remaining_seconds}
    Note right of Browser: NOT a dead-end — InteractionConfirmModal opens

    Note over Browser,DB: 3. User explicitly confirms ("Take anyway")
    Browser->>API: POST /api/doses {medication_id: B, interaction_acknowledged: true}
    API->>Domain: create_dose(B, interaction_acknowledged=true)
    Domain->>Domain: Phase 5 guards pass; detect → still active
    API->>DB: INSERT doses (B)
    API->>DB: INSERT dose_interaction_overrides (dose_B, conflicting=A)  %% same txn
    API-->>Browser: 201 Created
    Note over DB: append-only audit: who/when via doses.user_id, which conflict

    Note over Browser,DB: 4. Cooldown elapses or arming dose voided
    Browser->>API: GET /api/schedules/today (refetch on focus / after mutation)
    API->>Domain: load_active_interaction_state(now)
    Domain->>DB: partner A last non-voided dose within cooldown?
    DB-->>Domain: none (elapsed, or A's dose voided)
    Domain-->>API: interaction_state = null
    API-->>Browser: 200 — indicator cleared, no confirm step
```
