"""Generate a VAPID key pair for MedMinder Web Push (Phase 7).

Cross-platform script (Python) — see specs/tech-stack.md §Scripts.

Usage:
    python scripts/generate_vapid_keys.py

Prints, in env-var form, a freshly generated P-256 key pair:

    VAPID_PUBLIC_KEY=<url-safe base64, raw uncompressed point>   # browser applicationServerKey
    VAPID_PRIVATE_KEY=<url-safe base64, raw 32-byte private key> # SECRET — server only
    VAPID_SUBJECT=mailto:you@example.com                          # edit to a real contact

The raw URL-safe-base64 representation matches what the browser's
``PushManager.subscribe({ applicationServerKey })`` expects (public) and
what ``pywebpush`` accepts for ``vapid_private_key`` (private).  Paste the
values into the backend env / secret store.  Treat the private key like any
other secret: never commit it, never log it.
"""

from __future__ import annotations

import base64
import sys


def _b64url(raw: bytes) -> str:
    """URL-safe base64 without padding (the Web Push wire format)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )
    except ImportError:
        sys.stderr.write(
            "cryptography is required (installed transitively via pywebpush).\n"
            "Install backend deps first: pip install -e backend[dev]\n"
        )
        return 1

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # Private: the raw 32-byte scalar (what pywebpush/py_vapid accept as a
    # url-safe-base64 "raw" private key).
    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")
    # Public: the 65-byte uncompressed EC point (0x04 || X || Y) — the
    # browser applicationServerKey and the key the backend serves.
    public_raw = public_key.public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )

    print(f"VAPID_PUBLIC_KEY={_b64url(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(private_raw)}")
    print("VAPID_SUBJECT=mailto:you@example.com")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
