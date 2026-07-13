# ABOUTME: create_db_tables() must be a no-op outside development (prod-safety rider).
# ABOUTME: Environment-gated main-module startup behavior, driven via module-global monkeypatching.
import logging

import pytest

from fastapi_app import main as main_mod


@pytest.mark.asyncio
async def test_create_db_tables_skips_outside_development(monkeypatch, caplog):
    from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_create_db_tables_runs_in_development(monkeypatch):
    # Mirror direction (testing-pitfalls §6 Boundary): development must still reach
    # engine.begin()/drop_all/create_all — a gate that no-ops everywhere would pass
    # the skip test above while silently killing dev table creation (ENV-2).
    from types import SimpleNamespace

    from fastapi_app.db import Base

    monkeypatch.setattr(main_mod.settings, "ENVIRONMENT", "development")
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
