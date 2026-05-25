# Reminder dispatch flow (sequence)

What the in-process APScheduler "dispatch tick" does each interval (Phase 7,
ADR-0002). Durable state is the `reminders` table; the scheduler only holds
the recurring tick in memory.

```mermaid
sequenceDiagram
    autonumber
    participant Tick as Dispatch tick (AsyncIOScheduler)
    participant DB as reminders table (Postgres)
    participant QH as quiet-hours math (pure)
    participant Push as Web Push (pywebpush)
    participant Dev as Device(s)

    Tick->>DB: generate_due_dose_reminders<br/>(idempotent, 48h horizon)
    Tick->>DB: select pending where scheduled_for <= now

    loop each due reminder
        alt older than grace window
            Note over Tick,DB: overdue — leave pending,<br/>do not push (shown in-app)
        else within grace
            Tick->>QH: defer_for_quiet_hours(fire, tz, window)?
            alt inside quiet hours
                QH-->>Tick: window-end instant
                Tick->>DB: reschedule scheduled_for (stays pending)
            else deliver
                Tick->>DB: load user's push subscriptions
                loop each subscription
                    Tick->>Push: send (VAPID-signed),<br/>retry transient up to max
                    Push->>Dev: notification
                    alt gone (HTTP 404/410)
                        Tick->>DB: delete subscription
                    end
                end
                Tick->>DB: mark reminder sent
            end
        end
    end
```
