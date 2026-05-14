# Timer state diagram: count_down

The `count_down` mode reports remaining time until
`last_dose_at + min_interval_minutes`, clamped at zero. The server-side
guard in `domain/doses.create_dose` enforces the interval regardless of
whether the call came from the FE (FR-005 / FR-006); the client UI is
advisory and ticks locally between server refetches.

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> cooldown : first dose recorded
    cooldown --> cooldown : client ticks locally\n(remaining_seconds decreases)
    cooldown --> ready : remaining_seconds reaches 0\n(haptic vibration fires once)
    ready --> cooldown : new dose recorded\n(interval resets)
    cooldown --> cooldown : MinIntervalNotElapsedError\n(forced POST while remaining > 0)\n→ HTTP 409 MinIntervalViolation
    ready --> ready : voided previous dose\n(server reconciles on refetch)

    note right of idle
        no doses recorded
        remaining_seconds = 0
        next_allowed_at = null
        Mark-as-taken control enabled
    end note

    note right of cooldown
        remaining_seconds > 0
        next_allowed_at > now
        Mark-as-taken control disabled
        Direct API POST → 409
    end note

    note right of ready
        remaining_seconds = 0
        next_allowed_at ≤ now
        Mark-as-taken control enabled
        Haptic vibration fires once on
        the zero-crossing transition,
        only while document.visibilityState
        === "visible" (FR-010); silent
        when navigator.vibrate is absent.
    end note
```

## Invariants

1. `remaining_seconds == 0` iff `next_allowed_at is None` or `next_allowed_at ≤ now`.
2. `remaining_seconds ≤ min_interval_seconds` always; `max(0, …)` is the
   only clamp on the server (`domain/timers.compute_timer_state`).
3. The server rejects `POST /api/doses` while `remaining_seconds > 0` for
   a `count_down` med — `MinIntervalNotElapsedError` raised in
   `domain/doses.create_dose`, mapped by the global handler in `app.py`
   to HTTP 409 with the `MinIntervalViolation` body.
4. Voiding the most recent dose collapses the cooldown — the next
   non-voided dose surfaces as `last_dose_at` and the timer recomputes.
5. Haptic feedback fires **once** per zero-crossing, gated on
   foreground visibility. iOS Safari has no Vibration API; degrade
   silently.
