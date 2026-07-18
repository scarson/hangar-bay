# ABOUTME: ESI exception classes — attribute, message, and pickle/copy round-trip contracts.
# ABOUTME: Round-trips matter because exceptions cross process boundaries (multiprocessing, task queues) via pickle.
import copy
import pickle

from fastapi_app.core.exceptions import ESIRequestFailedError


def test_esi_request_failed_attributes_and_str():
    exc = ESIRequestFailedError(status_code=503, message="upstream sad")
    assert exc.status_code == 503
    assert exc.message == "upstream sad"
    assert str(exc) == "ESI request failed with status 503: upstream sad"


def test_esi_request_failed_pickle_round_trip():
    exc = ESIRequestFailedError(status_code=503, message="upstream sad")
    clone = pickle.loads(pickle.dumps(exc))
    assert clone.status_code == 503
    assert clone.message == "upstream sad"
    assert str(clone) == str(exc)


def test_esi_request_failed_copy_round_trip():
    exc = ESIRequestFailedError(status_code=404, message="no such page")
    clone = copy.copy(exc)
    assert clone.status_code == 404
    assert clone.message == "no such page"
    assert str(clone) == str(exc)
