# Hangar Bay - Observability Specification

## 1. Introduction

This document defines the observability strategy for the Hangar Bay application. **OpenTelemetry** is the default and only approach for all logging, metrics, and tracing across both backend (FastAPI) and frontend (Angular). This ensures end-to-end, industry-standard observability, correlation, and future-proof integration with modern tooling. All correlation is performed via OpenTelemetry trace context (`trace_id`, `span_id`).

## 2. Pillars of Observability

### 2.1. Logging (OpenTelemetry-Integrated)
*   **Structured Logging:** All logs (backend and frontend) MUST be structured (JSON format) and include OpenTelemetry trace context (`trace_id`, `span_id`).
    *   **Benefits:** Enables seamless correlation, parsing, and analysis by log management systems and observability platforms.
*   **Log Levels:** Use standard log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL). Configurable per environment.
*   **Trace Context Propagation:** All log records must include OpenTelemetry trace context. No manual correlation IDs are used.
*   **Key Information to Log:** Timestamp, log level, service name, `trace_id`, `span_id`, message, and relevant context (endpoint, user ID if authenticated, ESI request details - sanitized).
*   **Security:** Sensitive data (passwords, raw ESI tokens) MUST NOT be logged. See `security-spec.md`.
*   **Trace Context Explanation:** 
    *   `trace_id`: Unique identifier for an entire request flow (e.g., user action triggering multiple API calls)
    *   `span_id`: Unique identifier for a specific operation within that flow (e.g., database query, ESI API call)
    *   A trace contains multiple spans, all sharing the same `trace_id` but with different `span_id`s

    *   **AI Implementation Pattern (Backend/FastAPI Logging):**
        *   Use `structlog` configured with a processor that injects OpenTelemetry trace context into every log record.
        *   Example prompt: "Configure FastAPI with structlog for structured JSON logging. Integrate OpenTelemetry trace context (`trace_id`, `span_id`) into all logs."
        *   All logs must include `trace_id` and `span_id` fields.

    *   **AI Implementation Pattern (Frontend/Angular Logging):**
        *   Implement structured logging in Angular. Use OpenTelemetry JS SDK to propagate trace context and include `trace_id`/`span_id` in all logs.
        *   Log user interactions, API calls, and errors with trace context correlation.
        *   Add HTTP interceptors for trace context propagation.
        *   Example prompt: "Implement structured logging in Angular using OpenTelemetry. Ensure all logs include the current trace context (`trace_id`, `span_id`). Add HTTP interceptors for trace propagation. Log user interactions, API calls, and errors with trace correlation."

    *   **Cross-Platform Logging Consistency:**
        *   Both frontend and backend must use the same structured log format and include OpenTelemetry trace context.
        *   All logs must include: timestamp, level, `trace_id`, `span_id`, event, and relevant context.
        *   Logs from both frontend and backend can be correlated using `trace_id`.

### 2.2. Metrics (OpenTelemetry-Integrated)
*   **Application Metrics (Backend - FastAPI):**
    *   Use OpenTelemetry metrics API for all custom and standard metrics:
        *   Request rate, error rate, latency (overall and per-endpoint)
        *   ESI API interaction metrics: call count, error rate, latency per ESI endpoint
        *   Database query performance: execution time, error rate per query type
        *   Cache performance: hit/miss ratio, latency
        *   Task queue metrics (for alerts): queue length, task processing time, error rate
    *   Export metrics via OpenTelemetry Collector to Prometheus.
    *   *Note: Refer to `performance-spec.md` for specific target values for latencies and processing times.*
*   **Frontend Metrics (Angular):**
    *   Use OpenTelemetry JS SDK for all frontend metrics:
        *   **Core Web Vitals:** FCP, LCP, TTI, INP, CLS (refer to `performance-spec.md` for target values)
        *   **Angular-Specific Metrics:**
            *   Signal mutation frequency and performance
            *   Change detection cycles (zoneless architecture)
            *   Component rendering times and lazy loading performance
            *   HTTP request latency and error rates
            *   Bundle loading times and code splitting effectiveness
        *   **User Interaction Metrics:**
            *   Feature usage patterns and navigation flows
            *   Component interaction times and user engagement
            *   Error rates by feature and user action
    *   Correlate metrics with traces using `trace_id`.
*   **System Metrics:** Use Prometheus Node Exporter for host/container metrics. Correlate with application metrics via OpenTelemetry trace context.
*   **Business Metrics (High-Level):**
    *   Number of active users
    *   Number of contracts processed/displayed
    *   Watchlist creation/alert triggering frequency
    *   Feature adoption rates and user journey completion
    *   Instrument business events using OpenTelemetry metrics API

    *   **AI Implementation Pattern (Backend Metrics):**
        *   Use OpenTelemetry metrics API for all metrics. Export via OpenTelemetry Collector to Prometheus.
        *   For custom metrics (e.g., ESI call latency): Use OpenTelemetry metrics API with appropriate labels (e.g., ESI endpoint path).
        *   AI should add relevant labels to custom metrics for proper categorization.
        *   Example prompt: "Instrument FastAPI with OpenTelemetry metrics. Export via OpenTelemetry Collector to Prometheus. Add custom metrics for ESI calls with appropriate labels."

    *   **AI Implementation Pattern (Frontend Metrics):**
        *   Use OpenTelemetry JS SDK for all frontend metrics. Correlate with traces using `trace_id`.
        *   Example prompt: "Instrument Angular with OpenTelemetry metrics. Ensure all metrics are correlated with traces using `trace_id`."

### 2.3. Tracing (OpenTelemetry-Only)
*   **Distributed Tracing:** All request flows (frontend → backend → ESI API → DB → cache) must be traced using OpenTelemetry.
*   **Trace Context Propagation:** Use W3C Trace Context (`traceparent` header) for all HTTP requests between frontend and backend.
*   **Automatic Instrumentation:** Use OpenTelemetry instrumentation for FastAPI, HTTPX, SQLAlchemy, and Angular HTTP.
*   **Custom Spans:** Add custom spans for key business operations as needed.
*   **Correlation:** All logs and metrics must be correlated with traces using `trace_id` and `span_id`.

    *   **AI Implementation Pattern (Backend Tracing):**
        *   Use `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, and `opentelemetry-instrumentation-sqlalchemy` for automatic tracing.
        *   Add custom spans for business logic using OpenTelemetry API.
        *   Example prompt: "Instrument FastAPI with OpenTelemetry tracing. Add custom spans for key service methods. Ensure all logs and metrics are correlated with traces."

    *   **AI Implementation Pattern (Frontend Tracing):**
        *   Use OpenTelemetry JS SDK for HTTP, page load, and custom spans in Angular.
        *   **HTTP Tracing:** Use `@opentelemetry/instrumentation-xml-http-request` and `@opentelemetry/instrumentation-fetch` for automatic tracing of API calls.
        *   **Page Load Tracing:** Use `@opentelemetry/instrumentation-document-load` for page load traces.
        *   **Signal Tracing:** Implement custom tracing for signal mutations and change detection cycles.
        *   **Zoneless Considerations:** Ensure tracing works correctly in zoneless Angular without zone.js interference.
        *   **Context Propagation:** Configure trace context propagation (e.g., `W3CTraceContextPropagator`) for end-to-end correlation.
        *   Propagate trace context to backend via `traceparent` header.
        *   Example prompt: "Set up OpenTelemetry for a zoneless Angular application to trace HTTP requests, signal mutations, and page loads. Ensure trace context is propagated to the backend. Correlate all logs and metrics with traces."

### 2.4. Error Tracking & Alerting
*   **Error Logging:** All exceptions and errors (backend and frontend) must be logged with OpenTelemetry trace context attached.
*   **Frontend Error Considerations:**
    *   Track errors in signals, component rendering, HTTP, and user interactions. Attach trace context to all error logs.
*   **Alerting:** Set up alerts for critical errors, spikes in error rates, performance degradation, or resource exhaustion. Use OpenTelemetry metrics and Prometheus alerting.
*   **Future Enhancement:** Consider centralized error tracking (e.g., Sentry, Grafana Tempo) for advanced error analysis and correlation.

    *   **AI Implementation Pattern (Error Tracking):**
        *   Ensure all errors are logged with OpenTelemetry trace context (`trace_id`, `span_id`) for correlation.
        *   Configure Prometheus alerting for error rate thresholds.
        *   Example prompt: "Implement error logging with OpenTelemetry trace context in FastAPI and Angular. Configure Prometheus alerting for error rates."

## 3. Tools and Technologies (OpenTelemetry-First)

*   **Logging Management:**
    *   Use **Grafana Loki** for log aggregation. Loki supports JSON logs with OpenTelemetry trace context.
    *   All logs must be exportable and parsable with `trace_id` and `span_id` fields.
    *   Configure OpenTelemetry Collector to export logs to Loki via OTLP.

        *   **AI Actionable Checklist (Logging Tooling):**
            *   [ ] Configure structlog (backend) and frontend logger to include OpenTelemetry trace context in all logs.
            *   [ ] Configure OpenTelemetry Collector with Loki exporter for log aggregation.
            *   [ ] Ensure logs are exportable to Loki via OTLP.

*   **Metrics Collection & Visualization:**
    *   **Backend:** Use OpenTelemetry metrics API. Export via OpenTelemetry Collector to Prometheus.
    *   **Frontend:** Use OpenTelemetry JS SDK for metrics. Export via OpenTelemetry Collector to Prometheus.
    *   **System:** Prometheus Node Exporter for host/container metrics.
    *   **Storage:** Prometheus (time-series database).
    *   **Visualization:** Grafana dashboards for all metrics.

        *   **AI Actionable Checklist (Metrics Tooling):**
            *   [ ] Instrument all metrics using OpenTelemetry APIs.
            *   [ ] Configure OpenTelemetry Collector to export metrics to Prometheus.
            *   [ ] Configure Prometheus Node Exporter for system metrics.
            *   [ ] Ensure Grafana dashboards are configured for all key metrics.

*   **Distributed Tracing:**
    *   **Instrumentation:** Use OpenTelemetry SDKs for Python (FastAPI) and JavaScript (Angular).
    *   **Collector/Storage:** Use OpenTelemetry Collector for ingest, processing, and export. Use Grafana for trace visualization (Jaeger can be added later for advanced trace analysis).

        *   **AI Actionable Checklist (Tracing Tooling):**
            *   [ ] Instrument all services and frontend with OpenTelemetry tracing.
            *   [ ] Ensure trace context is propagated end-to-end (frontend to backend to DB/cache).
            *   [ ] Configure OpenTelemetry Collector to export traces for visualization.
            *   [ ] Configure Grafana for basic trace visualization (Jaeger integration can be added later).

*   **Error Tracking:**
    *   Use structured error logging with OpenTelemetry trace context. All error logs must include `trace_id` and `span_id` for correlation.
    *   Use Prometheus alerting for error rate monitoring.
    *   *Future: Consider centralized error tracking (Sentry, Grafana Tempo) for advanced error analysis.*

        *   **AI Actionable Checklist (Error Tracking Tooling):**
            *   [ ] Ensure all errors are logged with OpenTelemetry trace context (`trace_id`, `span_id`).
            *   [ ] Configure Prometheus alerting for error rate thresholds.
            *   [ ] Set up error rate dashboards in Grafana.

## 4. Frontend Observability Implementation (OpenTelemetry-First)

### 4.1. Angular-Specific Considerations

*   **Zoneless Architecture Impact:**
    *   Traditional Angular observability patterns may not work correctly without zone.js.
    *   Use OpenTelemetry JS SDK for all tracing and metrics. Ensure compatibility with zoneless Angular.
    *   Signal-based change detection requires custom instrumentation for performance monitoring.
    *   SSR/SSG observability must account for server-side rendering and hydration processes.
*   **HTTP Interceptor Requirements:**
    *   Use OpenTelemetry HTTP instrumentation. Propagate trace context via `traceparent` header.
    *   Correlate all logs and errors with current trace context.
    *   Track request/response times and correlate with backend metrics.
*   **Signal-Based Observability:**
    *   **Mutation Tracking:** Monitor signal mutation frequency and patterns using OpenTelemetry spans.
    *   **Performance Monitoring:** Track computed signal evaluation times and effect execution.
    *   **Error Propagation:** Monitor signal error propagation through the application.
    *   **Memory Leaks:** Detect potential memory leaks in signal subscriptions and effects.
    *   Use custom OpenTelemetry spans for signal mutations and performance monitoring.
*   **Performance Monitoring:**
    *   Use OpenTelemetry metrics for all frontend performance metrics (Core Web Vitals, rendering times, etc.).

### 4.2. Frontend Testing Strategy

*   **Observability Testing:** Test that all logs, metrics, and traces include correct OpenTelemetry context.
*   **Performance Testing:** Test all performance metrics are captured and exported via OpenTelemetry.
*   **Integration Testing:** Verify end-to-end trace correlation between frontend and backend.
*   **Error Simulation:** Test that all error reports include trace context.

## 5. Observability by Design

*   Instrumentation for logging, metrics, and tracing must be considered during development, not as an afterthought.
*   Dashboards must visualize key metrics and traces for all components and user flows.
*   Frontend and backend observability must be designed together for end-to-end traceability.

## 6. CI/CD Integration

*   All OpenTelemetry configuration and instrumentation must be part of the deployment pipeline.
*   Observability validation (logs, metrics, traces, error tracking) must be included in CI/CD checks.

*(This document is authoritative for all observability implementation. All legacy/manual correlation ID patterns are deprecated. OpenTelemetry is the only supported approach.)*
