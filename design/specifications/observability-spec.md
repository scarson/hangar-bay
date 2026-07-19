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

    *   **Log Formatting (Application Baseline):**
        *   **Standard Format:** To ensure readability and a degree of consistency with Uvicorn's default log output, a baseline format is established for application logs generated via Python's `logging` module.
        *   **Format String:** `%(levelname)s:     %(name)s - %(message)s`
        *   **Implementation:** This format is applied globally to the root logger in `app/backend/src/fastapi_app/main.py` using `logging.basicConfig(level=logging.INFO, format='%(levelname)s:     %(name)s - %(message)s')`.
        *   **Rationale:** This provides improved readability by aligning the log level prefix (e.g., `INFO:     `) and clearly separating the logger name from the log message. While full structured logging (e.g., JSON) is the ultimate goal (see above), this basic formatting improves immediate usability of console logs.
        *   **AI Implementation Guidance:** When modifying or extending logging, AI should adhere to this baseline format for non-structured console output unless a specific structured logging formatter (e.g., JSON) is being implemented for that handler.

### 2.2. Metrics
*   **Application Metrics (Backend - FastAPI):**
    *   Request rate, error rate, latency (overall and per-endpoint).
    *   ESI API interaction metrics: call count, error rate, latency per ESI endpoint.
    *   Database query performance: execution time, error rate per query type.
    *   Cache performance: hit/miss ratio, latency.
    *   Task queue metrics (for alerts): queue length, task processing time, error rate.
    *   *Note: Refer to `performance-spec.md` for specific target values for latencies and processing times.*
*   **Frontend Metrics (React):**
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

    *   **AI Implementation Pattern (Frontend Metrics - React with OpenTelemetry):** *(No frontend telemetry is wired into the React app yet — this remains a target to be defined for the React stack.)*
        *   If using OpenTelemetry for tracing, it can also collect basic frontend performance metrics.
        *   For custom metrics (e.g., component interaction time), AI can be prompted to use the OpenTelemetry Metrics API or a simple custom solution sending data to a backend endpoint for aggregation if OpenTelemetry is not fully set up on the frontend.
        *   Example prompt: "Instrument the `openapi-fetch` API client (`src/lib/api/client.ts`) — or wrap TanStack Query's `fetch` — using OpenTelemetry to capture client-side API call latency."

### 2.3. Tracing (Distributed Tracing - OpenTelemetry Preferred)
*   **Goal:** To visualize the entire lifecycle of a request as it flows through different components of the application (e.g., frontend -> backend API -> ESI API -> database -> cache).
*   **Implementation:** Strongly prefer and prioritize the use of OpenTelemetry SDKs and APIs for instrumenting code and propagating trace context across all services (Python backend, React frontend if applicable).
*   **Benefits:** Pinpoint bottlenecks, understand service dependencies, debug complex issues in a distributed environment.

    *   **AI Implementation Pattern (Tracing - FastAPI with OpenTelemetry):**
        *   Instruct AI to use `opentelemetry-instrumentation-fastapi` to automatically trace incoming requests.
        *   For outgoing HTTP calls (e.g., to ESI): use `opentelemetry-instrumentation-httpx`.
        *   For database calls: use relevant OpenTelemetry instrumentation library (e.g., `opentelemetry-instrumentation-sqlalchemy`).
        *   AI should ensure trace context is propagated correctly.
        *   Example prompt: "Set up OpenTelemetry for a FastAPI application, instrumenting FastAPI, HTTPX, and SQLAlchemy. Configure an OTLP exporter."

    *   **AI Implementation Pattern (Tracing - React with OpenTelemetry):** *(Not yet wired into the React app — a target to be defined for the React stack. The browser instrumentation packages below are framework-agnostic and apply as-is.)*
        *   Instruct AI to use `@opentelemetry/instrumentation-fetch` (the app uses `fetch` via `openapi-fetch`) for automatic tracing of API calls.
        *   Use `@opentelemetry/instrumentation-document-load` for page load traces.
        *   Configure trace context propagation (e.g., `W3CTraceContextPropagator`).
        *   Example prompt: "Set up OpenTelemetry for a React (Vite) application to trace `fetch` requests and page loads. Ensure trace context is propagated to the backend."

### 2.4. Error Tracking & Alerting (Operational)
*   **Centralized Error Aggregation:** Collect and aggregate exceptions and errors from both backend and frontend in a centralized system.
*   **Alerting:** Set up alerts for critical errors, unusual spikes in error rates, performance degradation (as defined by targets in `performance-spec.md`), or system resource exhaustion.
    *   Distinguish from user-facing application alerts (e.g., new contract found).

### 2.5. Health, Readiness & Upstream (ESI) Status

The application currently exposes a single static liveness stub — `GET /health` returns `{"status": "ok"}` unconditionally (`app/backend/src/fastapi_app/main.py`). It confirms the process is up; it does NOT report readiness (dependencies reachable) or data freshness. The following are deferred enhancements, ordered by value. None are required for the current stage (no production deployment yet); each becomes worthwhile as Hangar Bay moves toward a real deploy.

*   **Meaningful readiness probe.** Distinguish *liveness* (the process is running) from *readiness* (it can serve correct responses). A readiness check SHOULD verify the PostgreSQL connection and the Valkey cache are reachable, and SHOULD report the age of the last successful ESI ingestion (see below). Keep liveness cheap and dependency-free so an orchestrator does not kill an instance over a transient DB blip; put dependency checks behind readiness. Because reads are served from the local database, ESI being down does NOT make the app unready — it makes its data stale, which is a distinct signal handled next.

*   **Ingestion freshness / data-staleness indicator.** Hangar Bay's real failure mode under an ESI outage is *stale data*, not downtime: the aggregation job (`services/background_aggregation.py`) stops refreshing while the API keeps serving the last-ingested contracts. The system SHOULD record the timestamp (and outcome) of the last successful aggregation run — per region and/or globally — and surface staleness both operationally (a metric/alert when the last success exceeds the expected cadence) and to users (a "contract data may be stale" indicator in the SPA). This is the user-facing complement to the ESI-interaction metrics already listed in §2.2, and relates to F001 (Public Contract Aggregation & Display).

*   **ESI upstream health via `/meta/status`.** ESI publishes per-route health at `https://esi.evetech.net/meta/status` with status values `OK` / `Degraded` / `Down` / `Recovering`. Two concrete uses: (1) a scheduler pre-flight — skip or defer an ingestion run (and widen backoff) when the contracts routes report `Down`, rather than fanning dozens of region requests into a struggling API; (2) a data source for the staleness indicator above. This is an *enhancement*, not a prerequisite: the ESI client already observes ground-truth health first-hand via its own 5XX/timeout retry-and-backoff on the exact routes it depends on (`core/esi_client_class.py`), so `/meta/status` adds a coarser, predictive, cross-route signal rather than new primary information. Gate the work on a real production deploy plus the freshness surface existing first.
    *   **MUST target `/meta/status`, never `/status.json`.** ESI's legacy `/status.json` route was removed on 24 March 2026 (ESI dev blog, "Spring Cleaning: legacy routes removed 24 March 2026", https://developers.eveonline.com/blog/spring-cleaning-legacy-routes-removed-24-march-2026); `/meta/status` is its replacement ("A better view on status: improving ESI health monitoring", https://developers.eveonline.com/blog/a-better-view-on-status-improving-esi-health-monitoring). Any status integration built against the old route is dead on arrival. See ESI-1 in `docs/pitfalls/implementation-pitfalls.md`.

## 3. Tools and Technologies (Proposed - Emphasizing OpenTelemetry Compatibility)

*   **Logging Management:**
    *   **Chosen (2026-07-18):** Grafana Cloud Loki. The backend's structlog JSON output is duplicated to a file (`LOG_FILE` setting) that a Grafana Alloy container tails and pushes to the managed Loki instance (see `app/backend/docker/compose.observability.yml`).

        *   **AI Actionable Checklist (Logging Tooling):**
            *   [ ] When AI sets up logging, ensure logs are configured to be exportable/collectable by the chosen system.
            *   [ ] If using OpenTelemetry Collector, AI should generate a config for OTLP receiver and appropriate exporter (e.g., Loki, Elasticsearch).
*   **Metrics Collection & Visualization:**
    *   **Backend:** Prometheus client libraries for FastAPI. Consider OpenTelemetry SDKs for metrics as well, which can export to Prometheus.
    *   **System:** Prometheus Node Exporter or similar.
    *   **Storage & Visualization:** Grafana Cloud (managed Prometheus/Mimir + Grafana, org `scarson`), fed by a local Grafana Alloy collector scraping `/metrics`. Dashboards are committed JSON (`app/backend/observability/dashboards/`) provisioned via `pdm run provision-dashboards`. (Replaced the self-hosted Prometheus+Grafana compose stack, 2026-07-18.)

        *   **AI Actionable Checklist (Metrics Tooling):**
            *   [ ] AI should ensure FastAPI app exposes a `/metrics` endpoint for Prometheus scraping.
            *   [ ] When AI defines Grafana dashboards (e.g., via IaC), ensure queries match exposed Prometheus metrics.
*   **Distributed Tracing:**
    *   **Instrumentation:** OpenTelemetry SDKs for Python (FastAPI) and JavaScript/TypeScript (React) are the primary choice.
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
