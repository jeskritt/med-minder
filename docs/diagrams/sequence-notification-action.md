# Notification action flow (sequence)

What happens when a user taps a **Snooze** or **Mark taken** action button on a dose-reminder
notification (Phase 8, ADR-0015). The actions are handled in the service worker and act on the
server via reminder-id-keyed endpoints; "Mark taken" records a dose per attached medication
and is atomic — any overdose/interaction guard blocks the whole take and the worker shows a
fail-safe "open the app" notification.

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant SW as Service worker (sw.ts)
    participant API as reminders router
    participant Doses as domain.doses.take_reminder
    participant DB as Postgres

    User->>SW: tap notification action
    alt action = "snooze"
        SW->>API: POST /reminders/{id}/snooze (cookie)
        API-->>SW: 200 (re-fires in 1h)
    else action = "take"
        SW->>API: POST /reminders/{id}/take (cookie)
        API->>Doses: take_reminder(reminder_id, now)
        Doses->>DB: load owned dose reminder + slot medications
        loop each attached medication
            Doses->>DB: create_dose (guards run BEFORE insert)
            alt a guard blocks (overdose 409 / interaction cooldown)
                Note over Doses,DB: raise — request transaction rolls back,<br/>nothing committed, never auto-acknowledged
                Doses-->>API: guard error propagates
                API-->>SW: 409 (app-wide handler, violation body)
                SW->>User: "Couldn't record — open the app"
            end
        end
        Doses->>DB: resolve slot reminder(s) → dismissed
        API-->>SW: 204
    else body tap (no action)
        SW->>User: open app at /reminders
    end
```
