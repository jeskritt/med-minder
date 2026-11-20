"""Unit tests for PostgreSQL TLS configuration helpers in ``medminder.db``."""

from __future__ import annotations

import datetime as dt
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from medminder.db import make_async_ssl_arg, make_sync_connect_args
from medminder.settings import Settings


def _write_dummy_ca_pem(path: Path) -> str:
    """Generate a throwaway self-signed CA PEM file for SSLContext tests."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MedMinder Test CA")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(path)


def test_make_async_ssl_arg_unset() -> None:
    s = Settings(database_ssl_mode=None)
    assert make_async_ssl_arg(s) is None


def test_make_async_ssl_arg_passthrough_modes() -> None:
    for mode in ("disable", "allow", "prefer", "require"):
        s = Settings(database_ssl_mode=mode)  # type: ignore[arg-type]
        assert make_async_ssl_arg(s) == mode


def test_make_async_ssl_arg_verify_modes_with_system_ca() -> None:
    ctx_full = make_async_ssl_arg(Settings(database_ssl_mode="verify-full"))
    assert isinstance(ctx_full, ssl.SSLContext)
    assert ctx_full.verify_mode == ssl.CERT_REQUIRED
    assert ctx_full.check_hostname is True

    ctx_ca = make_async_ssl_arg(Settings(database_ssl_mode="verify-ca"))
    assert isinstance(ctx_ca, ssl.SSLContext)
    assert ctx_ca.verify_mode == ssl.CERT_REQUIRED
    assert ctx_ca.check_hostname is False


def test_make_async_ssl_arg_verify_full_with_ca_file(tmp_path: Path) -> None:
    ca_path = _write_dummy_ca_pem(tmp_path / "ca.pem")
    ctx = make_async_ssl_arg(
        Settings(database_ssl_mode="verify-full", database_ssl_ca_file=ca_path)
    )
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert ctx.cert_store_stats()["x509_ca"] >= 1


def test_make_sync_connect_args_modes() -> None:
    assert make_sync_connect_args(Settings(database_ssl_mode=None)) == {}
    assert make_sync_connect_args(Settings(database_ssl_mode="require")) == {
        "sslmode": "require"
    }
    assert make_sync_connect_args(Settings(database_ssl_mode="verify-full")) == {
        "sslmode": "verify-full",
        "sslrootcert": "system",
    }
    assert make_sync_connect_args(
        Settings(
            database_ssl_mode="verify-full",
            database_ssl_ca_file="/etc/secrets/supabase-ca.crt",
        )
    ) == {
        "sslmode": "verify-full",
        "sslrootcert": "/etc/secrets/supabase-ca.crt",
    }
