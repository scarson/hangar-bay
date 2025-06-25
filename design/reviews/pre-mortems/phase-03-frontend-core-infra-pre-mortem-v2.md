---
ReviewID: PREMORTEM-20250625-001
Date: 2025-06-25
Subject: '[V2] Phase 03 Frontend Core Infrastructure Implementation'
RelatedTasks:
  - plans/implementation/phase-03-frontend-core-infrastructure/03.0-angular-project-initialization.md
  - plans/implementation/phase-03-frontend-core-infrastructure/03.1-angular-core-module-setup.md
  - plans/implementation/phase-03-frontend-core-infrastructure/03.2-backend-api-service-layer.md
  - plans/implementation/phase-03-frontend-core-infrastructure/03.3-basic-layout-routing-navigation.md
Participants: [USER, Cascade]
ReviewRounds: [1]
PreviousPreMortemReview: [Phase 03 Pre-Mortem V1](./phase-03-frontend-core-infra-pre-mortem.md)
NextPreMortemReview: N/A
---

## 1. Pre-Mortem Review Summary

This document is a second-generation (V2) pre-mortem for the Phase 03 Frontend Core Infrastructure. It revisits the initial risks in light of the project's significantly enhanced Angular design documentation (`design/angular/`) and the new, more structured pre-mortem template. The goal is to transform the pre-mortem from a static risk log into a living document that actively guides development by linking potential failures directly to their codified architectural solutions, ensuring a more resilient and consistent implementation.

## 2. Imagining Failure: Key Risks Identified

This section reframes risks as potential violations of our established best practices, with direct references to the authoritative design documents that serve as mitigation.

*   **Risk 1: Architectural Drift (Module Responsibility Violation)**
    *   **Failure Scenario:** The `CoreModule` becomes bloated with shared UI components, or a `SharedModule` is incorrectly provided with services, violating the singleton pattern. This leads to circular dependencies, increased initial bundle sizes, and architectural decay.
    *   **Source of Truth / Mitigation:** Strict adherence to the module responsibilities defined in `design/angular/00-angular-architecture-overview.md` is required.

*   **Risk 2: Inconsistent Asynchronous State Management**
    *   **Failure Scenario:** Components implement their own ad-hoc logic for managing loading, data, and error states for API calls. This results in inconsistent UI/UX, redundant code, and poor error handling.
    *   **Source of Truth / Mitigation:** All asynchronous data operations must use the standardized `AsyncState` pattern detailed in `design/angular/guides/04-state-management-and-rxjs.md`.

*   **Risk 3: Data Contract Divergence from Backend**
    *   **Failure Scenario:** Frontend TypeScript interfaces are created manually and drift from the backend's Pydantic models, leading to subtle runtime errors, data mapping failures, and difficult-to-debug integration issues.
    *   **Source of Truth / Mitigation:** Frontend interfaces for API objects MUST be generated or strictly derived from the backend's OpenAPI specification. Manual creation is prohibited. This is covered in `design/angular/guides/07-http-and-data-loading.md`.

*   **Risk 4: Suboptimal Routing and Performance**
    *   **Failure Scenario:** Feature modules are not lazy-loaded by default, causing the application's initial load time to grow unnecessarily as new features are added.
    *   **Source of Truth / Mitigation:** Lazy loading is the default strategy for all feature modules, as prescribed in `design/angular/guides/06-routing-and-navigation.md`.

*   **Risk 5: Inadequate or Inconsistent Testing**
    *   **Failure Scenario:** New components or services are created without accompanying tests, or tests are written in a way that is brittle and difficult to maintain, leading to a decline in code quality and an inability to refactor safely.
    *   **Source of Truth / Mitigation:** All new code must be tested according to the strategies and patterns defined in `design/angular/guides/09-testing-strategies.md`.

## 3. Root Causes & Likelihood/Impact Assessment

*   **Problem 1: Failure to Consult Established Patterns**
    *   **Root Cause(s):** A developer, including Cascade, proceeds with implementation based on general knowledge without consulting the project-specific, authoritative design documents.
    *   **Likelihood:** Medium (Requires continuous discipline to avoid).
    *   **Impact:** High (Leads to architectural drift, technical debt, and rework).

## 4. Assumptions and Dependencies

*   **Key Assumptions:**
    *   The backend API is stable and available during frontend development.
    *   The backend's OpenAPI specification is accurate and serves as the single source of truth for all API contracts.
    *   The Angular CLI and associated tooling (`ng`, `eslint`, `prettier`) function as expected.

*   **Key Dependencies:**
    *   **Internal:** Hangar Bay Backend API (for data), Valkey/Redis (for backend caching/locking that may affect data freshness).
    *   **External:** EVE Online SSO (for authentication), ESI API (as the ultimate source of data).

*   **Backend API Characteristics (from Phase 2 Pre-Mortem):**
    *   The backend API may return `null` for optional fields (e.g., `ship_name`) if its own data sources are incomplete. The frontend must handle this gracefully.
    *   The backend currently uses `OFFSET`-based pagination, which is known to have performance limitations at scale. Future migration to keyset pagination should be anticipated.

## 5. Implications for Testing Strategy

*   **Configuration Testing:**
    *   **Test Case 1:** Verify the application fails fast with a clear, catastrophic error during startup if the production `apiUrl` is missing, malformed, or points to a development address in a production build. (Mitigates: Operator's Nightmare risk of silent configuration failure).
*   **Resilience & Failure Mode Testing:**
    *   **Test Case 1:** Create integration tests for the global `HttpInterceptor` to ensure that various backend error codes (e.g., 404, 500, 503) are correctly caught and translated into the appropriate user-facing state or message. (Mitigates: Operator's Nightmare risk of unhandled API errors).
*   **Integration Testing:**
    *   **Test Case 1:** Implement integration tests that specifically target and verify the application's routing configuration, ensuring all lazy-loaded routes resolve correctly without runtime errors. (Mitigates: New Developer Onboarding risk of confusing "magic string" path errors).
    *   **Test Case 2:** Create tests where the mock API response is intentionally missing optional fields (e.g., `ship_name: null`) to verify that UI components render gracefully without crashing. (Mitigates: Risk of unhandled data gaps from the backend).

## 6. Monitoring and Observability Requirements

*   **Key Metrics to Track:**
    *   **API Service Layer:**
        *   **Metric 1:** Frontend API request error rate (by status code, e.g., 4xx, 5xx).
        *   **Metric 2:** Frontend API request latency (p50, p90, p99).
*   **Critical Alerts:**
    *   **Alert 1:** A sustained spike in 5xx errors from the frontend, indicating a potential backend outage.
*   **Structured Logging:**
    *   **Requirement 1:** All caught exceptions, especially in the global `HttpInterceptor`, must be logged as structured JSON with a clear error message, component/service context, and the original `HttpErrorResponse` details.
    *   **Requirement 2:** Log a catastrophic error if the runtime `apiUrl` validation fails in production.
    *   **Requirement 3:** When logging API errors, capture and include any correlation ID (e.g., `X-Request-ID`) sent by the backend in response headers to facilitate end-to-end request tracing.

## 7. Key Decisions & Changes Resulting from this Review

*   **Decision 1: Enforce Architectural Guardrails via AI Memory.**
    *   **Change:** Created and will enforce **AI Memory `bc0358c8-bf02-475d-beff-3fa5a0a02f9e`**, which mandates that Cascade validate all Angular work against the project's five core architectural principles (module structure, state management, data contracts, routing, testing).
    *   **Mitigates:** All risks identified in Section 2 (Architectural Drift, Inconsistent State, Data Divergence, etc.).

*   **Decision 2: Implement Runtime Production Configuration Validation.**
    *   **Change:** The task plan `03.0-angular-project-initialization.md` was updated to include a mandatory runtime check to validate the `apiUrl` in production builds.
    *   **Mitigates:** Operator's Nightmare risk of silent configuration failure.

*   **Decision 3: Mandate Signals for Reactive State & Prioritize Global Error Handling.**
    *   **Change:** The task plan `03.2-backend-api-service-layer.md` was updated to mandate that services expose state via `Signal<AsyncState<T>>` and to elevate the priority of implementing a global `HttpInterceptor`.
    *   **Mitigates:** Data's Lifecycle risk of stale data, Cross-Phase Friction risk of component boilerplate, and Operator's Nightmare risk of poor error handling.

*   **Decision 4: Plan for Automated API Client Generation.**
    *   **Change:** The task plan `03.2-backend-api-service-layer.md` was updated to strongly recommend creating a future task for automated client/interface generation from the backend OpenAPI spec.
    *   **Mitigates:** Data's Lifecycle risk of data contract drift, New Developer Onboarding friction, and the **explicitly identified "Cross-Phase Friction" risk** from the Phase 2 backend pre-mortem.

*   **Decision 5: Require Integration Tests for Routing.**
    *   **Change:** The task plan `03.3-basic-layout-routing-navigation.md` was updated to require integration tests that verify lazy-loaded routing paths.
    *   **Mitigates:** New Developer Onboarding risk of confusing runtime routing errors.

## 8. Broader Lessons Learned / Insights Gained

*   **Living Documents:** Planning artifacts like pre-mortems are most valuable when they evolve with the project's knowledge base. They should be revisited and updated when significant new documentation or patterns are established.
*   **Operationalizing Knowledge:** The most effective way to enforce architectural decisions is to translate them from static documents into active, operational guardrails, such as AI memories and mandatory process steps (e.g., PR checklists).
*   **Value of Advanced Reviews:** A second, deeper review using alternative mental models after initial planning is highly effective at uncovering systemic, cross-cutting risks that may not be apparent at the individual task level.
