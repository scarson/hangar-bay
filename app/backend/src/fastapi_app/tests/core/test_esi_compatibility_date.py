# ABOUTME: Pins the X-Compatibility-Date Hangar Bay sends to ESI, and guards it against
# ABOUTME: drifting away from the date the ESI spec monitor watches (pitfall ESI-4).

import httpx
import pytest

from fastapi_app.core.config import Settings
from fastapi_app.core.esi_client_class import ESIClient

pytestmark = pytest.mark.asyncio


def _settings() -> Settings:
    """An isolated Settings instance.

    `_env_file=None` is load-bearing: without it pydantic-settings reads the repo's
    real .env, so the assertions below would describe whatever a developer's local
    file happens to say rather than the value this project ships.
    """
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/x",
        CACHE_URL="redis://localhost:6379/9",
        ESI_USER_AGENT="hangar-bay-tests",
    )


async def test_esi_client_sends_the_compatibility_date_header():
    """Every ESI request carries an explicit X-Compatibility-Date.

    Without the header ESI answers at the OLDEST published date, not the newest — so
    omitting it is not "no opinion", it is silently pinning the whole application to a
    date CCP chose for us and can raise with notice (ESI-4).
    """
    settings = _settings()
    seen: dict[str, str] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(capture)
    async with httpx.AsyncClient(
        base_url=settings.ESI_BASE_URL,
        headers=ESIClient.default_headers(settings),
        transport=transport,
    ) as http_client:
        await http_client.get("/anything")

    assert seen.get("x-compatibility-date") == settings.ESI_COMPATIBILITY_DATE


async def test_compatibility_date_matches_the_spec_monitor_snapshot():
    """The date we SEND and the date the drift monitor WATCHES must be the same string.

    These live in different trees — a setting in the app, a field in the monitor's
    committed snapshot — and nothing else couples them. If they drift apart the monitor
    keeps passing while faithfully watching a contract we no longer request, which is a
    worse failure than having no monitor: it reports safety it cannot see.
    """
    import json
    from pathlib import Path

    snapshot_path = (
        Path(__file__).resolve().parents[4]
        / "tools"
        / "esi_spec_monitor"
        / "snapshot.json"
    )
    snapshot = json.loads(snapshot_path.read_text())

    assert snapshot["pinned_compatibility_date"] == _settings().ESI_COMPATIBILITY_DATE


async def test_monitor_pins_the_same_date_the_client_sends():
    """The monitor's own constant must equal the setting.

    The monitor is standard-library only by design, so it cannot import Settings and
    duplicates the date instead. This is the guard that makes the duplication safe: the
    snapshot assertion above only proves the committed artifact agrees, and the artifact
    is regenerated from whatever date the monitor fetched — so without this, both could
    move together to a date the application does not send.
    """
    import sys
    from pathlib import Path

    tools_dir = Path(__file__).resolve().parents[4] / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from esi_spec_monitor.monitor import PINNED_COMPATIBILITY_DATE

    assert PINNED_COMPATIBILITY_DATE == _settings().ESI_COMPATIBILITY_DATE
