---
ReviewID: PREMORTEM-20250610-001
Date: 2025-06-10
Subject: Phase 03 Frontend Core Infrastructure Implementation
RelatedTasks:
  - plans/implementation/phase-03-frontend-core-infrastructure/03.0-angular-project-initialization.md
  - plans/implementation/phase-03-frontend-core-infrastructure/03.1-angular-core-module-setup.md
  - plans/implementation/phase-03-frontend-core-infrastructure/03.2-backend-api-service-layer.md
  - plans/implementation/phase-03-frontend-core-infrastructure/03.3-basic-layout-routing-navigation.md
Participants: USER, Cascade
ReviewRounds: 2 (Initial + "Outside the Box")
PreviousPreMortemReview: [Phase 02 Pre-Mortem](./phase-02-backend-f001-pre-mortem.md)
NextPreMortemReview: N/A
---

## 1. Pre-Mortem Review Summary

This pre-mortem review reflects a detailed, iterative analysis of the Phase 03 Frontend Core Infrastructure tasks. The primary goal was to proactively identify potential failures, ambiguities, and risks, and to refine the implementation plans to mitigate them before coding began. The desired end-state is a clean, well-architected Angular foundation that is robust, scalable, and aligned with Hangar Bay's architectural principles.

## 2. Imagining Failure: Key Risks Identified

*(This section synthesizes the potential problems identified across multiple review loops for each task.)*

*   **Task 03.0: Angular Project Initialization**
    *   **Risk 1 (Path Ambiguity):** The `ng new` command could be executed in the wrong directory, resulting in a nested project structure (`.../hangar-bay/app/frontend/frontend/`) that complicates pathing for shared assets and build configurations.
    *   **Risk 2 (Tooling Configuration Failure):** The integration of ESLint and Prettier could be incomplete or misconfigured, leading to inconsistent code formatting, constant linting errors, and developer friction.
    *   **Risk 3 (Incorrect Project Prefix):** The Angular component prefix (`hangar-bay`) might not be correctly applied or verified, leading to default `app-` prefixes and inconsistency.
    *   **Risk 4 (Missing Environment Configuration):** Key application configuration, like the `apiUrl`, could be omitted from the `environment.ts` files, causing runtime errors when the API service layer is implemented.

*   **Task 03.1: Angular Core Module Setup**
    *   **Risk 1 (Module Responsibility Confusion):** `CoreModule` could be misused by importing `SharedModule` or other reusable UI components, violating the principle that `CoreModule` is for singletons used once in the app shell. This leads to bloated initial bundles.
    *   **Risk 2 (Implicit Dependencies & Order of Operations):** A developer might attempt to perform steps out of order (e.g., integrate `CoreModule` before it's created or configured) due to implicit dependencies within the task instructions.
    *   **Risk 3 (Incomplete Integration):** `CoreModule` could be created but not correctly imported into the root `AppModule`, rendering its providers and components unavailable to the application.

*   **Task 03.2: Backend API Service Layer**
    *   **Risk 1 (Module Import Ambiguity):** Confusion about whether `HttpClientModule` should be imported in `CoreModule` or `AppModule`, leading to incorrect setup.
    *   **Risk 2 (Interface vs. Schema Mismatch):** Frontend TypeScript interfaces could diverge from the authoritative Pydantic schemas in the backend (Task 02.4), leading to data mapping errors.
    *   **Risk 3 (Ambiguous Boolean Parameter Handling):** The prompt for handling boolean query parameters could be misinterpreted, leading to incorrect API requests (e.g., sending `is_active=null` instead of omitting the parameter).

*   **Task 03.3: Basic Layout, Routing, and Navigation**
    *   **Risk 1 (Component Export Failure):** Core layout components (e.g., `HeaderComponent`) could be declared in `CoreModule` but not added to its `exports` array, making them unusable in `AppComponent`.
    *   **Risk 2 (Styling Scope Confusion):** Global styles could be incorrectly applied, or component-specific styles could unintentionally leak due to misunderstanding of Angular's view encapsulation.
    *   **Risk 3 (Suboptimal Routing Setup):** The initial routing setup might not correctly implement lazy loading for feature modules, or the CLI command to generate a feature module could be overly complex and error-prone.

## 3. Root Causes & Likelihood/Impact Assessment

*   **Problem 1: Ambiguity and Omissions in Initial Setup Instructions**
    *   Root Cause(s):
        *   Lack of explicit directory paths for `ng new` command.
        *   Absence of clear, step-by-step verification procedures for critical configurations (e.g., Angular project prefix, linter/formatter setup, environment variables like `apiUrl`).
        *   Underestimation of potential for misconfiguration when integrating multiple development tools.
    *   Likelihood: High (Very common in initial project scaffolding without rigorous checklists).
    *   Impact: Medium (Leads to avoidable rework, delays, and developer frustration at the project's outset).

*   **Problem 2: Unclear Module Design Principles and Responsibilities**
    *   Root Cause(s):
        *   Insufficiently defined boundaries and roles for core architectural modules like `CoreModule` (singletons, app-wide services) vs. `SharedModule` (reusable UI components, pipes, directives).
        *   Lack of explicit guidance on where to import common Angular modules (e.g., `HttpClientModule` – correctly placed in `CoreModule` if service is app-wide, or feature module if specific).
        *   Failure to ensure components, directives, or pipes declared within a module (especially `CoreModule` or `SharedModule`) are properly added to its `exports` array if they are intended for use by other modules that import it.
    *   Likelihood: High (A classic challenge in maintaining modular architecture clarity as projects grow).
    *   Impact: High (Can lead to bloated bundles, circular dependencies, runtime errors due to missing providers or components, difficult debugging, and long-term architectural decay).

*   **Problem 3: Implicit Dependencies and Unstated Order of Operations**
    *   Root Cause(s):
        *   Task instructions that imply a necessary sequence of actions (e.g., `CoreModule` must exist before `AppModule` imports it) without explicitly stating prerequisites or dependencies between steps or tasks.
        *   Splitting the setup and integration of a single conceptual feature (e.g., `CoreModule` creation and its import into `AppModule`) across multiple task descriptions or sub-steps without clear, sequential linkage.
    *   Likelihood: Medium-High (Developers, especially those less familiar with the specific framework patterns, may not always infer the correct sequence).
    *   Impact: Medium (Can cause build or runtime errors if steps are performed out of order, leading to confusion, lost time in debugging, and incorrect module setup).

*   **Problem 4: Data Contract Misalignment Between Frontend and Backend**
    *   Root Cause(s):
        *   Insufficient emphasis in AI prompts or developer guidelines on the backend API schema (e.g., Pydantic models from Task 02.4) as the **single source of truth** for frontend TypeScript data interfaces.
        *   Developers potentially working from memory, outdated assumptions, or incomplete information regarding API contracts, leading to manual interface creation that drifts from the backend.
        *   Lack of a mandated verification step or automated tool to compare/synchronize frontend interfaces against backend schemas.
    *   Likelihood: Medium (Increases with project complexity, team size, and frequency of API changes).
    *   Impact: High (Results in runtime data errors, integration failures, unexpected application behavior, and potentially corrupted data, which can be subtle and hard to trace).

*   **Problem 5: Ambiguity in API Interaction Specifications**
    *   Root Cause(s):
        *   Unclear or incomplete instructions for specific API interactions, such as the correct, consistent handling of boolean query parameters (e.g., omitting the parameter for `false` or `null` values vs. sending `is_active=false`).
    *   Likelihood: Medium (Depends on the complexity and nuances of the API design).
    *   Impact: Medium (Can lead to incorrect API requests, unexpected backend behavior, inconsistent data filtering/retrieval, and wasted debugging effort).

*   **Problem 6: Styling and Routing Misconceptions or Oversights**
    *   Root Cause(s):
        *   Potential misunderstanding of Angular's view encapsulation mechanisms, leading to unintended style leakage from global stylesheets or component-specific styles not applying as expected.
        *   Lack of clear, simple guidance or examples for best-practice routing setup, particularly for implementing lazy loading for feature modules to optimize initial load times.
        *   Overly complex or error-prone CLI commands suggested for common tasks like generating feature modules with routing, increasing the chance of incorrect setup.
    *   Likelihood: Medium (Common for developers newer to Angular's specific patterns or when rushing setup).
    *   Impact: Medium (Can lead to UI inconsistencies, poor user experience due to styling issues, performance degradation from eager loading all modules, and difficulties in maintaining and scaling the routing configuration).

## 4. Mitigation Strategies & Proactive Actions

*(This section was converted into the 'Key Decisions & Changes' section below, as all mitigation strategies resulted in direct changes to the task files.)*

## 5. Key Decisions & Changes Resulting from this Review

*The following actionable changes were made to the Phase 03 task files to mitigate the identified risks:* 

*   **For Task 03.0 (Project Initialization):**
    *   The `ng new` command was updated to include an explicit output directory to prevent nested projects.
    *   Added explicit verification steps to check `angular.json` for the correct `project.prefix` and to confirm `.prettierrc.json` and ESLint files are created and configured.
    *   Added a step to explicitly add the `apiUrl: ''` property to both `environment.ts` and `environment.prod.ts`.

*   **For Task 03.1 (Core Module Setup):**
    *   Clarified the responsibility for `CoreModule` creation and import to reside *solely* within this task, removing ambiguity from other tasks.
    *   Added an explicit step and a DoD criterion to ensure `CoreModule` is imported into the `imports` array of `AppModule`.
    *   Added a prerequisite note to the implementation steps, e.g., `**Prerequisite:** Ensure Task 03.0 has been completed...`.
    *   Added an explicit step to import `HttpClientModule` into `CoreModule`.
    *   Added a note to the AI Guidance to clarify the distinct roles of `CoreModule` (singletons) and `SharedModule` (reusable UI elements).

*   **For Task 03.2 (API Service Layer):**
    *   Strengthened the AI prompt to explicitly state that the backend Pydantic schemas from Task 02.4 are the **single source of truth** for TypeScript interface design.
    *   Added a new sub-step: "Verify Interface and Parameter Alignment" to mandate a direct comparison between frontend interfaces and backend schemas before implementation.
    *   Added a clarification note to the AI prompt regarding the handling of boolean query parameters to ensure correctness.

*   **For Task 03.3 (Layout & Routing):**
    *   Added an explicit instruction and DoD criterion to ensure layout components like `HeaderComponent` are added to the `exports` array of `CoreModule`.
    *   Simplified the recommended CLI command for generating feature modules to be more reliable.
    *   Added a task step to create a basic `styles.scss` with global styles and added a note to the AI prompt regarding Angular's default view encapsulation to prevent style conflicts.

## 6. Broader Lessons Learned / Insights Gained

*   **Value of Iterative Pre-Mortems:** This multi-loop review process proved highly effective at transforming abstract risks into concrete, actionable changes to the implementation plan, significantly de-risking the entire phase.
*   **Explicit is Better Than Implicit:** The review consistently revealed that implicit dependencies, unstated prerequisites, and ambiguous responsibilities are major sources of potential failure. Future task definitions must prioritize explicit instructions and verification steps.
*   **Single Source of Truth:** For cross-domain concerns like API contracts, the task documentation must be crystal clear about the single source of truth (e.g., backend schemas) to prevent divergence.

## 7. Impact on Cascade's Understanding & Future Actions

*   **Refined Understanding:** This process has deeply reinforced Cascade's understanding of Hangar Bay's specific architectural preferences and the importance of rigorous, proactive risk analysis before implementation.
*   **Proactive Referencing:** Cascade will now more proactively reference the established architectural guidelines (`/design/angular/`) and cross-cutting concern specifications when assisting with future development.
*   **Pattern Recognition:** Cascade will pay special attention to the patterns of risk identified here (e.g., module responsibilities, implicit dependencies, tooling configuration) when analyzing or generating future task plans.

---
