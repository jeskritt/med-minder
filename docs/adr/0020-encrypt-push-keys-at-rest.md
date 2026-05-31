# ADR-0020 — Encrypt push subscription keys at rest

## Status

**Accepted** (Phase 10 — Hardening).

## Context

`push_subscriptions` stored the Web Push key material (`p256dh`, `auth`) as
plaintext. These are the cryptographic secrets a push message is encrypted
against; the Phase 10 review (G3) flagged at-rest exposure if the database were
compromised. The `endpoint` is a per-browser opaque URL and the table's lookup
key / unique constraint — not high-value secret material.

## Decision

Encrypt `p256dh` and `auth` at rest with **Fernet** (AES-128-CBC + HMAC,
versioned URL-safe base64), keyed from a new env-only `PUSH_ENCRYPTION_KEY`.

- Pure crypto lives in `domain/crypto.py` (`build_fernet` / `encrypt_secret` /
  `decrypt_secret`); the API layer **encrypts on write** (`api/push.py`) and the
  push sender **decrypts immediately before pywebpush** (`domain/push.py`).
- **`endpoint` stays plaintext**: Fernet's random IV is non-deterministic, which
  would break the `WHERE endpoint = ...` lookup and the `(user_id, endpoint)`
  unique constraint. The crypto secrets are `p256dh`/`auth`, which are encrypted.
- The key is **environment-only** and enforced by the existing settings
  `model_validator` — the app refuses to boot outside development with the dev
  fallback key (mirroring `SESSION_SECRET`).
- **No migration / no backfill — re-subscribe over backfill.** Legacy plaintext
  rows are not valid Fernet tokens, so `decrypt_secret` raises `InvalidToken`;
  `send_web_push` treats that as `gone=True`, the row is deleted on the existing
  cleanup path, and the browser re-subscribes with fresh encrypted keys. The
  column type is unchanged (`Text`), so there is no schema migration.
- `cryptography` (already transitive via pywebpush, and `py.typed`) is now
  **pinned explicitly** in `pyproject.toml`.

## Consequences

- **Positive**: push secrets are no longer readable from a DB dump; clean
  domain/API split; fully typed; no schema change.
- **Negative / accepted**: **rotating `PUSH_ENCRYPTION_KEY` orphans all
  subscriptions** — they become undecryptable, are deleted as `gone`, and
  self-heal on the user's next app open. Acceptable for a single-tenant app with
  a handful of devices. Encrypt/decrypt runs on the push hot path, but volume is
  negligible.
