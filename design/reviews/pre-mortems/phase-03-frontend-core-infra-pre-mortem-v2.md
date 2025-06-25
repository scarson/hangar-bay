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

## 5. Mitigation Strategies & Proactive Actions

1.  **Operationalized AI Memory:** The primary mitigation is the creation and enforcement of the **AI Memory `bc0358c8-bf02-475d-beff-3fa5a0a02f9e`**. This memory serves as a persistent, high-level directive for Cascade to always validate its actions against the sources of truth.
2.  **Mandatory PR Checklist Item:** All frontend pull requests must include a checklist item: "Verified that the changes adhere to the relevant architectural patterns and guides in `design/angular/`."
3.  **Proactive Referencing:** Cascade is explicitly tasked with referencing the relevant design document when proposing a solution or generating code for a new feature.

## 6. Broader Lessons Learned / Insights Gained

*   **Living Documents:** Planning artifacts like pre-mortems are most valuable when they evolve with the project's knowledge base. They should be revisited and updated when significant new documentation or patterns are established.
*   **Operationalizing Knowledge:** The most effective way to enforce architectural decisions is to translate them from static documents into active, operational guardrails, such as AI memories and mandatory process steps (e.g., PR checklists).
