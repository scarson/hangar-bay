# ABOUTME: Covers the collection-time guard that forbids pytest.mark.vcr on tests driving the
# ABOUTME: ASGI app client — the pairing that silently replays cassettes instead of the app.

import pytest

from fastapi_app.tests import conftest
from fastapi_app.tests.marker_guards import forbid_vcr_on_app_client_tests


class _Item:
    """Stand-in for a pytest collection item. The guard reads only these two attributes."""

    def __init__(self, name, markers, fixturenames):
        self.nodeid = f"src/fastapi_app/tests/api/test_example.py::{name}"
        self._markers = markers
        self.fixturenames = fixturenames

    def get_closest_marker(self, name):
        return object() if name in self._markers else None


def test_vcr_on_a_client_test_aborts_the_run():
    items = [_Item("test_lists_contracts", ["vcr"], ["client", "db_session"])]

    with pytest.raises(pytest.UsageError) as excinfo:
        forbid_vcr_on_app_client_tests(items)

    assert "test_lists_contracts" in str(excinfo.value)


def test_vcr_on_an_auth_client_test_aborts_the_run():
    """auth_client wraps ASGITransport too, so it is caught by the same rule."""
    items = [_Item("test_reads_me", ["vcr"], ["auth_client"])]

    with pytest.raises(pytest.UsageError) as excinfo:
        forbid_vcr_on_app_client_tests(items)

    assert "test_reads_me" in str(excinfo.value)


def test_every_offender_is_named_not_just_the_first():
    """A whole module re-marked at once should be reported in one pass, not one run per fix."""
    items = [
        _Item("test_alpha", ["vcr"], ["client"]),
        _Item("test_beta", ["vcr"], ["client"]),
    ]

    with pytest.raises(pytest.UsageError) as excinfo:
        forbid_vcr_on_app_client_tests(items)

    message = str(excinfo.value)
    assert "test_alpha" in message
    assert "test_beta" in message


def test_vcr_without_the_app_client_is_allowed():
    """Recording a real ESI interaction is the legitimate use of the marker; leave it alone."""
    items = [_Item("test_fetches_public_contracts", ["vcr", "esi_live"], ["esi_client"])]

    forbid_vcr_on_app_client_tests(items)


def test_app_client_without_vcr_is_allowed():
    items = [_Item("test_lists_contracts", [], ["client", "db_session"])]

    forbid_vcr_on_app_client_tests(items)


def test_the_suite_conftest_wires_the_guard_into_collection():
    """Exercises the real hook, so deleting its body fails here rather than silently."""
    items = [_Item("test_lists_contracts", ["vcr"], ["client"])]

    with pytest.raises(pytest.UsageError):
        conftest.pytest_collection_modifyitems(items)
