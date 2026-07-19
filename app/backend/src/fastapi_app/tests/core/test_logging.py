# ABOUTME: Tests for core/logging.py setup_logging — LOG_FILE file-sink behavior.
# ABOUTME: Verifies the sink is off by default and writes JSON lines when configured.
import json
import logging

import pytest
import structlog

from fastapi_app.core.config import Settings
from fastapi_app.core.logging import setup_logging


def _make_settings(**overrides):
    return Settings(
        ESI_USER_AGENT="pytest",
        DATABASE_URL="postgresql+asyncpg://unused:unused@localhost/unused",
        CACHE_URL="redis://localhost:6379/0",
        _env_file=None,
        **overrides,
    )


@pytest.fixture
def restore_logging():
    """setup_logging mutates process-global state; snapshot and restore ALL of it.

    The suite normally runs on structlog's DEFAULT config — conftest never calls
    setup_logging (it only runs inside main.py's lifespan, which ASGITransport
    bypasses; see testing-pitfalls TEST-10). test_observability.py depends on
    that default (its human-readable log parser). So this fixture must restore
    BOTH the root logger's handlers/level AND structlog's exact prior config,
    or every test collected after this file runs under a leaked JSON config.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_structlog_config = structlog.get_config()
    yield
    for h in root.handlers:
        if h not in saved_handlers:
            h.close()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    structlog.configure(**saved_structlog_config)


def test_log_file_defaults_to_disabled(restore_logging, tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)  # _env_file=None still reads OS env
    monkeypatch.chdir(tmp_path)  # any accidental relative file would land here
    setup_logging(_make_settings())
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert not isinstance(root.handlers[0], logging.FileHandler)
    assert list(tmp_path.iterdir()) == []


def test_log_file_writes_json_lines(restore_logging, tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)
    log_path = tmp_path / "nested" / "backend.jsonl"
    setup_logging(_make_settings(LOG_FILE=str(log_path)))

    structlog.get_logger("test.sink").info("file_sink_smoke", marker="abc123")

    assert log_path.exists()  # parent dir auto-created
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    # Only structlog lines are JSON; a stray stdlib record (none expected here,
    # but possible from imported libraries) must not turn the test into a
    # JSONDecodeError instead of an assertion failure.
    payloads = [json.loads(line) for line in lines if line.startswith("{")]
    matching = [p for p in payloads if p.get("event") == "file_sink_smoke"]
    assert len(matching) == 1
    assert matching[0]["marker"] == "abc123"
    assert matching[0]["level"] == "info"


def test_log_file_and_stdout_both_attached(restore_logging, tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)
    setup_logging(_make_settings(LOG_FILE=str(tmp_path / "backend.jsonl")))
    root = logging.getLogger()
    kinds = [type(h) for h in root.handlers]
    assert kinds.count(logging.FileHandler) == 1
    # StreamHandler is FileHandler's base class; count exact stdout handler separately
    assert sum(1 for h in root.handlers if type(h) is logging.StreamHandler) == 1
