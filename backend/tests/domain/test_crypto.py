"""Symmetric secret encryption (ADR-0020)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from medminder.domain.crypto import (
    InvalidToken,
    build_fernet,
    decrypt_secret,
    encrypt_secret,
)
from medminder.settings import Settings


def _settings(key: str | None = None) -> Settings:
    kwargs: dict[str, str] = {"env": "development"}
    if key is not None:
        kwargs["push_encryption_key"] = key
    return Settings(**kwargs)


def test_round_trip() -> None:
    fernet = build_fernet(_settings())
    token = encrypt_secret(fernet, "BPpubkey")
    assert token != "BPpubkey"
    assert decrypt_secret(fernet, token) == "BPpubkey"


def test_ciphertext_is_non_deterministic() -> None:
    fernet = build_fernet(_settings())
    assert encrypt_secret(fernet, "same") != encrypt_secret(fernet, "same")


def test_wrong_key_raises_invalid_token() -> None:
    enc = build_fernet(_settings())
    token = encrypt_secret(enc, "secret")
    other = build_fernet(_settings(key=Fernet.generate_key().decode()))
    with pytest.raises(InvalidToken):
        decrypt_secret(other, token)


def test_legacy_plaintext_is_invalid_token() -> None:
    """A pre-encryption plaintext value is not a valid Fernet token."""
    fernet = build_fernet(_settings())
    with pytest.raises(InvalidToken):
        decrypt_secret(fernet, "BPpubkey")
