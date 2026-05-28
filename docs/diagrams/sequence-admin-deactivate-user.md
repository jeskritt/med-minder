# Sequence — admin deactivates a user (`DELETE /api/v1/users/{id}`)

How an admin deactivates another user in-app: the `require_admin` gate authorizes
the caller, the domain resolves the target by id, applies the self / last-admin
guards, soft-deletes the row and **revokes all of the target's sessions**, and
appends one audit row — all in the same request transaction (ADR-0014 / feature
009).

```mermaid
sequenceDiagram
    actor A as Admin
    participant FE as DeactivateUserModal
    participant API as DELETE /api/v1/users/{id}
    participant Dom as domain.admin_deactivate_user
    participant DB as Postgres (users, sessions, admin_audit_log)

    A->>FE: click Deactivate → confirm (in-app modal, not native confirm())
    FE->>API: DELETE /api/v1/users/{id} (mm_session cookie)
    API->>API: require_admin → 401 if anon, 403 if non-admin
    API->>Dom: admin_deactivate_user(actor, user_id)
    Dom->>DB: get_user_by_id(id)
    alt no active user
        Dom-->>API: UserNotFoundError
        API-->>FE: 404
    else target is the actor
        Dom-->>API: SelfActionError
        API-->>FE: 403 "cannot deactivate your own account"
    else target is the last active admin
        Dom->>DB: count_active_admins() FOR UPDATE
        Dom-->>API: LastAdminError
        API-->>FE: 409 (concurrency-safe via the row lock)
    else success
        Dom->>DB: soft_delete_user → set deleted_at
        Dom->>DB: revoke_all_user_sessions(target)
        Dom->>DB: record_admin_action(action=deactivate, details={})
        API-->>FE: 204
        FE-->>A: row disappears from the list
        Note over DB: target's cookies now map to no active row → 401 on next request
    end
```
