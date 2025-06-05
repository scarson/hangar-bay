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

### 2.2. Metrics
*   **Application Metrics (Backend - FastAPI):**
    *   Request rate, error rate, latency (overall and per-endpoint).
    *   ESI API interaction metrics: call count, error rate, latency per ESI endpoint.
    *   Database query performance: execution time, error rate per query type.
    *   Cache performance: hit/miss ratio, latency.
    *   Task queue metrics (for alerts): queue length, task processing time, error rate.
*   **Frontend Metrics (Angular):**
    *   Page load times, component interaction times.
    *   Client-side error rates.
    *   API call latency from client perspective.
*   **System Metrics:** CPU usage, memory usage, disk I/O, network traffic for application hosts/containers.
*   **Business Metrics (High-Level):**
    *   Number of active users (if SSO implemented).
    *   Number of contracts processed/displayed.
    *   Watchlist creation/alert triggering frequency.

### 2.3. Tracing (Distributed Tracing - OpenTelemetry Preferred)
*   **Goal:** To visualize the entire lifecycle of a request as it flows through different components of the application (e.g., frontend -> backend API -> ESI API -> database -> cache).
*   **Implementation:** Strongly prefer and prioritize the use of OpenTelemetry SDKs and APIs for instrumenting code and propagating trace context across all services (Python backend, Angular frontend if applicable).
*   **Benefits:** Pinpoint bottlenecks, understand service dependencies, debug complex issues in a distributed environment.

### 2.4. Error Tracking & Alerting (Operational)
*   **Centralized Error Aggregation:** Collect and aggregate exceptions and errors from both backend and frontend in a centralized system.
*   **Alerting:** Set up alerts for critical errors, unusual spikes in error rates, performance degradation, or system resource exhaustion.
    *   Distinguish from user-facing application alerts (e.g., new contract found).

## 3. Tools and Technologies (Proposed - Emphasizing OpenTelemetry Compatibility)

*   **Logging Management:**
    *   *(Placeholder: e.g., ELK Stack, Grafana Loki, OpenTelemetry Collector with backends like Jaeger/Elasticsearch. Prioritize solutions with strong OpenTelemetry OTLP ingest capabilities.)*
*   **Metrics Collection & Visualization:**
    *   **Backend:** Prometheus client libraries for FastAPI. Consider OpenTelemetry SDKs for metrics as well, which can export to Prometheus.
    *   **System:** Prometheus Node Exporter or similar.
    *   **Storage & Visualization:** Prometheus (time-series database) & Grafana (dashboards).
*   **Distributed Tracing:**
    *   **Instrumentation:** OpenTelemetry SDKs for Python (FastAPI) and JavaScript (Angular) are the primary choice.
    *   **Backend Collector/Storage:** An OpenTelemetry Collector is highly recommended for receiving, processing, and exporting telemetry data. Backends like Jaeger, Zipkin, Prometheus, or managed cloud services (e.g., AWS X-Ray, Google Cloud Trace, Azure Monitor) that support OpenTelemetry are preferred.
*   **Error Tracking:**
    *   *(Placeholder: e.g., Sentry, Rollbar, Elastic APM. Evaluate for OpenTelemetry integration capabilities, such as correlating errors with traces.)*

## 4. Observability by Design

*   Instrumentation for logging, metrics, and tracing should be considered during development, not as an afterthought.
*   Dashboards should be created to visualize key metrics and logs for different components and user flows.

## 5. CI/CD Integration

*   Ensure that observability configurations and instrumentation are part of the deployment pipeline.

*(This document will be updated as the tech stack is finalized and specific tools are chosen.)*
