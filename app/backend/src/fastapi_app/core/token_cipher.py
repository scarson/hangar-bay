# ABOUTME: Lazy Fernet/MultiFernet token encryption built from TOKEN_CIPHER_KEYS.
# ABOUTME: Empty/whitespace-only key config surfaces as not-configured, never a boot crash (m2-eve-sso design spec §3.4).
from typing import List

from cryptography.fernet import Fernet, MultiFernet

from .config import get_settings


def parse_cipher_keys(raw: str) -> List[str]:
    """Split on comma, strip each element, drop empties. Whitespace-only ⇒ []."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def is_token_cipher_configured() -> bool:
    raw = get_settings().TOKEN_CIPHER_KEYS.get_secret_value()
    return bool(parse_cipher_keys(raw))


def _build_cipher() -> MultiFernet:
    # Rebuilt per call: construction is cheap, encrypt/decrypt run only at
    # login/refresh frequency, and keys may rotate between calls — do not memoize.
    keys = parse_cipher_keys(get_settings().TOKEN_CIPHER_KEYS.get_secret_value())
    if not keys:
        raise RuntimeError("TOKEN_CIPHER_KEYS is not configured")
    return MultiFernet([Fernet(k) for k in keys])


def encrypt_token(plaintext: str) -> str:
    return _build_cipher().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _build_cipher().decrypt(ciphertext.encode()).decode()
