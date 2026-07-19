# ABOUTME: Tests for /ready — db + cache + ingestion-freshness readiness (deploy health gate).
# ABOUTME: Every dependency path (ok, down, hung, never-initialized) and the freshness/staleness derivations.
import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from fastapi_app.api import ops
from fastapi_app.core.config import settings
from fastapi_app.services.background_aggregation import INGEST_LAST_RUN_KEY

pytestmark = pytest.mark.asyncio


class _FakeConn:
    def __init__(self, *, exc=None, delay=0.0):
        self.exc = exc
        self.delay = delay

    async def execute(self, *_a, **_k):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return None


class _FakeEngine:
    """Engine double for /ready's dedicated-connection db probe (no session, no commit)."""

    def __init__(self, *, exc=None, delay=0.0, connect_exc=None):
        self.conn = _FakeConn(exc=exc, delay=delay)
        self.connect_exc = connect_exc

    def connect(self):
        engine = self

        class _Ctx:
            async def __aenter__(self):
                if engine.connect_exc:
                    raise engine.connect_exc
                return engine.conn

            async def __aexit__(self, *a):
                return False

        return _Ctx()


def _set_db_engine(monkeypatch: pytest.MonkeyPatch, fake: "_FakeEngine") -> None:
    monkeypatch.setattr(ops, "async_engine", fake)


class _OpsFakeCache:
    """ping/get double for the /ready cache probe (delay + failure injectable)."""

    def __init__(self, store=None, *, ping_exc=None, ping_delay=0.0):
        self.store = store or {}
        self.ping_exc = ping_exc
        self.ping_delay = ping_delay

    async def ping(self):
        if self.ping_delay:
            await asyncio.sleep(self.ping_delay)
        if self.ping_exc:
            raise self.ping_exc
        return True

    async def get(self, key):
        return self.store.get(key)


def _fresh_record(now=None):
    now_iso = (now or datetime.now(timezone.utc)).isoformat()
    return json.dumps(
        {
            "finished_at": now_iso,
            "outcome": "success",
            "regions_ok": 1,
            "regions_failed": 0,
            "last_success_at": now_iso,
        }
    )


def _set_cache(app: FastAPI, monkeypatch: pytest.MonkeyPatch, fake) -> None:
    """/ready reads the client straight off app.state (not the get_cache dependency,
    which would 503 before the probe runs); monkeypatch restores state after the test."""
    monkeypatch.setattr(app.state, "redis", fake, raising=False)


async def test_ready_ok_reports_db_cache_and_freshness(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record()}))
    r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok" and body["cache"] == "ok"
    assert body["last_ingest_outcome"] == "success"
    assert body["last_ingest_age_seconds"] < 60
    assert body["data_stale"] is False
    assert body["commit"]  # release identifier (RENDER_GIT_COMMIT or "unknown")


async def test_ready_probes_db_on_a_dedicated_connection_not_a_request_session(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    """The probe must run on its own engine connection — a request-scoped session's
    post-yield commit()/rollback() cleanup on a dead connection can replace the
    structured 503 with a 500 (PendingRollbackError class of failures)."""
    fake = _FakeEngine()
    _set_db_engine(monkeypatch, fake)
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record()}))
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


async def test_ready_503_when_db_down(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    _set_db_engine(monkeypatch, _FakeEngine(exc=RuntimeError("db down")))
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record()}))
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["db"] == "error"


async def test_ready_503_when_db_connect_fails(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    _set_db_engine(monkeypatch, _FakeEngine(connect_exc=ConnectionError("refused")))
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record()}))
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["db"] == "error"


async def test_ready_503_when_db_hangs(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(ops, "READINESS_CHECK_TIMEOUT_SECONDS", 0.05)
    _set_db_engine(monkeypatch, _FakeEngine(delay=0.5))
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record()}))
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["db"] == "error"


async def test_ready_503_when_cache_down(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, _OpsFakeCache(ping_exc=ConnectionError("cache down")))
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["cache"] == "error"


async def test_ready_503_when_cache_hangs(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(ops, "READINESS_CHECK_TIMEOUT_SECONDS", 0.05)
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, _OpsFakeCache(ping_delay=0.5))
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["cache"] == "error"


async def test_ready_structured_503_when_cache_never_initialized(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    """A failed startup init leaves app.state.redis None; /ready must still return its
    STRUCTURED body (db probed, commit present) — never the bare get_cache dependency
    503 — and must attempt exactly one self-heal reinitialization."""
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, None)
    reinit = {"n": 0}

    async def failing_init(app):
        reinit["n"] += 1   # heal attempt fails: state.redis stays None

    monkeypatch.setattr(ops, "init_cache", failing_init)
    r = await client.get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["cache"] == "error"
    assert body["db"] == "ok"
    assert body["commit"]
    assert reinit["n"] == 1


async def test_ready_self_heals_when_cache_recovers(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    """A transient Valkey outage at boot must not brick readiness until a restart:
    once Valkey answers again, the reinit succeeds and /ready reports healthy."""
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, None)
    fake = _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record()})

    async def recovering_init(app):
        app.state.redis = fake

    monkeypatch.setattr(ops, "init_cache", recovering_init)
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["cache"] == "ok"


async def test_ready_stale_flag_when_ingest_old(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    old = datetime.now(timezone.utc) - timedelta(
        seconds=3 * settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS
    )
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: _fresh_record(old)}))
    r = await client.get("/ready")
    assert r.status_code == 200  # staleness NEVER fails readiness (observability-spec §2.5)
    body = r.json()
    assert body["data_stale"] is True
    assert body["last_ingest_age_seconds"] > 2 * settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS


async def test_ready_null_freshness_before_first_run(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, _OpsFakeCache({}))
    r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["last_ingest_age_seconds"] is None
    assert body["last_ingest_outcome"] is None
    assert body["data_stale"] is True  # never-ingested IS stale


@pytest.mark.parametrize("corrupt", ["null", "[]", '"str"', "42"])
async def test_ready_treats_non_object_freshness_json_as_absent(
    client: AsyncClient, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch, corrupt
):
    """Valid-but-non-object JSON in the freshness key must read as no-record — never
    an AttributeError 500 that wedges the deployment health gate."""
    _set_db_engine(monkeypatch, _FakeEngine())
    _set_cache(test_app, monkeypatch, _OpsFakeCache({INGEST_LAST_RUN_KEY: corrupt}))
    r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["last_ingest_age_seconds"] is None
    assert body["last_ingest_outcome"] is None
    assert body["data_stale"] is True
