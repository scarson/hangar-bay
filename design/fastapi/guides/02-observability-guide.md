# FastAPI Observability Design Guide

## 1. Overview

This guide establishes the standards for observability within the Hangar Bay backend. Adhering to these standards ensures that our application is transparent, debuggable, and maintainable. The strategy covers four pillars:

-   **Structured Logging:** For event-based, queryable insights into application behavior.
-   **Metrics:** For aggregated, numerical data on performance and system health.
-   **Global Exception Handling:** For consistent error logging and response formatting.
-   **Testing:** To ensure our observability instrumentation is reliable and accurate.

## 2. Technology Stack, Chosen Libraries, & Rationale

Based on research, the following libraries have been selected for our observability stack:

*   **Structured Logging:** `structlog`
    *   **Rationale:** `structlog` provides a powerful processor chain that allows for easy enrichment of logs with contextual data (e.g., request IDs, user info). It integrates cleanly with FastAPI via middleware and is more maintainable and feature-rich than building a custom `JSONFormatter` on top of the standard `logging` library.
*   **Metrics:** `prometheus-fastapi-instrumentator`
    *   **Rationale:** This library is the de-facto standard for instrumenting FastAPI applications with Prometheus metrics. It provides a robust set of default metrics (latency, requests, errors) out-of-the-box and makes it easy to add custom application-specific metrics. It is well-maintained and designed specifically for our framework.
*   **Visualization & Storage:** `Grafana Cloud` (via `Grafana Alloy`)
    *   **Rationale:** Metrics and logs ship to the managed Grafana Cloud stack (org `scarson`) instead of a self-hosted Prometheus+Grafana pair — no local dashboard/storage containers to maintain. A single Alloy container (`app/backend/docker/compose.observability.yml`) scrapes the FastAPI `/metrics` endpoint on the host and tails the backend's JSON log file (`LOG_FILE` setting) into Grafana Cloud Loki. Dashboards are committed JSON under `app/backend/observability/dashboards/`, provisioned with `pdm run provision-dashboards`. Credentials live in the gitignored `app/backend/docker/grafana-cloud.env` (canonical copies in 1Password); Alloy's debug UI is at `http://localhost:12345`.

## 3. Structured Logging Strategy

### 3.1. Log Format and Correlation

*   All logs MUST be rendered as a single-line JSON object to ensure they are machine-parsable.
*   A middleware MUST be used to bind a unique `request_id` to all logs generated during a request's lifecycle. This is the primary mechanism for correlating events and tracing a single user's request through the entire application stack.

> **Risk Mitigation: Incorrect Correlation ID Propagation**
> The `request_id` must be available in all contexts (API layer, service layer, background tasks). The implementation will leverage `structlog.contextvars` to ensure the ID is automatically propagated without needing to pass it manually through function calls.

### 3.2. Core Configuration

> **Risk Mitigation: Performance Overhead**
> To prevent performance degradation in production, the logging configuration MUST be environment-aware. The log level will be dynamically set based on a `LOG_LEVEL` setting from the central `Settings` object (`core/config.py`), defaulting to `INFO` in production and `DEBUG` in development.

Logging will be configured centrally in the application startup logic. The configuration will use a processor chain to add timestamps, log levels, and render the final output as JSON.

```python
# Example configuration (to be placed in app/main.py or a config module)
import logging
import sys
import structlog

def setup_logging():
    """Configures structured logging for the application."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger to use structlog
    root_logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    # The formatter is not strictly needed for JSONRenderer but good practice
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
```

### 3.3. Key Event Schema

When logging significant business events (e.g., a contract search), the log MUST include a consistent set of key-value pairs.

> **Warning: Prevent Sensitive Data Leakage**
> To prevent inadvertently logging sensitive information, **never log raw data objects** (e.g., entire Pydantic models, full request bodies). Always construct the log entry by explicitly including only the necessary, sanitized fields defined in the schema below.

-   `event`: A short, descriptive name for the event (e.g., `contract_search_executed`).
-   `success`: (boolean) `true` if the operation succeeded, `false` otherwise.
-   `duration_ms`: (float) The time taken for the operation in milliseconds.
-   `error_message`: (string, optional) The error message if `success` is `false`.
-   `search_terms`: (dict, optional) The specific parameters used in the search.
-   `results_count`: (int, optional) The number of results returned.

**Example Log:**
```json
{"event": "contract_search_executed", "success": true, "duration_ms": 123.45, "search_terms": {"type": "item_exchange", "location": "jita"}, "results_count": 50, "log_level": "info", ...}
```

## 3.4. Global Exception Handling (Mandatory)

A global exception handler MUST be configured to catch any unhandled exceptions and ensure they are logged with structured data while returning consistent error responses to clients.

### Implementation Pattern

The global exception handler must be registered **before** any middleware in the FastAPI application to ensure it catches all unhandled exceptions:

```python
# In app/main.py - Add FIRST, before middleware
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch any unhandled exceptions and return a
    standardized 500 error response.
    """
    # Use structlog to log the exception with context
    logger = structlog.get_logger("uvicorn.error")
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        error_message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )
```

### Key Requirements

1. **Structured Logging**: All exceptions must be logged with `exc_info` for full stack traces
2. **Consistent Response**: Always return the same JSON structure for unhandled errors
3. **Security**: Never expose internal error details to clients
4. **Correlation**: The request ID will automatically be included via `structlog.contextvars`

### Testing the Global Exception Handler

The global exception handler MUST be tested to ensure proper error logging and response formatting:

```python
@pytest.mark.asyncio
async def test_global_exception_handler_logs_and_responds(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that unhandled exceptions are caught, logged, and return proper responses.
    """
    # Arrange: Mock service to raise exception
    mocker.patch(
        "fastapi_app.services.contract_service.list_contracts",
        side_effect=Exception("Critical database failure")
    )
    
    # Mock the error logger
    mock_logger = mocker.patch("structlog.get_logger")
    mock_error_logger = mock_logger.return_value
    
    # Act: Make request that triggers exception
    response = await client.get("/contracts/")
    
    # Assert: Verify error response structure
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected server error occurred."
    
    # Verify structured error logging
    mock_error_logger.error.assert_called_once()
    log_call = mock_error_logger.error.call_args[1]
    assert "exc_info" in log_call
    assert "error_message" in log_call
    assert log_call["error_message"] == "Critical database failure"
```

## 4. Metrics Strategy

The `prometheus-fastapi-instrumentator` will be configured in the main application factory. It will automatically expose a `/metrics` endpoint for Prometheus to scrape.

Our metrics strategy is based on the **RED methodology**:
-   **Rate:** The number of requests per second (`http_requests_total`).
-   **Errors:** The number of requests resulting in server-side errors (`http_requests_total` with a `status_code` label of `5xx`).
-   **Duration:** The distribution of request processing times (`http_requests_latency_seconds`).

### 4.1. Default Metrics

The `prometheus-fastapi-instrumentator` will be configured to capture the following default metrics for all relevant API endpoints. These metrics provide a comprehensive view of application performance out-of-the-box.

*   `http_requests_latency_seconds`: **Histogram** of request processing time.
*   `http_requests_total`: **Counter** for total requests.
*   `http_requests_inprogress`: **Gauge** for requests currently in progress.
*   `http_response_size_bytes`: **Histogram** of response sizes.
*   `http_request_size_bytes`: **Histogram** of request sizes.

These metrics will be labeled with `method`, `status_code`, and `handler` to allow for detailed analysis.

### 4.2. Custom Metrics

Custom metrics (e.g., `esi_api_calls_total`) will be defined as needed in relevant services to track application-specific operations.

## 5. Testing Strategy

Observability testing is **mandatory** and must verify that structured logging, metrics instrumentation, and error handling work correctly. This section provides comprehensive patterns based on real implementation experience.

### 5.1. Core Testing Tools

*   **`pytest-mock`**: Essential for isolating and verifying logging behavior without actual I/O
*   **`httpx.AsyncClient`**: For making API requests in integration tests
*   **MockerFixture**: For mocking logger instances and capturing log calls
*   **Metrics endpoint**: The `/metrics` endpoint for verifying Prometheus instrumentation

For complete testing infrastructure setup, see our [FastAPI Testing Strategies Guide](09-testing-strategies.md#observability-testing-a-mandatory-category).

### 5.2. Testing Structured Logging with Key Events Schema

Tests must verify that service functions emit logs conforming to the **Key Events Schema** defined above.

```python
import pytest
from pytest_mock import MockerFixture
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_successful_request_logs_key_event(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that successful operations generate structured logs 
    matching the Key Events schema.
    """
    # Arrange: Mock the service logger to capture calls
    mock_logger = mocker.patch("fastapi_app.services.contract_service.logger")
    
    # Act: Trigger the operation
    response = await client.get("/contracts/")
    
    # Assert: Verify response and Key Events schema compliance
    assert response.status_code == 200
    
    # Verify logger was called with correct structure
    mock_logger.info.assert_called_once()
    log_call = mock_logger.info.call_args[1]  # Get keyword arguments
    
    # Verify required Key Events fields
    assert "event" in log_call
    assert "success" in log_call
    assert "duration_ms" in log_call
    assert log_call["success"] is True
    assert isinstance(log_call["duration_ms"], (int, float))
    
    # Verify event-specific fields
    if "results_count" in log_call:
        assert isinstance(log_call["results_count"], int)
```

### 5.3. Testing Prometheus Metrics Instrumentation

Tests must verify that API endpoints correctly increment Prometheus metrics with proper labels.

```python
@pytest.mark.asyncio
async def test_successful_request_increments_prometheus_metrics(
    client: AsyncClient
):
    """
    Verify that API requests increment Prometheus metrics with correct labels.
    """
    # Act: Make request to instrumented endpoint
    response = await client.get("/contracts/")
    assert response.status_code == 200
    
    # Verify: Check metrics endpoint for proper instrumentation
    metrics_response = await client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Verify specific metrics with correct labels
    assert 'http_requests_total{handler="/contracts/",method="GET",status="200"}' in metrics_text
    assert 'http_request_duration_seconds_bucket{handler="/contracts/",method="GET"}' in metrics_text
    
    # Verify metrics are actually incremented (not just present)
    # Look for non-zero values in the metrics output
    assert any('} 1.0' in line or '} 1' in line for line in metrics_text.split('\n') 
              if 'http_requests_total' in line and 'GET' in line)
```

### 5.4. Testing Global Exception Handler

Tests must verify that unhandled exceptions are caught by the global exception handler and logged properly.

```python
@pytest.mark.asyncio
async def test_failed_request_logs_key_event(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that server errors trigger proper exception handling and structured logging.
    """
    # Arrange: Mock service to raise exception
    mocker.patch(
        "fastapi_app.services.contract_service.list_contracts",
        side_effect=Exception("Critical database failure")
    )
    
    # Mock the error logger used by global exception handler
    mock_logger = mocker.patch("structlog.get_logger")
    mock_error_logger = mock_logger.return_value
    
    # Act: Make request that triggers exception
    response = await client.get("/contracts/")
    
    # Assert: Verify standardized error response
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected server error occurred."
    
    # Verify structured error logging
    mock_error_logger.error.assert_called_once()
    log_call = mock_error_logger.error.call_args[1]
    
    # Verify required error logging fields
    assert "exc_info" in log_call
    assert "error_message" in log_call
    assert log_call["error_message"] == "Critical database failure"
```

### 5.5. Testing Request ID Correlation

Tests must verify that the same `request_id` propagates across all service layers during a single request.

```python
@pytest.mark.asyncio
async def test_request_id_correlation(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that request_id is consistent across API and service layers.
    """
    # Arrange: Mock loggers from different layers
    api_mock = mocker.patch("fastapi_app.middleware.request_id.logger")
    service_mock = mocker.patch("fastapi_app.services.contract_service.logger")
    
    # Act: Make request that touches multiple layers
    response = await client.get("/contracts/")
    assert response.status_code == 200
    
    # Extract request_id from both loggers
    api_request_id = api_mock.info.call_args[1].get("request_id")
    service_request_id = service_mock.info.call_args[1].get("request_id")
    
    # Verify: Same request_id across all layers
    assert api_request_id is not None
    assert service_request_id is not None
    assert api_request_id == service_request_id
```

### 5.6. Best Practices for Observability Testing

> **Critical: Use pytest-mock for Isolation**
> Always use `pytest-mock` to isolate logging behavior. Never rely on actual log output or files, as this creates brittle tests and potential race conditions.

1. **Schema Compliance**: Always verify that logs match the defined Key Events schema
2. **Mock Isolation**: Use `pytest-mock` to isolate logging from actual I/O operations
3. **Label Verification**: For metrics tests, verify both presence and correct labeling
4. **Error Scenarios**: Test both success and failure paths for complete coverage
5. **Correlation Testing**: Verify request ID propagation across service boundaries

### 5.7. Integration with Main Testing Strategy

Observability tests should be integrated into the main test suite, not run separately. They use the same fixtures (`client`, `db_session`) as integration tests but focus specifically on telemetry verification.

For complete fixture setup and additional observability testing patterns, see the [FastAPI Testing Strategies Guide](09-testing-strategies.md).
