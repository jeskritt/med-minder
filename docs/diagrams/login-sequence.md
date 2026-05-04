# Login Sequence

This diagram details the primary authentication lifecycle (FR-015, SC-007).

```mermaid
sequenceDiagram
    participant Browser
    participant API
    participant Database

    Note over Browser,Database: 1. Successful Login
    Browser->>API: POST /auth/login {email, password}
    API->>Database: SELECT user BY email (including soft-deleted)
    Database-->>API: User Record
    API->>API: Verify Password (Argon2id)
    API->>Database: Delete existing session matching old cookie (if any)
    API->>Database: INSERT sessions (user_id, expires_at=now+30d) returning token
    API->>API: Sign plaintext token (itsdangerous)
    API-->>Browser: 204 No Content + Set-Cookie: mm_session=signed_token; HttpOnly; SameSite=Lax

    Note over Browser,Database: 2. Authenticated Request
    Browser->>API: GET /me (Cookie: mm_session=signed_token)
    API->>API: Verify signature (itsdangerous)
    API->>Database: SELECT sessions WHERE token_hash = hash(token)
    Database-->>API: Session Record
    API->>API: Check expires_at > now
    API->>Database: UPDATE sessions SET expires_at=now+30d (rolling expiry)
    API->>API: Sign token again
    API-->>Browser: 200 OK {user data} + Set-Cookie: mm_session=signed_token (Max-Age refreshed)

    Note over Browser,Database: 3. Logout
    Browser->>API: POST /auth/logout (Cookie: mm_session=signed_token)
    API->>API: Verify signature (best effort)
    API->>Database: DELETE FROM sessions WHERE token_hash = hash(token)
    API-->>Browser: 204 No Content + Set-Cookie: mm_session=; Max-Age=0
```
