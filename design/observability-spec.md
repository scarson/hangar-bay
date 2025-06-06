# Hangar Bay - Observability Specification

## 1. Introduction

This document outlines the observability strategy for the Hangar Bay application. Comprehensive observability is crucial for understanding application behavior, diagnosing issues, monitoring performance, and ensuring reliability. It complements the security-focused logging detailed in `security-spec.md`.

## 2. Pillars of Observability

### 2.1. Logging
*   **Structured Logging:** All application logs (backend and frontend) MUST be structured (e.g., JSON format).
    *   **Benefits:** Easier parsing, searching, and analysis by log management systems.
*   **Log Levels:** Implement standard log levels (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).
    *   Allow configurable log levels per environment.
*   **Correlation IDs & Context Propagation:** Generate/propagate a correlation ID (e.g., trace ID from OpenTelemetry) for each incoming request (or initiated task) across all services and log messages. Ensure context propagation mechanisms (ideally OpenTelemetry-native) are used.
*   **Key Information to Log:** Timestamp, log level, service name, correlation ID, message, and relevant context (e.g., endpoint, user ID if authenticated, ESI request details - sanitizing sensitive info).
*   **Security:** Sensitive data (passwords, raw ESI tokens) MUST NOT be logged. Refer to `security-spec.md`.

    *   **AI Implementation Pattern (Structured Logging - Python/FastAPI):**
        *   Instruct AI to use Python's `logging` module configured with a JSON formatter (e.g., `python-json-logger`).
        *   Example prompt: "Configure FastAPI logging to output JSON logs including timestamp, level, message, and logger name. Add a middleware to log request details (method, path, status code, duration) and include a correlation ID."
        *   Ensure AI includes `correlation_id` in all log records related to a request.

    *   **AI Implementation Pattern (Correlation ID - FastAPI Middleware with OpenTelemetry):**
        *   If OpenTelemetry is used, the trace ID can serve as the correlation ID.
        *   AI should be prompted to add middleware that extracts the trace ID from the current OpenTelemetry span and makes it available for logging contexts.
        *   Example: `from opentelemetry import trace; tracer = trace.get_tracer(__name__); span = trace.get_current_span(); correlation_id = span.get_span_context().trace_id; logger.info("message", extra={"correlation_id": hex(correlation_id)})` (Simplified, actual integration would be more robust).

### 2.2. Metrics
*   **Application Metrics (Backend - FastAPI):**
    *   Request rate, error rate, latency (overall and per-endpoint).
    *   ESI API interaction metrics: call count, error rate, latency per ESI endpoint.
    *   Database query performance: execution time, error rate per query type.
    *   Cache performance: hit/miss ratio, latency.
    *   Task queue metrics (for alerts): queue length, task processing time, error rate.
    *   *Note: Refer to `performance-spec.md` for specific target values for latencies and processing times.*
*   **Frontend Metrics (Angular):**
    *   Page load times, component interaction times.
    *   Client-side error rates.
    *   API call latency from client perspective.
    *   *Note: Refer to `performance-spec.md` for specific target values for frontend performance metrics (FCP, LCP, TTI, INP).*
*   **System Metrics:** CPU usage, memory usage, disk I/O, network traffic for application hosts/containers.
*   **Business Metrics (High-Level):**
    *   Number of active users (if SSO implemented).
    *   Number of contracts processed/displayed.
    *   Watchlist creation/alert triggering frequency.

    *   **AI Implementation Pattern (Backend Metrics - FastAPI with Prometheus):**
        *   Instruct AI to use a Prometheus client library (e.g., `starlette-exporter` or `prometheus-fastapi-instrumentator`) to expose standard metrics (request count, latency, errors by path/status).
        *   For custom metrics (e.g., ESI call latency): `my_custom_metric = Summary('my_metric_seconds', 'Description of my metric'); @my_custom_metric.time() def my_function(): ...`
        *   AI should add relevant labels (e.g., ESI endpoint path) to custom metrics.

    *   **AI Implementation Pattern (Frontend Metrics - Angular with OpenTelemetry):**
        *   If using OpenTelemetry for tracing, it can also collect basic frontend performance metrics.
        *   For custom metrics (e.g., component interaction time), AI can be prompted to use OpenTelemetry Metrics API or a simple custom solution sending data to a backend endpoint for aggregation if OpenTelemetry is not fully set up on frontend.
        *   Example prompt: "Instrument Angular `HttpClient` calls using OpenTelemetry to capture client-side API call latency."

### 2.3. Tracing (Distributed Tracing - OpenTelemetry Preferred)
*   **Goal:** To visualize the entire lifecycle of a request as it flows through different components of the application (e.g., frontend -> backend API -> ESI API -> database -> cache).
*   **Implementation:** Strongly prefer and prioritize the use of OpenTelemetry SDKs and APIs for instrumenting code and propagating trace context across all services (Python backend, Angular frontend if applicable).
*   **Benefits:** Pinpoint bottlenecks, understand service dependencies, debug complex issues in a distributed environment.

    *   **AI Implementation Pattern (Tracing - FastAPI with OpenTelemetry):**
        *   Instruct AI to use `opentelemetry-instrumentation-fastapi` to automatically trace incoming requests.
        *   For outgoing HTTP calls (e.g., to ESI): use `opentelemetry-instrumentation-httpx`.
        *   For database calls: use relevant OpenTelemetry instrumentation library (e.g., `opentelemetry-instrumentation-sqlalchemy`).
        *   AI should ensure trace context is propagated correctly.
        *   Example prompt: "Set up OpenTelemetry for a FastAPI application, instrumenting FastAPI, HTTPX, and SQLAlchemy. Configure an OTLP exporter."

    *   **AI Implementation Pattern (Tracing - Angular with OpenTelemetry):**
        *   Instruct AI to use `@opentelemetry/instrumentation-xml-http-request` and `@opentelemetry/instrumentation-fetch` for automatic tracing of API calls.
        *   Use `@opentelemetry/instrumentation-document-load` for page load traces.
        *   Configure trace context propagation (e.g., `W3CTraceContextPropagator`).
        *   Example prompt: "Set up OpenTelemetry for an Angular application to trace HTTP requests and page loads. Ensure trace context is propagated to the backend."

### 2.4. Error Tracking & Alerting (Operational)
*   **Centralized Error Aggregation:** Collect and aggregate exceptions and errors from both backend and frontend in a centralized system.
*   **Alerting:** Set up alerts for critical errors, unusual spikes in error rates, performance degradation (as defined by targets in `performance-spec.md`), or system resource exhaustion.
    *   Distinguish from user-facing application alerts (e.g., new contract found).

## 3. Tools and Technologies (Proposed - Emphasizing OpenTelemetry Compatibility)

*   **Logging Management:**
    *   *(Placeholder: e.g., ELK Stack, Grafana Loki, OpenTelemetry Collector with backends like Jaeger/Elasticsearch. Prioritize solutions with strong OpenTelemetry OTLP ingest capabilities.)*

        *   **AI Actionable Checklist (Logging Tooling):**
            *   [ ] When AI sets up logging, ensure logs are configured to be exportable/collectable by the chosen system.
            *   [ ] If using OpenTelemetry Collector, AI should generate a config for OTLP receiver and appropriate exporter (e.g., Loki, Elasticsearch).
*   **Metrics Collection & Visualization:**
    *   **Backend:** Prometheus client libraries for FastAPI. Consider OpenTelemetry SDKs for metrics as well, which can export to Prometheus.
    *   **System:** Prometheus Node Exporter or similar.
    *   **Storage & Visualization:** Prometheus (time-series database) & Grafana (dashboards).

        *   **AI Actionable Checklist (Metrics Tooling):**
            *   [ ] AI should ensure FastAPI app exposes a `/metrics` endpoint for Prometheus scraping.
            *   [ ] When AI defines Grafana dashboards (e.g., via IaC), ensure queries match exposed Prometheus metrics.
*   **Distributed Tracing:**
    *   **Instrumentation:** OpenTelemetry SDKs for Python (FastAPI) and JavaScript (Angular) are the primary choice.
    *   **Backend Collector/Storage:** An OpenTelemetry Collector is highly recommended for receiving, processing, and exporting telemetry data. Backends like Jaeger, Zipkin, Prometheus, or managed cloud services (e.g., AWS X-Ray, Google Cloud Trace, Azure Monitor) that support OpenTelemetry are preferred.

        *   **AI Actionable Checklist (Tracing Tooling):**
            *   [ ] AI should configure OpenTelemetry SDKs in both backend and frontend to export traces via OTLP (HTTP or gRPC) to an OpenTelemetry Collector or a compatible backend.
            *   [ ] If using an OpenTelemetry Collector, AI should generate its configuration (receivers, processors, exporters).
*   **Error Tracking:**
    *   *(Placeholder: e.g., Sentry, Rollbar, Elastic APM. Evaluate for OpenTelemetry integration capabilities, such as correlating errors with traces.)*

        *   **AI Actionable Checklist (Error Tracking Tooling):**
            *   [ ] When AI instruments error tracking (e.g., Sentry SDK), ensure trace IDs from OpenTelemetry are attached to error reports for correlation.
            *   Example prompt: "Integrate Sentry with FastAPI and OpenTelemetry, ensuring Sentry errors include the OpenTelemetry trace ID."

## 4. Observability by Design

*   Instrumentation for logging, metrics, and tracing should be considered during development, not as an afterthought.
*   Dashboards should be created to visualize key metrics and logs for different components and user flows.

## 5. CI/CD Integration

*   Ensure that observability configurations and instrumentation are part of the deployment pipeline.

*(This document will be updated as the tech stack is finalized and specific tools are chosen.)*
