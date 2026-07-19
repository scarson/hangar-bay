# ABOUTME: create_db_tables() must be a no-op outside development (prod-safety rider).
# ABOUTME: Environment-gated main-module startup behavior, driven via module-global monkeypatching.
import logging
from types import SimpleNamespace

import pytest

from fastapi_app import main as main_mod


@pytest.mark.asyncio
async def test_create_db_tables_skips_outside_development(monkeypatch, caplog):
    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", "production")
    called = {"drop_or_create": False}

    class _Boom:
        async def __aenter__(self):
            called["drop_or_create"] = True
            raise AssertionError("engine.begin() must not run in production")

        async def __aexit__(self, *a):
            return False

    # AsyncEngine forbids instance-attribute assignment ('begin' is read-only under
    # SQLAlchemy 2.0.41), so swap the MODULE-GLOBAL binding create_db_tables() reads.
    monkeypatch.setattr(main_mod, "async_engine", SimpleNamespace(begin=lambda: _Boom()))
    with caplog.at_level(logging.INFO):
        await main_mod.create_db_tables()
    assert called["drop_or_create"] is False
    assert "Skipping" in caplog.text


@pytest.mark.parametrize("recreate_flag", [False, True])
@pytest.mark.asyncio
async def test_create_db_tables_skips_when_environment_unset(monkeypatch, recreate_flag):
    # P1 (fully closed): when ENVIRONMENT is simply omitted, a fresh Settings must
    # NOT resolve to "development" — otherwise DB_RECREATE_ON_STARTUP=true (easily
    # inherited/copied into a prod env that omits ENVIRONMENT) satisfies BOTH gate
    # conditions and drops every table. Secure-by-default: unset ENVIRONMENT is
    # "production", so the destructive recreate never runs regardless of the flag.
    # Parametrized over the flag so the flag=True case (the missed one) is pinned.
    from fastapi_app.core.config import Settings

    fresh_settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/x",
        CACHE_URL="redis://localhost:6379/9",
        ESI_USER_AGENT="test",
        DB_RECREATE_ON_STARTUP=recreate_flag,
    )
    assert fresh_settings.ENVIRONMENT == "production"  # secure-by-default, never dev when unset
    monkeypatch.setattr(main_mod, "settings", fresh_settings)

    called = {"drop_or_create": False}

    class _Boom:
        async def __aenter__(self):
            called["drop_or_create"] = True
            raise AssertionError("engine.begin() must not run with an unset ENVIRONMENT")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(main_mod, "async_engine", SimpleNamespace(begin=lambda: _Boom()))
    await main_mod.create_db_tables()
    assert called["drop_or_create"] is False


@pytest.mark.asyncio
async def test_create_db_tables_skips_in_development_without_explicit_flag(monkeypatch):
    # Pins the "AND", not "OR": ENVIRONMENT=="development" alone (however it got set)
    # must not be enough — DB_RECREATE_ON_STARTUP defaults False and must be flipped
    # on independently, or the two-gate design collapses back to the single-gate bug.
    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(main_mod.settings, "DB_RECREATE_ON_STARTUP", False)
    called = {"drop_or_create": False}

    class _Boom:
        async def __aenter__(self):
            called["drop_or_create"] = True
            raise AssertionError("engine.begin() must not run without the explicit recreate flag")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(main_mod, "async_engine", SimpleNamespace(begin=lambda: _Boom()))
    await main_mod.create_db_tables()
    assert called["drop_or_create"] is False


@pytest.mark.asyncio
async def test_create_db_tables_runs_in_development(monkeypatch):
    # Mirror direction (testing-pitfalls §6 Boundary): development must still reach
    # engine.begin()/drop_all/create_all — a gate that no-ops everywhere would pass
    # the skip test above while silently killing dev table creation (ENV-2).
    from fastapi_app.db import Base

    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(main_mod.settings, "DB_RECREATE_ON_STARTUP", True)
    synced = []

    async def _record(fn):
        synced.append(fn)

    entered = {"value": False}

    class _RecordingBegin:
        async def __aenter__(self):
            entered["value"] = True
            return SimpleNamespace(run_sync=_record)

        async def __aexit__(self, *args):
            return False

    # Module-global swap, not engine-attribute assignment (read-only — see above).
    monkeypatch.setattr(main_mod, "async_engine", SimpleNamespace(begin=lambda: _RecordingBegin()))
    await main_mod.create_db_tables()
    assert entered["value"] is True
    assert synced == [Base.metadata.drop_all, Base.metadata.create_all]


# --- validate_sso_configuration (M4 Task 3.7, spec §6 two-tier diagnostic) ---
# Tier (a): the trio {ESI_CLIENT_ID, ESI_CLIENT_SECRET, TOKEN_CIPHER_KEYS} wholly empty
# → warn in EVERY environment and continue (anonymous marketplace stays valid).
# Tier (b), production only: ANY non-empty proper subset of the trio, or any of the trio
# set while a localhost URL remains → RuntimeError naming the offending fields.
# Outside production a partial trio warns; localhost URLs are the CORRECT dev config
# and stay silent there (plan Deviation D-10).

_REAL_CALLBACK = "https://hangarbay.example/api/v1/auth/sso/callback"
_REAL_ORIGIN = "https://hangarbay.example"


def _set_sso(monkeypatch, *, env, cid="", secret="", keys="",
             callback=_REAL_CALLBACK, origin=_REAL_ORIGIN):
    from pydantic import SecretStr

    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", env)
    monkeypatch.setattr(main_mod.settings, "ESI_CLIENT_ID", cid)
    monkeypatch.setattr(main_mod.settings, "ESI_CLIENT_SECRET", SecretStr(secret))
    monkeypatch.setattr(main_mod.settings, "TOKEN_CIPHER_KEYS", SecretStr(keys))
    monkeypatch.setattr(main_mod.settings, "ESI_SSO_CALLBACK_URL", callback)
    monkeypatch.setattr(main_mod.settings, "FRONTEND_ORIGIN", origin)


@pytest.mark.parametrize("env", ["development", "production", "test"])
def test_sso_wholly_unconfigured_warns_and_boots(monkeypatch, caplog, env):
    _set_sso(monkeypatch, env=env)
    with caplog.at_level(logging.WARNING):
        main_mod.validate_sso_configuration()   # must not raise in ANY environment
    warnings = [r for r in caplog.records if "EVE SSO is not configured" in r.getMessage()]
    assert len(warnings) == 1


def test_sso_wholly_unconfigured_warning_names_only_login_and_callback(monkeypatch, caplog):
    # Logout stays operational (204, not guarded) — the message must name the two
    # affected routes, never the whole /auth/sso/* family.
    _set_sso(monkeypatch, env="development")
    with caplog.at_level(logging.WARNING):
        main_mod.validate_sso_configuration()
    messages = [r.getMessage() for r in caplog.records if "EVE SSO is not configured" in r.getMessage()]
    assert len(messages) == 1
    assert "/auth/sso/login" in messages[0]
    assert "/auth/sso/callback" in messages[0]
    assert "/auth/sso/*" not in messages[0]
    assert "/auth/sso/logout" not in messages[0]


# Every non-empty proper subset of the trio — a leftover credential with no client id
# is as much a deploy mistake as the reverse.
_PARTIAL_SUBSETS = [
    dict(cid="cid"),
    dict(secret="sec"),
    dict(keys="key"),
    dict(cid="cid", secret="sec"),
    dict(cid="cid", keys="key"),
    dict(secret="sec", keys="key"),
]


@pytest.mark.parametrize("subset", _PARTIAL_SUBSETS)
def test_sso_partial_config_fails_startup_in_production(monkeypatch, subset):
    _set_sso(monkeypatch, env="production", **subset)
    with pytest.raises(RuntimeError) as excinfo:
        main_mod.validate_sso_configuration()
    message = str(excinfo.value)
    empty_fields = {"ESI_CLIENT_ID", "ESI_CLIENT_SECRET", "TOKEN_CIPHER_KEYS"} - {
        {"cid": "ESI_CLIENT_ID", "secret": "ESI_CLIENT_SECRET", "keys": "TOKEN_CIPHER_KEYS"}[k]
        for k in subset
    }
    for field in empty_fields:
        assert field in message


@pytest.mark.parametrize(
    "url_kwargs,named_field",
    [
        (dict(callback="https://localhost:5173/api/v1/auth/sso/callback"), "ESI_SSO_CALLBACK_URL"),
        (dict(origin="https://localhost:5173"), "FRONTEND_ORIGIN"),
    ],
)
def test_sso_localhost_urls_fail_startup_in_production(monkeypatch, url_kwargs, named_field):
    _set_sso(monkeypatch, env="production", cid="cid", secret="sec", keys="key", **url_kwargs)
    with pytest.raises(RuntimeError) as excinfo:
        main_mod.validate_sso_configuration()
    assert named_field in str(excinfo.value)


@pytest.mark.parametrize("env", ["development", "test"])
def test_sso_partial_config_only_warns_outside_production(monkeypatch, caplog, env):
    _set_sso(monkeypatch, env=env, cid="cid")
    with caplog.at_level(logging.WARNING):
        main_mod.validate_sso_configuration()   # must not raise
    assert any("SSO misconfiguration" in r.getMessage() for r in caplog.records)


def test_sso_fully_configured_production_is_silent(monkeypatch, caplog):
    _set_sso(monkeypatch, env="production", cid="cid", secret="sec", keys="key")
    with caplog.at_level(logging.WARNING):
        main_mod.validate_sso_configuration()
    assert not caplog.records


def test_sso_dev_localhost_urls_are_silent_when_fully_configured(monkeypatch, caplog):
    # localhost URLs ARE the correct dev configuration (registered dev callback) —
    # a configured dev boot must not warn (D-10).
    _set_sso(
        monkeypatch, env="development", cid="cid", secret="sec", keys="key",
        callback="https://localhost:5173/api/v1/auth/sso/callback",
        origin="https://localhost:5173",
    )
    with caplog.at_level(logging.WARNING):
        main_mod.validate_sso_configuration()
    assert not caplog.records


@pytest.mark.asyncio
async def test_lifespan_invokes_sso_validation(monkeypatch):
    # The rename must not orphan the startup call site: a production+partial config
    # must abort the lifespan itself, with every external initializer patched out.
    _set_sso(monkeypatch, env="production", cid="cid")

    async def _noop_async(*a, **k):
        return None

    def _noop(*a, **k):
        return None

    monkeypatch.setattr(main_mod, "create_db_tables", _noop_async)
    monkeypatch.setattr(main_mod, "init_http_client", _noop)
    monkeypatch.setattr(main_mod, "init_cache", _noop_async)
    monkeypatch.setattr(main_mod, "create_scheduler", _noop)
    with pytest.raises(RuntimeError):
        async with main_mod.app.router.lifespan_context(main_mod.app):
            pass
