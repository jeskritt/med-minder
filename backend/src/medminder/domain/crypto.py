"""Symmetric encryption for secrets stored at rest (Phase 10 hardening).

Used to encrypt Web Push subscription key material (``p256dh`` / ``auth``)
before it touches the database — see ADR-0020.  Fernet (AES-128-CBC +
HMAC-SHA256, URL-safe base64 tokens) is the primitive; the key is loaded
from ``Settings.push_encryption_key`` and is environment-only.

This module is pure (no DB, no FastAPI): the API layer encrypts on write,
the push sender decrypts immediately before handing the keys to pywebpush.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from medminder.settings import Settings

__all__ = ["InvalidToken", "build_fernet", "decrypt_secret", "encrypt_secret"]


def build_fernet(settings: Settings) -> Fernet:
    """Build the Fernet cipher from the configured key.

    Raises ``ValueError`` if the key is not a valid 32-byte url-safe base64
    Fernet key.  The dev fallback is a valid key so dev/test boot cleanly;
    non-dev environments must supply their own (enforced in ``Settings``).
    """
    return Fernet(settings.push_encryption_key.encode("utf-8"))


def encrypt_secret(fernet: Fernet, plaintext: str) -> str:
    """Encrypt ``plaintext`` to a URL-safe Fernet token (ASCII)."""
    return fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(fernet: Fernet, token: str) -> str:
    """Decrypt a Fernet ``token``.  Raises ``InvalidToken`` on mismatch.

    A legacy plaintext value (written before encryption was introduced) is
    not a valid Fernet token, so this raises ``InvalidToken`` — the caller
    treats that as a dead subscription and the browser re-subscribes.
    """
    return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
