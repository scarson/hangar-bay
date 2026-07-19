# ABOUTME: Thin tests for the matcher scheduler wiring — job registration args + wrapper error-swallow.
# ABOUTME: The scheduler itself is not run (mirrors how add_aggregation_job is left unexercised).
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi_app.core.scheduler import add_watchlist_matcher_job
from fastapi_app.services.scheduled_jobs import run_watchlist_matcher_job
from fastapi_app.services.watchlist_matcher import WatchlistMatcherService



def test_add_watchlist_matcher_job_registers_expected_id():
    scheduler = MagicMock()
    settings = MagicMock(WATCHLIST_MATCH_INTERVAL_SECONDS=900)
    svc = WatchlistMatcherService(settings=settings)
    add_watchlist_matcher_job(scheduler, svc, settings)
    scheduler.add_job.assert_called_once()
    call = scheduler.add_job.call_args
    assert call.args[0] is run_watchlist_matcher_job
    assert call.kwargs["id"] == "match_watchlists"
    assert call.kwargs["seconds"] == 900
    assert call.kwargs["args"] == [svc]
    assert call.kwargs["replace_existing"] is True


def test_matcher_service_is_picklable():
    import pickle
    # RedisJobStore pickles the job func + args; the SERVICE itself must round-trip (a MagicMock
    # settings or a lambda now_fn would break this — use the real settings singleton).
    from fastapi_app.core.config import settings as real_settings
    svc = WatchlistMatcherService(settings=real_settings, now_fn=None)
    restored = pickle.loads(pickle.dumps(svc))
    assert restored.now_fn is None
    assert restored.settings.WATCHLIST_MATCH_INTERVAL_SECONDS == real_settings.WATCHLIST_MATCH_INTERVAL_SECONDS


@pytest.mark.asyncio
async def test_run_watchlist_matcher_job_swallows_exceptions():
    svc = MagicMock()
    svc.run_matching = AsyncMock(side_effect=RuntimeError("boom"))
    await run_watchlist_matcher_job(svc)   # must NOT raise
    svc.run_matching.assert_awaited_once()
