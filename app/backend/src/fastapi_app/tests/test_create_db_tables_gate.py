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


@pytest.mark.parametrize(
    "env,client_id,keys,expect_warning",
    [
        ("development", "", "", True),        # unconfigured in dev → exactly one warning
        ("development", "cid", "some-key", False),  # configured in dev → silent
        ("development", "cid", "", True),     # client id set, cipher unset → still warns (pins the OR)
        ("development", "", "some-key", True),  # cipher set, client id unset → still warns (pins the OR)
        ("production", "", "", False),        # never warns outside development
    ],
)
def test_sso_unconfigured_startup_warning(monkeypatch, caplog, env, client_id, keys, expect_warning):
    from pydantic import SecretStr

    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", env)
    monkeypatch.setattr(main_mod.settings, "ESI_CLIENT_ID", client_id)
    monkeypatch.setattr(main_mod.settings, "TOKEN_CIPHER_KEYS", SecretStr(keys))
    with caplog.at_level(logging.WARNING):
        main_mod.warn_if_sso_unconfigured()
    warnings = [r for r in caplog.records if "EVE SSO is not configured" in r.getMessage()]
    assert len(warnings) == (1 if expect_warning else 0)


def test_sso_unconfigured_startup_warning_names_only_login_and_callback(monkeypatch, caplog):
    # Finding 11: the message previously claimed every /auth/sso/* route 503s,
    # but logout stays operational (204, not guarded) — the warning must name
    # login and callback specifically, not the whole route family.
    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(main_mod.settings, "ESI_CLIENT_ID", "")
    from pydantic import SecretStr
    monkeypatch.setattr(main_mod.settings, "TOKEN_CIPHER_KEYS", SecretStr(""))
    with caplog.at_level(logging.WARNING):
        main_mod.warn_if_sso_unconfigured()
    messages = [r.getMessage() for r in caplog.records if "EVE SSO is not configured" in r.getMessage()]
    assert len(messages) == 1
    assert "/auth/sso/login" in messages[0]
    assert "/auth/sso/callback" in messages[0]
    assert "/auth/sso/*" not in messages[0]   # the over-broad claim must be gone
    assert "/auth/sso/logout" not in messages[0]   # logout is never guarded (§4.4)
