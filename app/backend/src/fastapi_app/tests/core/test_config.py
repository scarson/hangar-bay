# ABOUTME: Guards the consolidated Settings — resolved .env path, SSO defaults, extra=ignore.
# ABOUTME: Also pins the get_settings() singleton and unknown-dotenv-key tolerance (D-DELTA-3).
from pathlib import Path

from pydantic import SecretStr

from fastapi_app.core.config import Settings, get_settings, settings


def test_env_file_path_resolves_to_backend_src_env():
    env_file = Settings.model_config["env_file"]
    # core/config.py lives at .../src/fastapi_app/core/config.py; parents[2] == .../src
    assert Path(env_file).is_absolute()
    assert str(env_file).replace("\\", "/").endswith("app/backend/src/.env")


def test_extra_env_keys_are_ignored_config():
    # Config-level guard; the behavioral dotenv test below proves it end-to-end.
    assert Settings.model_config.get("extra") == "ignore"


def test_unknown_env_file_key_does_not_crash(tmp_path, monkeypatch):
    # D-DELTA-3: unknown keys in the .env FILE abort construction unless extra="ignore"
    # (unknown OS-env vars are ignored either way — the trap is dotenv-specific).
    # OS env takes PRECEDENCE over dotenv in pydantic-settings, and CI exports
    # ESI_USER_AGENT/DATABASE_URL/CACHE_URL — clear them so the temp .env wins.
    for var in ("ESI_USER_AGENT", "DATABASE_URL", "CACHE_URL", "AGGREGATION_REGION_IDS"):
        monkeypatch.delenv(var, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SOME_FUTURE_KEY=1\n"
        "DATABASE_URL=postgresql+asyncpg://u:p@localhost/x\n"
        "CACHE_URL=redis://localhost:6379/9\n"
        "ESI_USER_AGENT=test\n"
    )
    s = Settings(_env_file=env_file)
    assert s.ESI_USER_AGENT == "test"


def test_sso_fields_have_safe_defaults(monkeypatch):
    # Assert CLASS defaults on an isolated instance — NOT the ambient singleton, which
    # reads the real app/backend/src/.env (which may hold real credentials on a dev
    # machine) and CI's exported TOKEN_CIPHER_KEYS. Clear every SSO/session
    # env var first so OS-env values can't leak into the isolated instance.
    for var in (
        "ESI_CLIENT_ID", "ESI_CLIENT_SECRET", "ESI_SSO_AUTHORIZE_URL", "ESI_SSO_TOKEN_URL",
        "ESI_SSO_JWKS_URI", "ESI_SSO_CALLBACK_URL", "FRONTEND_ORIGIN", "SESSION_COOKIE_NAME",
        "SESSION_IDLE_TTL_SECONDS", "SESSION_ABSOLUTE_TTL_SECONDS", "TOKEN_CIPHER_KEYS",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/x",
        CACHE_URL="redis://localhost:6379/9",
        ESI_USER_AGENT="test",
    )
    assert s.ESI_CLIENT_ID == ""
    assert isinstance(s.ESI_CLIENT_SECRET, SecretStr)
    assert s.ESI_CLIENT_SECRET.get_secret_value() == ""
    assert isinstance(s.TOKEN_CIPHER_KEYS, SecretStr)
    assert s.TOKEN_CIPHER_KEYS.get_secret_value() == ""
    assert s.ESI_SSO_AUTHORIZE_URL == "https://login.eveonline.com/v2/oauth/authorize"
    assert s.ESI_SSO_TOKEN_URL == "https://login.eveonline.com/v2/oauth/token"
    assert s.ESI_SSO_JWKS_URI == "https://login.eveonline.com/oauth/jwks"
    # Registered EVE callback, char-for-char: dev rides the Vite proxy over HTTPS (D-DELTA-1).
    assert s.ESI_SSO_CALLBACK_URL == "https://localhost:5173/api/v1/auth/sso/callback"
    assert s.FRONTEND_ORIGIN == "https://localhost:5173"
    assert s.SESSION_COOKIE_NAME == "hb_session"
    assert s.SESSION_IDLE_TTL_SECONDS == 604_800
    assert s.SESSION_ABSOLUTE_TTL_SECONDS == 2_592_000


def test_reconciled_non_sso_defaults(monkeypatch):
    # Isolated instance, same pattern as the SSO-defaults test. 3600 pins the
    # scheduler-interval default the consolidation chose (over the 900 alternative).
    for var in (
        "AGGREGATION_SCHEDULER_INTERVAL_SECONDS", "ESI_TIMEOUT", "AGGREGATION_REGION_IDS",
        "AGGREGATION_DEV_CONTRACT_LIMIT", "ENVIRONMENT", "LOG_LEVEL", "ESI_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/x",
        CACHE_URL="redis://localhost:6379/9",
        ESI_USER_AGENT="test",
    )
    assert s.AGGREGATION_SCHEDULER_INTERVAL_SECONDS == 3600
    assert s.ESI_TIMEOUT == 20.0
    assert s.AGGREGATION_REGION_IDS == [10000002]
    assert s.AGGREGATION_DEV_CONTRACT_LIMIT == 100
    assert s.ENVIRONMENT == "development"


def test_region_ids_validator_direct_construction_forms(monkeypatch):
    # Constructor kwargs hit the mode="before" validator directly (no dotenv JSON
    # pre-decode), so all three input forms are exercised here.
    monkeypatch.delenv("AGGREGATION_REGION_IDS", raising=False)
    base = dict(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/x",
        CACHE_URL="redis://localhost:6379/9",
        ESI_USER_AGENT="test",
    )
    s = Settings(**base, AGGREGATION_REGION_IDS="10000002, 10000043")
    assert s.AGGREGATION_REGION_IDS == [10000002, 10000043]
    s = Settings(**base, AGGREGATION_REGION_IDS=[10000002, "10000043"])
    assert s.AGGREGATION_REGION_IDS == [10000002, 10000043]
    s = Settings(**base, AGGREGATION_REGION_IDS="[10000002]")
    assert s.AGGREGATION_REGION_IDS == [10000002]


def test_get_settings_returns_the_singleton():
    assert get_settings() is settings


def test_single_base_registry_shared_by_models():
    from fastapi_app.db import Base
    from fastapi_app.models.contracts import Contract
    assert Contract.__table__.metadata is Base.metadata
    assert "contracts" in Base.metadata.tables
