# ABOUTME: Tests for APScheduler construction — jobstore choice and app.state wiring.
# ABOUTME: Pins the in-memory jobstore: scheduler state must never live in an evicting cache.
from unittest.mock import MagicMock

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from fastapi import FastAPI

from fastapi_app.core.config import settings
from fastapi_app.core.scheduler import add_aggregation_job, create_scheduler


def test_create_scheduler_uses_in_memory_jobstore():
    """The lifespan re-registers every job on boot (replace_existing=True), so a
    persistent jobstore adds nothing — while a Redis-backed one colocates the
    scheduler's job records with a cache running allkeys-lru, where memory
    pressure silently evicts them: no due jobs, no errors, no ticks (production
    outage 2026-07-23, 3.6 days without a scheduler tick)."""
    app = FastAPI()
    scheduler = create_scheduler(app, settings)
    store = scheduler._jobstores["default"]
    assert isinstance(store, MemoryJobStore)
    assert not isinstance(store, RedisJobStore)


def test_create_scheduler_attaches_scheduler_to_app_state():
    app = FastAPI()
    scheduler = create_scheduler(app, settings)
    assert app.state.scheduler is scheduler


def test_aggregation_job_runs_single_instance():
    """max_instances=1 is what actually serializes aggregation runs — the Valkey
    lock's TTL (interval + margin) is shorter than a full-corpus resweep, so a
    second in-process instance would race the tail of a long run. The
    ENRICHMENT_VERSION runbook in services/background_aggregation.py leans on
    this value; it must be pinned, not inherited from a library default."""
    app = FastAPI()
    scheduler = create_scheduler(app, settings)
    add_aggregation_job(scheduler, MagicMock(), settings)
    job = scheduler.get_job("aggregate_public_contracts")
    assert job.max_instances == 1
