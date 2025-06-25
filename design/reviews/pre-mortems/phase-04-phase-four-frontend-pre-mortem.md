---
ReviewID: PREMORTEM-20250625-PH4
Date: 2025-06-25
Subject: Phase 04 Frontend (F001/F002) - Contract Listing & Filtering
RelatedTasks:
  - plans/implementation/phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.1-contract-list-component.md
Participants: [USER, Cascade]
ReviewRounds: 1
PreviousPreMortemReview: N/A
NextPreMortemReview: N/A
---

## 1. Pre-Mortem Review Summary

This pre-mortem review was initiated to proactively identify and mitigate risks before beginning the implementation of Hangar Bay's core frontend feature: the contract browsing and filtering page (Phase 4). The review process involves a thorough analysis of the Phase 4 implementation plan (`04.1-contract-list-component.md`) and the relevant feature specifications (F001, F002).

The primary goal is to ensure the implementation plan is fully aligned with the modern, standalone, signal-based Angular architecture established in Phase 3. The desired end-state is a robust, scalable, and maintainable feature built on a solid architectural foundation, avoiding the introduction of technical debt.

## 2. Imagining Failure: Key Risks Identified

*   **For the Contract Browsing Feature (Phase 4):**
    *   **Risk F1 (Inconsistent State Shape):** The definition for the state managed by the feature's core service is vague (e.g., "filter criteria").
        *   **Failure Scenario:** Different parts of the filter object are updated independently, leading to race conditions or effects that trigger on incomplete state changes. The API is called with a mix of old and new filter values.
    *   **Risk F2 (Poor User Experience on State Transitions):** The plan mentions displaying "loading, data, and error states" but lacks specifics on how to handle transitions *between* these states.
        *   **Failure Scenario:** A user performs a new search while a previous one is still loading. The UI flashes a loading spinner, then old data, then the new loading spinner, then the new data, creating a jarring "flicker" effect.
    *   **Risk F3 (Vague API Contract):** The plan assumes the backend API is stable but doesn't explicitly reference the OpenAPI specification or define the expected frontend data models.
        *   **Failure Scenario:** The frontend development proceeds with incorrect assumptions about API field names, data types, or pagination structure, leading to significant rework and integration problems.
    *   **Risk T1 (Effect Race Condition):** Using a simple `effect()` to trigger API calls based on filter changes can lead to race conditions.
        *   **Failure Scenario:** A user rapidly clicks multiple filter checkboxes. This triggers several API requests in quick succession. Due to network latency, Request #1 (with old filters) might resolve *after* Request #3 (with the newest filters), causing the UI to briefly show the correct new data, then be overwritten by stale data.
    *   **Risk T2 (State Desynchronization on Init):** The component may initialize and fetch data before it has a chance to read filter parameters from the URL's query string.
        *   **Failure Scenario:** A user navigates directly to `/contracts?status=active`. The component loads, fires an initial API call with default (empty) filters, then the routing logic parses the `status=active` parameter and triggers a *second* API call. This results in wasted network requests and a potential UI flicker.

## 3. Root Causes & Likelihood/Impact Assessment

*   **Problem 1: Insufficiently Specific Implementation Plan**
    *   **Root Cause(s):**
        *   The initial plan lacks explicit definitions for state management data structures.
        *   The plan does not mandate specific patterns for handling UI state transitions.
        *   The plan fails to enforce a direct dependency on the backend's published API contract (`openapi.yaml`).
    *   **Likelihood:** High
    *   **Impact:** High (Rework, bugs, integration delays)

*   **Problem 2: Naive Use of Asynchronous Primitives**
    *   **Root Cause(s):**
        *   The plan relies on a basic Angular `effect()` for asynchronous operations, which lacks built-in cancellation logic for handling rapid-fire events.
        *   The plan does not account for the timing of component initialization relative to the asynchronous resolution of Angular Router data (like query parameters).
    *   **Likelihood:** Medium
    *   **Impact:** Medium (Bugs, poor performance, bad user experience)

## 4. Assumptions and Dependencies

*   **Key Assumptions:**
    *   The standalone component, signal-based state management architecture defined in Phase 3 is the correct and final architectural direction for the project.
    *   The backend API (`/design/api/openapi.yaml`) is stable, and its data contracts will not change significantly during Phase 4 development.
    *   The `ContractApi` service created in Phase 3 correctly handles HTTP communication and error propagation.

*   **Key Dependencies:**
    *   Angular (v17+ with standalone components, signals, and zoneless change detection).
    *   The Hangar Bay backend API for providing contract data.
    *   The `ContractApi` service for abstracting HTTP calls.

## 5. Implications for Testing Strategy

*   **State Management Logic Testing:**
    *   The `ContractSearchService` must have comprehensive unit tests, mocking the `ContractApi` dependency. All state-updating methods must be rigorously validated to ensure atomic and correct state transitions (Mitigates F1).
    *   The RxJS pipeline that replaces the simple `effect()` must be tested using marble testing (`TestScheduler`) to verify that debouncing and switching logic correctly prevents race conditions (Mitigates T1).
*   **Component-Service Integration Testing:**
    *   The `ContractBrowsePage` component's tests will use a mock `ContractSearchService` to verify that the component's view correctly renders all possible states, including the graceful handling of loading-with-stale-data to prevent UI flicker (Mitigates F2).
*   **Contract Testing:**
    *   While not a separate test suite, unit tests for the `ContractApi` service and the new `ContractSearchService` will use mock data that strictly adheres to the frontend data models derived from the OpenAPI spec, ensuring alignment (Mitigates F3).
*   **Resolver Testing:**
    *   The new `ContractFilterResolver` will be unit tested to ensure it correctly parses URL query parameters into a `ContractSearchFilters` object (Mitigates T2).

## 6. Monitoring and Observability Requirements

*   **Key Metrics to Track (Frontend):**
    *   **Contract API Interaction:**
        *   API call success/failure rate (from the client's perspective).
        *   API call latency (measured from request initiation to response received).
*   **Structured Logging:**
    *   All caught errors related to API interaction or state management on the frontend should be logged to the console with structured information (e.g., error message, status code, component/service context).

## 7. Key Decisions & Changes Resulting from this Review

*   **For the Phase 4 Implementation Plan (`04.1-contract-list-component.md`):**
    *   **Action:** The implementation plan will be updated to mandate the creation of strongly-typed frontend data models and an immutable filter interface, and to require atomic state updates.
    *   **Mitigates:** Risk F1 (Inconsistent State Shape), Risk F3 (Vague API Contract)

*   **For the Phase 4 Implementation Plan (`04.1-contract-list-component.md`):**
    *   **Action:** The implementation plan will be updated to require graceful handling of UI state transitions, where stale data is preserved while new data is loading.
    *   **Mitigates:** Risk F2 (Poor User Experience on State Transitions)

*   **For the Phase 4 Implementation Plan (`04.1-contract-list-component.md`):**
    *   **Action:** Replace the simple `effect()` for data fetching with a more robust RxJS pipeline using `toObservable`, `debounceTime`, and `switchMap`.
    *   **Mitigates:** Risk T1 (Effect Race Condition)

*   **For the Phase 4 Implementation Plan (`04.1-contract-list-component.md`):**
    *   **Action:** Implement an Angular Route Resolver (`ContractFilterResolver`) to parse URL query parameters and provide the initial filter state to the `ContractSearchService` *before* the component is activated.
    *   **Mitigates:** Risk T2 (State Desynchronization on Init)

## 8. Broader Lessons Learned / Insights Gained

*   Implementation plans are living documents that must be reviewed and updated if foundational architectural assumptions change. A change in one phase can have significant ripple effects on the plans for subsequent phases.
*   A formal pre-mortem process is highly effective at catching architectural drift and plan ambiguity before any code is written, preventing significant rework.

## 9. Impact on Cascade's Understanding & Future Actions

*   **Refined Understanding:** This review has reinforced the critical importance of ensuring plans are synchronized with the latest architectural reality of the codebase. A plan's specificity is a direct mitigation for implementation risk.
*   **Proactive Application:** In the future, when beginning a new phase, I will proactively cross-reference the existing plans against the outcomes and post-mortems of the preceding phase to identify potential architectural drift earlier.
*   **Emphasis:** I will place a stronger emphasis on treating planning documents as dynamic artifacts that must be maintained, rather than static one-off deliverables.

---
