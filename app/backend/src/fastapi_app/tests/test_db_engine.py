# ABOUTME: The application engine must never render a failed statement's bind values.
# ABOUTME: Bind values carry user-typed search text, which is PII everywhere it can surface.
from sqlalchemy.exc import StatementError

from fastapi_app.db import async_engine


def test_engine_errors_never_render_bound_parameter_values():
    """A statement failure raised by the application engine hides its bind values.

    Every SQLAlchemy error that wraps a failed statement renders
    `[parameters: {...}]` into its `str()` unless the engine that raised it was built
    with `hide_parameters=True`. On the contract-search path the failing statement is
    the one carrying the `ILIKE` bind that holds the user's raw search text, and that
    string reaches a log line from more than one place: the service's own failure log
    and `main.py`'s `generic_exception_handler`, which logs both `str(exc)` and the
    traceback. Hiding at the engine closes all of them at the source.

    The engine's configured URL is not reachable from the test environment (the test
    suite runs against `DATABASE_URL_TESTS`, a different engine), so this drives the
    rendering directly with the flag the engine actually carries — the same value
    SQLAlchemy passes to `DBAPIError.instance()` when it wraps a driver error
    (`engine/base.py::_handle_dbapi_exception`).
    """
    secret = "Tristan sale"
    error = StatementError(
        "canceling statement due to statement timeout",
        "SELECT contracts.contract_id FROM contracts WHERE contracts.title ILIKE %(title_1)s",
        {"title_1": f"%{secret}%"},
        Exception("canceling statement due to statement timeout"),
        hide_parameters=async_engine.sync_engine.hide_parameters,
    )

    rendered = str(error)
    assert secret not in rendered
    assert "hide_parameters=True" in rendered
