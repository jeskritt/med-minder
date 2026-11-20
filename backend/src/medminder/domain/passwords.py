"""Argon2id password hashing.

This module is the single source of truth for password hashing
parameters — the CLI calls these helpers, and the future Phase 2 auth
middleware will reuse them verbatim.

The hash + verify functions never log raw passwords or hashes.
Callers are expected to do the same.
"""

from __future__ import annotations

import asyncio
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# argon2-cffi defaults are mission-conformant — see ADR/Phase 1
# requirements.  Centralizing them here means Phase 2 auth doesn't
# accidentally drift from CLI-issued hashes.
_HASHER: PasswordHasher = PasswordHasher()

MIN_PASSWORD_LENGTH: int = 12


def hash_password(plain: str) -> str:
    """Hash ``plain`` with Argon2id; return the encoded hash string."""
    return _HASHER.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    """Constant-time verify.  Returns ``False`` on mismatch — never raises."""
    try:
        return _HASHER.verify(stored_hash, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # An unrelated argon2 error (corrupt hash, unsupported variant)
        # is treated as a verification failure — the alternative is to
        # leak failure modes to attackers.
        return False


async def hash_password_async(plain: str) -> str:
    """Offload Argon2id hashing to a worker thread to keep the loop responsive."""
    return await asyncio.to_thread(hash_password, plain)


async def verify_password_async(stored_hash: str, plain: str) -> bool:
    """Offload Argon2id verification to a worker thread to keep the loop responsive."""
    return await asyncio.to_thread(verify_password, stored_hash, plain)


def password_too_short(plain: str) -> bool:
    return len(plain) < MIN_PASSWORD_LENGTH


# token_urlsafe(n) yields ceil(n*8/6) chars; 16 bytes → ~22 chars, well over
# the 12-char minimum and ≥ 128 bits of entropy from a CSPRNG.
_TEMP_PASSWORD_NBYTES: int = 16


def generate_temp_password() -> str:
    """Mint a one-time temporary password.

    Uses the stdlib CSPRNG (``secrets``); the result comfortably clears
    ``MIN_PASSWORD_LENGTH`` and carries ≥ 128 bits of entropy. Callers show it
    to the admin exactly once and never persist or log the plaintext (FR-004).
    """
    return secrets.token_urlsafe(_TEMP_PASSWORD_NBYTES)
