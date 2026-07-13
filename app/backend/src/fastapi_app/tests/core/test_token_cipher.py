# ABOUTME: Fernet/MultiFernet parse + round-trip + rotation + not-configured behavior.
# ABOUTME: Wrong-key decrypt raises InvalidToken — the re-auth trigger — never a silent success.
import pytest
from cryptography.fernet import Fernet, InvalidToken

from fastapi_app.core import token_cipher as tc


def test_parse_keys_rules():
    assert tc.parse_cipher_keys("") == []
    assert tc.parse_cipher_keys("   \n ") == []          # whitespace-only ⇒ not configured
    assert tc.parse_cipher_keys("k1\n") == ["k1"]        # stray trailing newline stripped
    assert tc.parse_cipher_keys("k1, k2 ,k3") == ["k1", "k2", "k3"]
    assert tc.parse_cipher_keys("k1,,k2") == ["k1", "k2"]  # empty elements dropped


def test_not_configured_when_empty(monkeypatch):
    from fastapi_app.core.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr("  \n "))
    assert tc.is_token_cipher_configured() is False
    with pytest.raises(RuntimeError):
        tc.encrypt_token("hello")   # lazy build raises, never a boot crash


def test_round_trip_with_configured_key(monkeypatch):
    from fastapi_app.core.config import settings
    from pydantic import SecretStr
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(key))
    assert tc.is_token_cipher_configured() is True
    ct = tc.encrypt_token("refresh-token-abc")
    assert ct != "refresh-token-abc"          # ciphertext != plaintext
    assert tc.decrypt_token(ct) == "refresh-token-abc"


def test_multifernet_rotation_decrypts_old_ciphertext(monkeypatch):
    from fastapi_app.core.config import settings
    from pydantic import SecretStr
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(old))
    ct_old = tc.encrypt_token("token")
    # rotate: new primary first, old kept for decrypt
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(f"{new}, {old}"))
    assert tc.decrypt_token(ct_old) == "token"          # still decryptable
    ct_new = tc.encrypt_token("token")
    # Mechanism assertion: the NEW primary produced ct_new. (ct_new != ct_old would be
    # vacuous — Fernet embeds a random IV, so any two encryptions differ regardless.)
    assert Fernet(new).decrypt(ct_new.encode()) == b"token"
    with pytest.raises(InvalidToken):
        Fernet(old).decrypt(ct_new.encode())


def test_wrong_key_decrypt_raises_invalid_token(monkeypatch):
    from fastapi_app.core.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(Fernet.generate_key().decode()))
    ct = tc.encrypt_token("token")
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(Fernet.generate_key().decode()))
    with pytest.raises(InvalidToken):
        tc.decrypt_token(ct)


def test_malformed_key_is_configured_but_fails_loudly(monkeypatch):
    from fastapi_app.core.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr("not-a-valid-fernet-key"))
    assert tc.is_token_cipher_configured() is True   # non-empty config counts as configured
    with pytest.raises(ValueError) as exc:
        tc.encrypt_token("x")
    assert "not-a-valid-fernet-key" not in str(exc.value)   # no key material in the error
