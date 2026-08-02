# ABOUTME: Collection-time guards that reject test-marker combinations known to produce
# ABOUTME: tests which pass without exercising anything.

import pytest

# Fixtures that hand a test an httpx client wired to our own app over ASGITransport.
APP_CLIENT_FIXTURES = frozenset({"client", "auth_client"})


def forbid_vcr_on_app_client_tests(items):
    """Abort collection if any test pairs `pytest.mark.vcr` with an ASGI app client.

    vcrpy patches below httpx and ahead of ASGITransport, so a VCR-marked test that calls
    our own endpoints records its first run into a cassette and replays it forever after.
    It then passes identically whether the behavior it names works or has been deleted —
    the application, the database, and the code under test are never reached (TEST-14).

    The marker is legitimate on tests of the client-to-ESI interaction, which own no app
    client; only the pairing is banned, so those keep working untouched.
    """
    offenders = [
        item.nodeid
        for item in items
        if item.get_closest_marker("vcr") is not None
        and APP_CLIENT_FIXTURES.intersection(item.fixturenames)
    ]
    if offenders:
        listed = "\n  ".join(offenders)
        raise pytest.UsageError(
            "pytest.mark.vcr is applied to tests that drive the app over ASGITransport:\n"
            f"  {listed}\n"
            "vcrpy intercepts ahead of ASGITransport, so these replay a cassette and assert "
            "nothing about the app (TEST-14). Drop the marker, or move the recorded "
            "interaction into a test of the ESI client that uses no app-client fixture."
        )
