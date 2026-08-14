"""Symmetric encryption for sensitive bank account numbers.

The full account number is encrypted at rest with AES-256-GCM (the key is
derived from :setting:`SECRET_KEY` — or the dedicated
``BANK_ENCRYPTION_KEY`` when present). Only the last 4 digits are stored
plaintext (for masked display); the raw number is never returned by any API.
Online-banking passwords, PINs and credentials are never stored at all.
"""
import base64
import os
import re

from django.conf import settings

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - fails closed in odd environments
    _HAS_CRYPTO = False


def _derive_key() -> bytes:
    secret = getattr(settings, "BANK_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    import hashlib

    return hashlib.sha256(str(secret).encode()).digest()


def encrypt_account_number(value: str) -> str:
    """Encrypt a bank account number → ``base64(nonce ‖ ciphertext)``."""
    if not _HAS_CRYPTO:  # pragma: no cover
        raise RuntimeError("cryptography is required to store bank accounts.")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key()).encrypt(nonce, value.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_account_number(stored: str) -> str:
    """Decrypt a bank account number previously written by :func:`encrypt_account_number`."""
    raw = base64.b64decode(stored)
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(_derive_key()).decrypt(nonce, ciphertext, None).decode()


def mask_account_number(value: str) -> str:
    """Human-friendly masked form: ``••••1234`` (only last 4 digits visible)."""
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if len(digits) <= 4:
        return "•" * len(digits) + digits
    return "•" * (len(digits) - 4) + digits[-4:]


def normalize_account_number(value: str) -> str:
    """Strip spaces/dashes and validate the result is digit-only 6–18 chars."""
    digits = re.sub(r"[\s-]", "", str(value or ""))
    if not digits or not digits.isdigit():
        raise ValueError("Account number must contain digits only.")
    if not 6 <= len(digits) <= 18:
        raise ValueError("Account number must be between 6 and 18 digits.")
    return digits