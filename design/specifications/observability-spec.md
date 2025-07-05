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

    *   **AI Implementation Pattern (Structured Logging - Backend/FastAPI):**
        *   Instruct AI to use `structlog` for structured logging with JSON output.
        *   Example prompt: "Configure FastAPI with structlog for structured JSON logging. Add middleware for request ID generation and correlation. Ensure all logs include correlation_id and follow the Key Events schema."
        *   Ensure AI includes `correlation_id` in all log records related to a request.

    *   **AI Implementation Pattern (Structured Logging - Frontend/Angular):**
        *   Instruct AI to implement structured logging in Angular using a compatible library (e.g., `@angular/core` logging or custom structured logger).
        *   Example prompt: "Implement structured logging in Angular that matches backend format. Add HTTP interceptors for request ID propagation. Log user interactions, API calls, and errors with correlation IDs."
        *   Ensure frontend logs include the same correlation_id as corresponding backend requests.

    *   **AI Implementation Pattern (Correlation ID - End-to-End):**
        *   Backend generates request IDs (UUID v4) in `RequestIDMiddleware` and injects into structlog context.
        *   Frontend should extract request IDs from response headers and use for correlation.
        *   Both frontend and backend should log with the same request ID for end-to-end correlation.
        *   Example: Backend generates `request_id`, includes in response headers, frontend extracts and uses in all logs for that request.

    *   **Cross-Platform Logging Consistency:**
        *   Both frontend and backend must use the same structured log format.
        *   All logs must include: timestamp, level, correlation_id, event, and relevant context.
        *   Frontend logs should correlate with backend API calls using the same request ID.

### 2.2. Metrics
*   **Application Metrics (Backend - FastAPI):**
    *   Request rate, error rate, latency (overall and per-endpoint).
    *   ESI API interaction metrics: call count, error rate, latency per ESI endpoint.
    *   Database query performance: execution time, error rate per query type.
    *   Cache performance: hit/miss ratio, latency.
    *   Task queue metrics (for alerts): queue length, task processing time, error rate.
    *   *Note: Refer to `performance-spec.md` for specific target values for latencies and processing times.*
*   **Frontend Metrics (Angular):**
    *   **Core Web Vitals:** FCP, LCP, TTI, INP, CLS (refer to `performance-spec.md` for target values).
    *   **Angular-Specific Metrics:**
        *   Signal mutation frequency and performance.
        *   Change detection cycles (zoneless architecture).
        *   Component rendering times and lazy loading performance.
        *   HTTP request latency and error rates.
        *   Bundle loading times and code splitting effectiveness.
    *   **User Interaction Metrics:**
        *   Feature usage patterns and navigation flows.
        *   Component interaction times and user engagement.
        *   Error rates by feature and user action.
*   **System Metrics:** CPU usage, memory usage, disk I/O, network traffic for application hosts/containers.
*   **Business Metrics (High-Level):**
    *   Number of active users (if SSO implemented).
    *   Number of contracts processed/displayed.
    *   Watchlist creation/alert triggering frequency.
    *   Feature adoption rates and user journey completion.

    *   **AI Implementation Pattern (Backend Metrics - FastAPI with Prometheus):**
        *   Instruct AI to use a Prometheus client library (e.g., `starlette-exporter` or `prometheus-fastapi-instrumentator`) to expose standard metrics (request count, latency, errors by path/status).
        *   For custom metrics (e.g., ESI call latency): `my_custom_metric = Summary('my_metric_seconds', 'Description of my metric'); @my_custom_metric.time() def my_function(): ...`
        *   AI should add relevant labels (e.g., ESI endpoint path) to custom metrics.

    *   **AI Implementation Pattern (Frontend Metrics - Angular):**
        *   **Core Web Vitals:** Use Web Vitals library to capture and report Core Web Vitals metrics.
        *   **Angular Performance:** Implement custom metrics for signal performance, change detection, and component rendering.
        *   **HTTP Monitoring:** Use Angular HTTP interceptors to capture request/response metrics.
        *   **Bundle Performance:** Monitor lazy loading and code splitting performance.
        *   Example prompt: "Implement comprehensive frontend metrics in Angular including Core Web Vitals, signal performance, and HTTP request monitoring. Send metrics to backend endpoint for aggregation."

### 2.3. Tracing (Distributed Tracing - OpenTelemetry Preferred)
*   **Goal:** To visualize the entire lifecycle of a request as it flows through different components of the application (e.g., frontend -> backend API -> ESI API -> database -> cache).
*   **Implementation:** Strongly prefer and prioritize the use of OpenTelemetry SDKs and APIs for instrumenting code and propagating trace context across all services (Python backend, Angular frontend).
*   **Benefits:** Pinpoint bottlenecks, understand service dependencies, debug complex issues in a distributed environment.
*   **Frontend Considerations:** Angular's zoneless architecture and signal-based reactivity require special attention for tracing implementation.

    *   **AI Implementation Pattern (Tracing - FastAPI with OpenTelemetry):**
        *   Instruct AI to use `opentelemetry-instrumentation-fastapi` to automatically trace incoming requests.
        *   For outgoing HTTP calls (e.g., to ESI): use `opentelemetry-instrumentation-httpx`.
        *   For database calls: use relevant OpenTelemetry instrumentation library (e.g., `opentelemetry-instrumentation-sqlalchemy`).
        *   AI should ensure trace context is propagated correctly.
        *   Example prompt: "Set up OpenTelemetry for a FastAPI application, instrumenting FastAPI, HTTPX, and SQLAlchemy. Configure an OTLP exporter."

    *   **AI Implementation Pattern (Tracing - Angular with OpenTelemetry):**
        *   **HTTP Tracing:** Use `@opentelemetry/instrumentation-xml-http-request` and `@opentelemetry/instrumentation-fetch` for automatic tracing of API calls.
        *   **Page Load Tracing:** Use `@opentelemetry/instrumentation-document-load` for page load traces.
        *   **Signal Tracing:** Implement custom tracing for signal mutations and change detection cycles.
        *   **Zoneless Considerations:** Ensure tracing works correctly in zoneless Angular without zone.js interference.
        *   **Context Propagation:** Configure trace context propagation (e.g., `W3CTraceContextPropagator`) for end-to-end correlation.
        *   Example prompt: "Set up OpenTelemetry for a zoneless Angular application to trace HTTP requests, signal mutations, and page loads. Ensure trace context is propagated to the backend."

### 2.4. Error Tracking & Alerting (Operational)
*   **Centralized Error Aggregation:** Collect and aggregate exceptions and errors from both backend and frontend in a centralized system.
*   **Frontend Error Considerations:**
    *   **Signal Errors:** Track errors in signal mutations and computed signal evaluations.
    *   **Component Errors:** Monitor component rendering errors and lifecycle issues.
    *   **HTTP Errors:** Correlate frontend HTTP errors with backend API errors.
    *   **User Interaction Errors:** Track errors related to user actions and form submissions.
*   **Alerting:** Set up alerts for critical errors, unusual spikes in error rates, performance degradation (as defined by targets in `performance-spec.md`), or system resource exhaustion.
    *   Distinguish from user-facing application alerts (e.g., new contract found).

## 3. Tools and Technologies (Proposed - Emphasizing OpenTelemetry Compatibility)

*   **Logging Management:**
    *   *(Placeholder: e.g., ELK Stack, Grafana Loki, structured log aggregation. Prioritize solutions with strong JSON log ingest capabilities.)*

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

## 4. Frontend Observability Implementation

### 4.1. Angular-Specific Considerations

*   **Zoneless Architecture Impact:**
    *   Traditional Angular observability patterns may not work correctly without zone.js.
    *   Signal-based change detection requires custom instrumentation for performance monitoring.
    *   SSR/SSG observability must account for server-side rendering and hydration processes.

*   **HTTP Interceptor Requirements:**
    *   **Request ID Generation:** Generate UUID v4 request IDs for all HTTP requests.
    *   **Header Injection:** Inject request IDs into headers (e.g., `X-Request-ID`) for backend correlation.
    *   **Error Correlation:** Ensure frontend errors include the same request ID as corresponding backend requests.
    *   **Performance Monitoring:** Track request/response times and correlate with backend metrics.

*   **Signal-Based Observability:**
    *   **Mutation Tracking:** Monitor signal mutation frequency and patterns.
    *   **Performance Monitoring:** Track computed signal evaluation times and effect execution.
    *   **Error Propagation:** Monitor signal error propagation through the application.
    *   **Memory Leaks:** Detect potential memory leaks in signal subscriptions and effects.

### 4.2. Frontend Testing Strategy

*   **Observability Testing:** Frontend observability must be tested to ensure proper correlation with backend.
*   **Performance Testing:** Test signal performance and change detection in zoneless environment.
*   **Integration Testing:** Verify end-to-end request correlation between frontend and backend.
*   **Error Simulation:** Test error handling and correlation across frontend/backend boundaries.

## 5. Observability by Design

*   Instrumentation for logging, metrics, and tracing should be considered during development, not as an afterthought.
*   Dashboards should be created to visualize key metrics and logs for different components and user flows.
*   Frontend and backend observability should be designed together to ensure proper correlation and end-to-end visibility.

## 6. CI/CD Integration

*   Ensure that observability configurations and instrumentation are part of the deployment pipeline.

*(This document will be updated as the tech stack is finalized and specific tools are chosen.)*
