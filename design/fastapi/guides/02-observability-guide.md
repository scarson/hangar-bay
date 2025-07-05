# FastAPI Observability Design Guide

## 1. Overview

This guide establishes the standards for observability within the Hangar Bay backend using **OpenTelemetry** as the foundation. Adhering to these standards ensures that our application is transparent, debuggable, and maintainable with industry-standard observability practices. The strategy covers five pillars:

-   **Structured Logging:** For event-based, queryable insights into application behavior with OpenTelemetry trace context.
-   **Metrics:** For aggregated, numerical data on performance and system health using OpenTelemetry metrics API.
-   **Distributed Tracing:** For end-to-end request flow visibility using OpenTelemetry tracing.
-   **Exception Handling:** For consistent error logging and response formatting with trace correlation.
-   **Testing:** To ensure our observability instrumentation is reliable and accurate.

## 2. Technology Stack, Chosen Libraries, & Rationale

Based on research and industry best practices, the following libraries have been selected for our observability stack:

*   **Structured Logging:** `structlog` + OpenTelemetry
    *   **Rationale:** `structlog` provides a powerful processor chain that allows for easy enrichment of logs with contextual data. When integrated with OpenTelemetry via a custom processor, it includes trace context in all logs, providing seamless correlation across the entire application stack without manual correlation ID management.
*   **Metrics:** OpenTelemetry Metrics API
    *   **Rationale:** OpenTelemetry provides a vendor-neutral, standardized approach to metrics collection. It offers automatic instrumentation for FastAPI, HTTPX, and SQLAlchemy, plus a flexible API for custom metrics. This ensures future-proof integration with any observability platform and eliminates vendor lock-in.
*   **Distributed Tracing:** OpenTelemetry Tracing API
    *   **Rationale:** OpenTelemetry provides automatic instrumentation for FastAPI, HTTPX, and SQLAlchemy, plus a simple API for custom spans. It ensures end-to-end traceability from frontend to backend to external services, with automatic context propagation via W3C Trace Context.
*   **Observability Infrastructure:** OpenTelemetry Collector + Prometheus  + Loki + Grafana
    *   **Rationale:** OpenTelemetry Collector acts as a unified data pipeline that receives, processes, and exports telemetry data to multiple destinations. This provides flexibility to send data to Prometheus (metrics), Grafana Loki (logs), and Grafana (visualization) while maintaining a single configuration point.

## 3. Structured Logging Strategy

### 3.1. Log Format and Correlation

*   All logs MUST be rendered as a single-line JSON object to ensure they are machine-parsable.
*   All logs MUST include OpenTelemetry span context for correlation.
*   No manual correlation IDs are used - all correlation is handled by OpenTelemetry span context.

> **Risk Mitigation: Trace Context Propagation**
> The OpenTelemetry trace context must be available in all contexts (API layer, service layer, background tasks). The implementation will leverage OpenTelemetry's automatic instrumentation and `structlog.contextvars` to ensure trace context is automatically propagated without manual intervention.

### 3.2. Core Configuration

> **Risk Mitigation: Performance Overhead**
> To prevent performance degradation in production, the logging configuration MUST be environment-aware. The log level will be dynamically set based on a `LOG_LEVEL` setting from the central `Settings` object (`core/config.py`), defaulting to `INFO` in production and `DEBUG` in development.

Logging will be configured centrally in the application startup logic. The configuration will use a processor chain to add timestamps, log levels, OpenTelemetry trace context, and render the final output as JSON.

```python
# Example configuration (to be placed in app/main.py or a config module)
import logging
import sys
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_observability():
    """Configures OpenTelemetry and structured logging for the application."""
    
    # Initialize OpenTelemetry FIRST
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter())
    )
    
    # Define OpenTelemetry integration processor (official structlog pattern)
    # https://www.structlog.org/en/stable/frameworks.html#opentelemetry
    def add_open_telemetry_spans(_, __, event_dict):
        """Add OpenTelemetry span context to log events."""
        span = trace.get_current_span()
        if not span.is_recording():
            event_dict["span"] = None
            return event_dict

        ctx = span.get_span_context()
        parent = getattr(span, "parent", None)

        event_dict["span"] = {
            "span_id": format(ctx.span_id, "016x"),
            "trace_id": format(ctx.trace_id, "032x"),
            "parent_span_id": None if not parent else format(parent.span_id, "016x"),
        }

        return event_dict
    
    # Configure structlog with OpenTelemetry trace context
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,        # 1. Merge context first
            structlog.stdlib.add_log_level,                 # 2. Add log level
            structlog.stdlib.add_logger_name,               # 3. Add logger name
            structlog.processors.TimeStamper(fmt="iso"),    # 4. Add timestamp
            structlog.processors.StackInfoRenderer(),       # 5. Add stack info
            structlog.processors.format_exc_info,           # 6. Format exceptions
            structlog.processors.add_log_level_number,      # 7. Add numeric log level
            structlog.processors.CallsiteParameterAdder(    # 8. Add call site info
                parameters=["funcName", "lineno", "module"]
            ),
            add_open_telemetry_spans,                       # 9. Add OpenTelemetry span context
            structlog.processors.JSONRenderer(),            # 10. Render to JSON LAST
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger to use structlog
    root_logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

def instrument_fastapi_app(app):
    """Instruments FastAPI app with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    # SQLAlchemy instrumentation will be added to the existing engine in db.py
    # See section 8.4 for complete setup instructions
```

### 3.3. Key Event Schema

When logging significant business events (e.g., a contract search), the log MUST include a consistent set of key-value pairs with OpenTelemetry trace context.

> **Warning: Prevent Sensitive Data Leakage**
> To prevent inadvertently logging sensitive information, **never log raw data objects** (e.g., entire Pydantic models, full request bodies). Always construct the log entry by explicitly including only the necessary, sanitized fields defined in the schema below.

-   `event`: A short, descriptive name for the event (e.g., `contract_search_executed`).
-   `success`: (boolean) `true` if the operation succeeded, `false` otherwise.
-   `duration_ms`: (float) The time taken for the operation in milliseconds.
-   `error_message`: (string, optional) The error message if `success` is `false`.
-   `search_terms`: (dict, optional) The specific parameters used in the search.
-   `results_count`: (int, optional) The number of results returned.
-   `span`: (object) OpenTelemetry span context containing:
    - `trace_id`: (string) OpenTelemetry trace ID for correlation
    - `span_id`: (string) OpenTelemetry span ID for correlation  
    - `parent_span_id`: (string, optional) Parent span ID for nested operations

**Example Log:**
```json
{
  "event": "contract_search_executed", 
  "success": true, 
  "duration_ms": 123.45, 
  "search_terms": {"type": "item_exchange", "location": "jita"}, 
  "results_count": 50, 
  "span": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "parent_span_id": null
  },
  "log_level": "info", 
  "timestamp": "2024-01-15T10:30:00.123Z"
}
```

## 4. Metrics Strategy

OpenTelemetry Metrics API will be used for all metrics collection. Metrics will be exported via OpenTelemetry Collector to Prometheus for storage and visualization.

Our metrics strategy is based on the **RED methodology**:
-   **Rate:** The number of requests per second (`http.server.requests`).
-   **Errors:** The number of requests resulting in server-side errors (`http.server.requests` with error status).
-   **Duration:** The distribution of request processing times (`http.server.duration`).

### 4.1. Default Metrics

OpenTelemetry automatic instrumentation will capture the following default metrics for all relevant API endpoints. These metrics provide a comprehensive view of application performance out-of-the-box:

*   `http.server.duration`: **Histogram** of request processing time.
*   `http.server.request.size`: **Histogram** of request sizes.
*   `http.server.response.size`: **Histogram** of response sizes.
*   `http.server.requests`: **Counter** for total requests.
*   `http.server.active_requests`: **Gauge** for requests currently in progress.

These metrics will be automatically labeled with `http.method`, `http.status_code`, `http.route`, and `http.scheme` to allow for detailed analysis.

### 4.2. Custom Metrics

Custom metrics will be defined using OpenTelemetry Metrics API in relevant services:

```python
import time
import httpx
from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram

# Create meters for different components
esi_meter = metrics.get_meter("esi_client")
db_meter = metrics.get_meter("database")

# Define custom metrics
esi_calls_total = esi_meter.create_counter(
    name="esi_api_calls_total",
    description="Total number of ESI API calls",
    unit="calls"
)

esi_call_duration = esi_meter.create_histogram(
    name="esi_api_call_duration_seconds",
    description="Duration of ESI API calls",
    unit="seconds"
)

# Use in services
def make_esi_call(endpoint: str):
    start_time = time.time()
    try:
        result = httpx.get(f"https://esi.evetech.net/{endpoint}")
        esi_calls_total.add(1, {"endpoint": endpoint, "status": str(result.status_code)})
        return result
    finally:
        duration = time.time() - start_time
        esi_call_duration.record(duration, {"endpoint": endpoint})
```

## 5. Distributed Tracing Strategy

OpenTelemetry provides automatic instrumentation for FastAPI, HTTPX, and SQLAlchemy, ensuring end-to-end traceability across the entire application stack.

### 5.1. Automatic Instrumentation

The following components will be automatically instrumented:

*   **FastAPI:** All HTTP requests and responses
*   **HTTPX:** All outgoing HTTP requests to external services (ESI API)
*   **SQLAlchemy:** All database queries and transactions

### 5.2. Custom Spans

Custom spans will be added for key business operations to provide detailed visibility into application logic:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def search_contracts(search_params: dict):
    """Search contracts with custom tracing."""
    with tracer.start_as_current_span("contract_search") as span:
        # Add search parameters as span attributes
        span.set_attribute("search.type", search_params.get("type"))
        span.set_attribute("search.location", search_params.get("location"))
        
        # Perform search operations
        with tracer.start_as_current_span("esi_contract_lookup"):
            contracts = fetch_contracts_from_esi(search_params)
        
        with tracer.start_as_current_span("database_filter"):
            filtered_contracts = filter_contracts_in_db(contracts, search_params)
        
        return filtered_contracts
```

### 5.3. Trace Context Propagation

OpenTelemetry automatically propagates trace context via W3C Trace Context headers (`traceparent`, `tracestate`) for all HTTP requests. This ensures seamless correlation between frontend and backend operations.

## 6. Exception Handling

FastAPI provides excellent built-in exception handling that automatically:
- Returns appropriate HTTP status codes for different error types
- Provides detailed validation error information in development
- Handles common exceptions with proper responses
- Logs exceptions through the configured logging system

### Leveraging FastAPI's Exception Handling with OpenTelemetry

When using OpenTelemetry, exceptions will automatically be logged with full context and trace correlation. The structured logging configuration ensures that:

1. **Structured Logging**: All exceptions are logged with `exc_info` for full stack traces
2. **Trace Correlation**: The trace context is automatically included via OpenTelemetry
3. **Consistent Format**: All error logs follow the same structured format as other application logs

### Optional: Custom Exception Handler

If you need custom error response formatting or have specific security requirements, you can optionally add a global exception handler:

```python
# In app/main.py - Add FIRST, before middleware (optional)
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog
from opentelemetry import trace

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Optional global exception handler for custom error response formatting.
    Only needed if you require specific error response structures or security policies.
    """
    # Get current span for trace context
    current_span = trace.get_current_span()
    
    # Use structlog to log the exception with trace context
    logger = structlog.get_logger("uvicorn.error")
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        error_message=str(exc),
        trace_id=format(current_span.get_span_context().trace_id, "032x"),
        span_id=format(current_span.get_span_context().span_id, "016x"),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )
```

### Testing Exception Handling

When testing exception scenarios, focus on verifying that exceptions are properly logged with structured data and trace context:

```python
@pytest.mark.asyncio
async def test_exception_logging_with_opentelemetry(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that exceptions are properly logged with structured data and trace context.
    """
    # Arrange: Mock service to raise exception
    mocker.patch(
        "fastapi_app.services.contract_service.list_contracts",
        side_effect=Exception("Critical database failure")
    )
    
    # Mock the logger to capture error calls
    mock_logger = mocker.patch("fastapi_app.services.contract_service.logger")
    
    # Act: Make request that triggers exception
    response = await client.get("/contracts/")
    
    # Assert: Verify FastAPI handles the exception appropriately
    assert response.status_code == 500
    
    # Verify structured error logging with trace context
    if mock_logger.error.called:
        log_call = mock_logger.error.call_args[1]
        assert "exc_info" in log_call
        assert "error_message" in log_call
        assert "trace_id" in log_call
        assert "span_id" in log_call
```

## 7. Testing Strategy

Observability testing is **mandatory** and must verify that structured logging, metrics instrumentation, distributed tracing, and exception handling work correctly with OpenTelemetry.

### 7.1. Core Testing Tools

*   **`pytest-mock`**: Essential for isolating and verifying logging behavior without actual I/O
*   **`httpx.AsyncClient`**: For making API requests in integration tests
*   **MockerFixture**: For mocking logger instances and capturing log calls
*   **OpenTelemetry testing utilities**: For verifying trace context propagation
*   **Metrics endpoint**: The `/metrics` endpoint for verifying OpenTelemetry metrics instrumentation

For complete testing infrastructure setup, see our [FastAPI Testing Strategies Guide](09-testing-strategies.md#observability-testing-a-mandatory-category).

### 7.2. Testing Structured Logging with OpenTelemetry Trace Context

Tests must verify that service functions emit logs conforming to the **Key Events Schema** with OpenTelemetry trace context.

```python
import pytest
from pytest_mock import MockerFixture
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_successful_request_logs_with_trace_context(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that successful operations generate structured logs 
    with OpenTelemetry trace context.
    """
    # Arrange: Mock the service logger to capture calls
    mock_logger = mocker.patch("fastapi_app.services.contract_service.logger")
    
    # Act: Trigger the operation
    response = await client.get("/contracts/")
    
    # Assert: Verify response and trace context compliance
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
    
    # Verify OpenTelemetry span context
    assert "span" in log_call
    span_data = log_call["span"]
    assert isinstance(span_data, dict)
    assert "trace_id" in span_data
    assert "span_id" in span_data
    assert isinstance(span_data["trace_id"], str)
    assert isinstance(span_data["span_id"], str)
    
    # Verify event-specific fields
    if "results_count" in log_call:
        assert isinstance(log_call["results_count"], int)
```

### 7.3. Testing OpenTelemetry Metrics

Tests must verify that API endpoints correctly record OpenTelemetry metrics with proper labels.

```python
@pytest.mark.asyncio
async def test_successful_request_records_opentelemetry_metrics(
    client: AsyncClient
):
    """
    Verify that API requests record OpenTelemetry metrics with correct labels.
    """
    # Act: Make request to instrumented endpoint
    response = await client.get("/contracts/")
    assert response.status_code == 200
    
    # Verify: Check metrics endpoint for proper instrumentation
    # Note: In a real implementation, you would check the OpenTelemetry Collector
    # or Prometheus endpoint for metrics
    metrics_response = await client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Verify OpenTelemetry metrics are present
    assert 'http_server_duration_bucket' in metrics_text
    assert 'http_server_requests_total' in metrics_text
    
    # Verify specific metrics with correct labels
    assert 'http_server_requests_total{http_method="GET",http_status_code="200"' in metrics_text
    assert 'http_server_duration_bucket{http_method="GET"' in metrics_text
    
    # Verify metrics are actually recorded (not just present)
    assert any('} 1.0' in line or '} 1' in line for line in metrics_text.split('\n') 
              if 'http_server_requests_total' in line)
```

### 7.4. Testing Distributed Tracing

Tests must verify that trace context is properly propagated across service boundaries:

```python
@pytest.mark.asyncio
async def test_trace_context_propagation(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that OpenTelemetry trace context is consistent across API and service layers.
    """
    # Arrange: Mock loggers from different layers
    api_mock = mocker.patch("fastapi_app.api.contracts.logger")
    service_mock = mocker.patch("fastapi_app.services.contract_service.logger")
    
    # Act: Make request that touches multiple layers
    response = await client.get("/contracts/")
    assert response.status_code == 200
    
    # Extract span context from both loggers
    api_span = api_mock.info.call_args[1].get("span", {})
    service_span = service_mock.info.call_args[1].get("span", {})
    
    # Verify: Same trace_id across all layers
    assert api_span.get("trace_id") is not None
    assert service_span.get("trace_id") is not None
    assert api_span.get("trace_id") == service_span.get("trace_id")
```

### 7.5. Testing Exception Handling with Trace Context

Tests must verify that exceptions are properly handled and logged with OpenTelemetry trace context:

```python
@pytest.mark.asyncio
async def test_failed_request_logs_with_trace_context(
    client: AsyncClient, 
    mocker: MockerFixture
):
    """
    Verify that server errors trigger proper exception handling and structured logging
    with OpenTelemetry trace context.
    """
    # Arrange: Mock service to raise exception
    mocker.patch(
        "fastapi_app.services.contract_service.list_contracts",
        side_effect=Exception("Critical database failure")
    )
    
    # Mock the service logger to capture error calls
    mock_logger = mocker.patch("fastapi_app.services.contract_service.logger")
    
    # Act: Make request that triggers exception
    response = await client.get("/contracts/")
    
    # Assert: Verify FastAPI handles the exception appropriately
    assert response.status_code == 500
    
    # Verify structured error logging with trace context
    # Note: FastAPI may handle the exception before it reaches the service
    if mock_logger.error.called:
        log_call = mock_logger.error.call_args[1]
        
        # Verify required error logging fields
        assert "exc_info" in log_call
        assert "error_message" in log_call
        assert "span" in log_call
        span_data = log_call["span"]
        assert "trace_id" in span_data
        assert "span_id" in span_data
        assert log_call["error_message"] == "Critical database failure"
```

### 7.6. Integration Testing with Observability Infrastructure

Tests must verify that telemetry data is properly exported to the observability infrastructure (Prometheus, Loki):

```python
import asyncio
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_metrics_exported_to_prometheus(
    client: AsyncClient,
    docker_services
):
    """
    Verify that OpenTelemetry metrics are properly exported to Prometheus.
    This test requires the observability infrastructure to be running.
    """
    # Act: Make request to generate metrics
    response = await client.get("/contracts/")
    assert response.status_code == 200
    
    # Wait for metrics to be exported
    await asyncio.sleep(2)
    
    # Verify: Check Prometheus endpoint for metrics
    prometheus_response = await client.get("http://localhost:9464/metrics")
    assert prometheus_response.status_code == 200
    metrics_text = prometheus_response.text
    
    # Verify OpenTelemetry metrics are present in Prometheus
    assert 'hangar_bay_http_server_requests_total' in metrics_text
    assert 'hangar_bay_http_server_duration_seconds' in metrics_text
    
    # Verify metrics have correct labels
    assert 'http_method="GET"' in metrics_text
    assert 'http_status_code="200"' in metrics_text

@pytest.mark.asyncio
async def test_logs_exported_to_loki(
    client: AsyncClient,
    docker_services
):
    """
    Verify that structured logs are properly exported to Loki.
    This test requires the observability infrastructure to be running.
    """
    # Act: Make request to generate logs
    response = await client.get("/contracts/")
    assert response.status_code == 200
    
    # Wait for logs to be exported
    await asyncio.sleep(2)
    
    # Verify: Check Loki endpoint for logs
    # Note: This is a simplified example. In practice, you would query Loki's API
    # to verify that logs with trace_id are present
    loki_response = await client.get("http://localhost:3100/ready")
    assert loki_response.status_code == 200
```

### 7.7. Best Practices for Observability Testing

> **Critical: Use pytest-mock for Isolation**
> Always use `pytest-mock` to isolate logging behavior. Never rely on actual log output or files, as this creates brittle tests and potential race conditions.

1. **Schema Compliance**: Always verify that logs match the defined Key Events schema with trace context
2. **Mock Isolation**: Use `pytest-mock` to isolate logging from actual I/O operations
3. **Trace Context Verification**: For all tests, verify that `trace_id` and `span_id` are present and consistent
4. **Label Verification**: For metrics tests, verify both presence and correct labeling
5. **Exception Scenarios**: Test both success and failure paths for complete coverage
6. **Correlation Testing**: Verify trace context propagation across service boundaries
7. **Integration Testing**: Verify telemetry data reaches observability infrastructure (Prometheus, Loki)

### 7.8. Integration with Main Testing Strategy

Observability tests should be integrated into the main test suite, not run separately. They use the same fixtures (`client`, `db_session`) as integration tests but focus specifically on telemetry verification.

For complete fixture setup and additional observability testing patterns, see the [FastAPI Testing Strategies Guide](09-testing-strategies.md).

## 8. OpenTelemetry Configuration

### 8.1. Dependencies

Add the following dependencies to `pyproject.toml`:

```toml
[tool.pdm.dev-dependencies]
opentelemetry-api = "^1.21.0"
opentelemetry-sdk = "^1.21.0"
opentelemetry-instrumentation-fastapi = "^0.42b0"
opentelemetry-instrumentation-httpx = "^0.42b0"
opentelemetry-instrumentation-sqlalchemy = "^0.42b0"
opentelemetry-exporter-otlp-proto-http = "^1.21.0"

```

### 8.2. OpenTelemetry Collector Configuration

The OpenTelemetry Collector is a vendor-neutral implementation for receiving, processing, and exporting telemetry data. It acts as a unified data pipeline that receives data from multiple sources (our FastAPI app) and exports it to multiple destinations (Prometheus for metrics, Loki for logs, Grafana for visualization).

Update the Docker Compose configuration to include OpenTelemetry Collector:

```yaml
# docker/compose.observability.yml
services:
  prometheus:
    image: prom/prometheus:v3.4.2
    container_name: hangar_bay_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'      
    networks:
      - hb-monitoring-net

  loki:
    image: grafana/loki:3.4.4
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes:
      - ./loki:/etc/loki
      - loki_data:/tmp/loki
    ports:
      - "3100:3100"
    networks:
      - hb-monitoring-net      

  grafana:
    image: grafana/grafana:12.0.2
    container_name: hangar_bay_grafana
    ports:
      - "3000:3000"
    environment:
      # Enable public dashboards for development - allows sharing dashboards without authentication
      # Useful for demos, external stakeholders, and development collaboration
      - GF_FEATURE_TOGGLES_ENABLE=publicDashboards      
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning/:/etc/grafana/provisioning/
    networks:
      - hb-monitoring-net


  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-collector/config.yaml"]
    volumes:
      - ./otel-collector:/etc/otel-collector
      - otel_data:/tmp/otel-collector
    ports:
      # - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    networks:
      - hb-monitoring-net
    depends_on:
      - prometheus
      - loki

volumes:
  prometheus_data: {}
  loki_data: {}
  grafana_data: {}
  otel_data: {}

# Note: Networks are defined in the main compose.yml file
# The hb-monitoring-net network is already configured there
```

### 8.3. Collector Configuration File

Create `docker/otel-collector/config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
    #  grpc:
    #    endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  prometheus:
    endpoint: "0.0.0.0:9464"
    namespace: "hangar_bay"
    # Note: service labels should be set per-service in application code, not globally here
    send_timestamps: true
    metric_expiration: 180m
    enable_open_metrics: true
    resource_to_telemetry_conversion:
      enabled: true

  loki:
    endpoint: "http://loki:3100/loki/api/v1/push"
    format: "json"
    tenant_id: "hangar-bay"

  logging:
    verbosity: detailed

  otlp:
    endpoint: "http://localhost:4318"
    # No TLS configuration needed for HTTP endpoints

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging, otlp]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus, logging]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [loki, logging]
```

### 8.4. Loki Configuration File

Create `docker/loki/config.yaml`:

```yaml
# This is a complete configuration to deploy Loki backed by the filesystem.
# The index will be shipped to the storage via tsdb-shipper.

auth_enabled: false

server:
  http_listen_port: 3100

common:
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
  replication_factor: 1
  path_prefix: /tmp/loki

schema_config:
  configs:
  - from: 2020-05-15
    store: tsdb
    object_store: filesystem
    schema: v13
    index:
      prefix: index_
      period: 24h

storage_config:
  filesystem:
    directory: /tmp/loki/chunks
```

### 8.5. Application Integration

Update the main application to use OpenTelemetry. **Note**: Each service (backend, frontend) should set its own service name in the resource configuration:

```python
# Backend (FastAPI) - app/main.py
resource = Resource.create({"service.name": "hangar-bay-backend"})

# Frontend (Angular) - will use:
# resource = Resource.create({"service.name": "hangar-bay-frontend"})
```

**SQLAlchemy Instrumentation**: The database engine in `db.py` is already configured. We add OpenTelemetry instrumentation to the existing engine to track database queries and performance.

Update the main application to use OpenTelemetry:

```python
# app/main.py
from fastapi import FastAPI
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPSpanExporterHTTP
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as OTLPMetricExporterHTTP

def setup_opentelemetry():
    """Configure OpenTelemetry for the application."""
    
    # Configure trace provider with service resource
    from opentelemetry.sdk.resources import Resource
    resource = Resource.create({"service.name": "hangar-bay-backend"})
    
    trace_provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporterHTTP(endpoint="http://localhost:4318/v1/traces")
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    trace.set_tracer_provider(trace_provider)
    
    # Configure metric provider with same service resource
    metric_provider = MeterProvider(resource=resource)
    otlp_metric_exporter = OTLPMetricExporterHTTP(endpoint="http://localhost:4318/v1/metrics")
    metric_provider.add_metric_reader(PeriodicExportingMetricReader(otlp_metric_exporter))
    metrics.set_meter_provider(metric_provider)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_opentelemetry()
    setup_observability()  # From section 3.2
    
    app = FastAPI(title="Hangar Bay API")
    
    # Instrument FastAPI with OpenTelemetry
    instrument_fastapi_app(app)  # From section 3.2
    
    # Add SQLAlchemy instrumentation to the existing engine
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from .db import async_engine
    
    # SQLAlchemy instrumentation works with the underlying sync engine
    SQLAlchemyInstrumentor().instrument(
        engine=async_engine.sync_engine,
        service="hangar-bay-backend"
    )
    
    # Add routes and middleware
    # ...
    
    return app
```

This configuration provides a complete OpenTelemetry-first observability solution that ensures end-to-end traceability, standardized metrics collection, and structured logging with automatic correlation across the entire application stack.
