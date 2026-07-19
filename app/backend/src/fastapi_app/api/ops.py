# ABOUTME: Operational endpoints — /ready (dependency + freshness readiness; deploy health gate).
# ABOUTME: /health (in main.py) stays the dependency-free liveness stub per observability-spec §2.5.
import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.dependencies import get_cache
from ..db import get_db
from ..services.background_aggregation import INGEST_LAST_RUN_KEY

router = APIRouter(tags=["Ops"])  # bare mount (PROXY-1)

READINESS_CHECK_TIMEOUT_SECONDS = 2.0  # spec §8.1: short timeouts so /ready never hangs a deploy gate


@router.get("/ready")
async def ready(response: Response, db: AsyncSession = Depends(get_db), cache=Depends(get_cache)):
    settings = get_settings()
    checks: dict[str, object] = {
        "commit": os.environ.get("RENDER_GIT_COMMIT", "unknown"),
    }
    healthy = True
    try:
        async with asyncio.timeout(READINESS_CHECK_TIMEOUT_SECONDS):
            await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:            # includes TimeoutError — a hung probe is an unhealthy component
        checks["db"] = "error"
        healthy = False
    freshness = None
    try:
        async with asyncio.timeout(READINESS_CHECK_TIMEOUT_SECONDS):
            await cache.ping()
            freshness = await cache.get(INGEST_LAST_RUN_KEY)
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "error"
        healthy = False
    age = None
    outcome = None
    if freshness:
        try:
            record = json.loads(freshness)
            outcome = record.get("outcome")
            last_success = record.get("last_success_at")
            if last_success:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_success)).total_seconds()
        except (ValueError, TypeError):
            pass
    checks["last_ingest_age_seconds"] = age
    checks["last_ingest_outcome"] = outcome
    # Never-ingested or over 2x the cadence counts as stale; staleness NEVER fails
    # readiness (observability-spec §2.5: ESI trouble is a freshness signal, not unreadiness).
    checks["data_stale"] = age is None or age > 2 * settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS
    if not healthy:
        response.status_code = 503
    return checks
