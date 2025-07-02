# FastAPI Observability Design Guide

## 1. Overview

This guide establishes the standards for observability within the Hangar Bay backend. Adhering to these standards ensures that our application is transparent, debuggable, and maintainable. The strategy covers three pillars:

-   **Structured Logging:** For event-based, queryable insights into application behavior.
-   **Metrics:** For aggregated, numerical data on performance and system health.
-   **Testing:** To ensure our observability instrumentation is reliable and accurate.

## 2. Technology Stack, Chosen Libraries, & Rationale

Based on research, the following libraries have been selected for our observability stack:

*   **Structured Logging:** `structlog`
    *   **Rationale:** `structlog` provides a powerful processor chain that allows for easy enrichment of logs with contextual data (e.g., request IDs, user info). It integrates cleanly with FastAPI via middleware and is more maintainable and feature-rich than building a custom `JSONFormatter` on top of the standard `logging` library.
*   **Metrics:** `prometheus-fastapi-instrumentator`
    *   **Rationale:** This library is the de-facto standard for instrumenting FastAPI applications with Prometheus metrics. It provides a robust set of default metrics (latency, requests, errors) out-of-the-box and makes it easy to add custom application-specific metrics. It is well-maintained and designed specifically for our framework.
*   **Local Visualization:** `Prometheus` & `Grafana`
    *   **Rationale:** This is the industry-standard combination for metrics collection and visualization. We will use the Docker Compose setup at `app\backend\docker\compose.observability.yml` for local development to ensure developers can test and verify metrics before deployment. The `prometheus.yml` file will be configured to scrape the `/metrics` endpoint of the FastAPI app and expose it at `http://localhost:9090`. The `grafana.yml` file will be configured to visualize the metrics at `http://localhost:3000`.

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

### 5.1. Testing Structured Logs

*   Unit tests should assert that service functions emit logs that conform to the **Key Events Schema**. 
*   Integration tests should verify that API errors are captured and logged correctly.
*   To verify that the correct logs are emitted, we will use a `pytest` fixture that leverages `structlog.testing.capture_logs`.

**Example Fixture and Test:**
```python
# In conftest.py or a dedicated test file
import pytest
from structlog.testing import capture_logs

@pytest.fixture
def log_capture():
    """A fixture to capture structlog's output."""
    with capture_logs() as captured:
        yield captured

# In a test file, e.g., test_services.py
def test_some_service_function_logging(log_capture):
    # Call the function that is expected to log
    result = my_service_function(param="test")

    # Assert the function behaved correctly
    assert result is True

    # Assert that the log was captured and contains the expected data
    assert len(log_capture) == 1
    log = log_capture[0]
    assert log["event"] == "my_service_event"
    assert log["log_level"] == "info"
    assert log["some_key"] == "some_value"
```

### 5.2. Testing Metrics

> **Best Practice: Avoid Brittle Tests**
> When testing metrics, avoid asserting exact values (e.g., `...} 1`), which can be brittle. Instead, test for *changes* in metrics or use `>` comparisons. For logs, assert the *presence* of key fields and their values rather than matching an exact log string. This makes tests resilient to minor changes in log format or execution order.

* Integration tests should make requests to instrumented endpoints and then scrape a test client's `/metrics` endpoint to assert that the correct Prometheus counters/histograms have been incremented with the correct labels.
* To verify metrics, we will use the standard FastAPI `TestClient` to perform requests and then scrape the `/metrics` endpoint to check the values.

**Example Test:**
```python
from fastapi.testclient import TestClient

# client is a pytest fixture providing a TestClient instance
def test_metrics_increment_on_request(client: TestClient):
    # 1. Get initial metric value (optional, but good for robustness)
    response_before = client.get("/metrics")
    assert response_before.status_code == 200
    # A helper function to parse Prometheus text format would be useful here
    # For simplicity, we'll use string checking
    assert 'http_requests_total{method="GET",path="/my-endpoint"} 0' in response_before.text

    # 2. Make a request to the endpoint being measured
    client.get("/my-endpoint")

    # 3. Get updated metric value and assert it has changed
    response_after = client.get("/metrics")
    assert response_after.status_code == 200
    assert 'http_requests_total{method="GET",path="/my-endpoint"} 1' in response_after.text
```
