# Sequence — self-service password change (`POST /me/password`)

How a signed-in user changes their own password: the current password is verified,
the new hash is stored, **all** of the user's sessions are revoked, and a fresh
session is issued for the current device so it stays signed in while other devices
are logged out (ADR-0011 / feature 007).

```mermaid
sequenceDiagram
    actor U as User (this device)
    participant FE as ProfileDialog
    participant API as POST /me/password
    participant Dom as domain.change_own_password
    participant DB as Postgres (users, sessions)

    U->>FE: enter current + new password
    FE->>API: POST /me/password {current, new} (mm_session cookie)
    API->>API: get_current_user → authenticated user
    API->>Dom: change_own_password(user, current, new)
    alt current password wrong
        Dom-->>API: IncorrectPasswordError
        API-->>FE: 403 "Current password is incorrect."
        FE-->>U: error on current-password field
    else new password < 12 chars
        Dom-->>API: PasswordTooShortError
        API-->>FE: 422
        FE-->>U: error on new-password field
    else success
        Dom->>DB: verify_password ok → set password_hash
        Dom->>DB: revoke_all_user_sessions(user)  %% kills every session incl. this one
        API->>DB: create_session(user) → new token
        API-->>FE: 204 + Set-Cookie mm_session=<fresh token>
        FE-->>U: "Password changed. Other devices signed out."
        Note over DB: other devices' cookies now map to no row → 401 on next request
    end
```
