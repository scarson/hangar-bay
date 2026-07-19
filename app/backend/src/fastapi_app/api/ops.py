# ABOUTME: Operational endpoints — /ready (dependency + freshness readiness; deploy health gate).
# ABOUTME: /health (in main.py) stays the dependency-free liveness stub per observability-spec §2.5.
import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from ..core.cache import init_cache
from ..core.config import get_settings
from ..db import async_engine
from ..services.background_aggregation import INGEST_LAST_RUN_KEY

router = APIRouter(tags=["Ops"])  # bare mount (PROXY-1)

READINESS_CHECK_TIMEOUT_SECONDS = 2.0  # spec §8.1: short timeouts so /ready never hangs a deploy gate


async def _probe_db() -> bool:
    """SELECT 1 on a dedicated engine connection — never a request-scoped session.

    A session-based probe leaves a failed/canceled transaction for get_db's post-yield
    commit()/rollback() cleanup, which can raise on the dead connection and replace the
    structured 503 with a 500. The connection context here never commits; its close/
    rollback failures are contained in this except.
    """
    try:
        async with asyncio.timeout(READINESS_CHECK_TIMEOUT_SECONDS):
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True
    except Exception:            # includes TimeoutError — a hung probe is an unhealthy component
        return False


async def _probe_cache(request: Request) -> tuple[bool, object]:
    """Ping the cache and fetch the freshness record; returns (ok, raw record or None).

    The client comes straight off app.state, NOT the get_cache dependency — that
    dependency raises when startup init failed, which would replace the structured
    readiness body with a bare 503 and never re-probe. A missing client gets one
    reinit attempt per call. Reachability note: a Valkey outage that persists through
    startup crashes the process at scheduler.start() (RedisJobStore) before /ready ever
    serves — platform restarts recover that case; this reinit covers the narrower blip
    where init_cache's single ping failed but Valkey returned afterwards.
    """
    try:
        async with asyncio.timeout(READINESS_CHECK_TIMEOUT_SECONDS):
            cache = getattr(request.app.state, "redis", None)
            if cache is None:
                await init_cache(request.app)
                cache = getattr(request.app.state, "redis", None)
            if cache is None:
                raise ConnectionError("cache client unavailable")
            await cache.ping()
            return True, await cache.get(INGEST_LAST_RUN_KEY)
    except Exception:
        return False, None


def _freshness_fields(freshness) -> tuple[object, object]:
    """Parse (age_seconds, outcome) out of the raw freshness record; (None, None) when absent/corrupt."""
    if not freshness:
        return None, None
    try:
        record = json.loads(freshness)
        if not isinstance(record, dict):
            # Valid-but-non-object JSON is corrupt — read as no-record; an
            # AttributeError here would 500 the deployment health gate.
            return None, None
        outcome = record.get("outcome")
        last_success = record.get("last_success_at")
        age = None
        if last_success:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_success)).total_seconds()
        return age, outcome
    except (ValueError, TypeError):
        return None, None


@router.get("/ready")
async def ready(request: Request, response: Response):
    settings = get_settings()
    db_ok = await _probe_db()
    cache_ok, freshness = await _probe_cache(request)
    age, outcome = _freshness_fields(freshness)
    checks: dict[str, object] = {
        "commit": os.environ.get("RENDER_GIT_COMMIT", "unknown"),
        "db": "ok" if db_ok else "error",
        "cache": "ok" if cache_ok else "error",
        "last_ingest_age_seconds": age,
        "last_ingest_outcome": outcome,
        # Never-ingested or over 2x the cadence counts as stale; staleness NEVER fails
        # readiness (observability-spec §2.5: ESI trouble is a freshness signal, not unreadiness).
        "data_stale": age is None or age > 2 * settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS,
    }
    if not (db_ok and cache_ok):
        response.status_code = 503
    return checks
