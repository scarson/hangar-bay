<!-- AI_NOTE: This document summarizes the review of Phase 04: Frontend Contract Listing & Filtering for the Hangar Bay project. It consolidates learnings, tracks decisions, and guides future phases. -->

# Phase 04: Frontend F001/F002 Contract Listing & Filtering - Post-Mortem Review

**Date of Review:** 2025-06-25
**Phase Duration:** Approx. 2025-06-25
**Lead Developer(s)/AI Pair:** USER & Cascade
**RelatedPreMortemReview:** [phase-04-phase-four-frontend-pre-mortem.md](../../pre-mortems/phase-04-phase-four-frontend-pre-mortem.md)
**PreviousPhaseReview:** [03-frontend-core-infrastructure-review.md](./03-frontend-core-infrastructure-review.md)
**NextPhaseReview:** N/A

## 1. Phase Objectives, Outcomes, and Strategic Alignment

*   **1.1. Stated Objectives:**
    *   Implement a contract browsing page that displays a list of public contracts from the backend API.
    *   Implement basic filtering capabilities (e.g., text search) and pagination.
    *   Build the feature using the established modern Angular architecture (standalone, signal-based).
    *   Proactively mitigate risks identified in the pre-mortem, especially regarding state management and asynchronous operations.
*   **1.2. Achieved Outcomes:**
    *   All objectives were successfully met.
    *   A `ContractBrowsePage` was created, displaying contract data fetched from the `/api/v1/contracts/` endpoint.
    *   A `ContractSearch` injectable service was implemented to manage all state and API interactions, cleanly separating concerns from the component.
    *   The implementation successfully used an advanced RxJS pipeline (`debounceTime`, `switchMap`) to prevent race conditions, directly mitigating Risk T1 from the pre-mortem.
    *   The UI correctly handles and displays loading, error, and data states, providing a good user experience and mitigating Risk F2.
*   **1.3. Deviations/Scope Changes:**
    *   There were no major deviations. The implementation closely followed the mitigation strategies outlined in the pre-mortem review.
*   **1.4. Alignment with Strategic Goals:**
    *   This phase delivered the first core, user-facing feature of the application. It proved the viability and effectiveness of the foundational architecture established in Phase 3 and set a high-quality pattern for all subsequent feature development.

## 2. Key Features & Infrastructure: Design vs. Implementation

*   **2.1. Major Deliverables (with file paths):**
    *   **Signal State Service:** The `ContractSearch` service, which acts as the single source of truth for the feature's state. (`app/frontend/angular/src/app/features/contracts/contract-search.ts`)
    *   **Standalone Feature Component:** The `ContractBrowsePage` component, responsible for rendering the UI. (`app/frontend/angular/src/app/features/contracts/contract-browse-page/`)
    *   **API Data Models:** TypeScript interfaces (`ContractSearchFilters`, `PaginatedContractsResponse`) defining the shape of data. (`app/frontend/angular/src/app/features/contracts/contract.models.ts`)
*   **2.2. Design vs. Implementation - Key Variances & Rationale:**
    *   There were no negative variances. The implementation was a direct and successful execution of the *mitigation plan* from the pre-mortem, which was more advanced than the original, simplistic task plan.
    *   **Feature/Component:** State Management & Data Fetching
        *   **Variance:** The initial plan was vague. The pre-mortem identified a risk of using a naive `effect()` for data fetching. The final implementation used a sophisticated RxJS pipeline.
        *   **Rationale:** The RxJS `switchMap` operator was chosen specifically to solve the classic rapid-input race condition. It automatically cancels previous, in-flight API requests when a new one is triggered, ensuring only the results for the *latest* filter criteria are ever processed. This is a more robust and declarative solution than manual cancellation logic.
        *   **Impact (Positive):** High. This pattern completely prevents a category of subtle, hard-to-debug race condition bugs and improves UI stability.

## 3. Technical Learnings & Discoveries

*   **2.2. Design vs. Implementation - Key Variances & Rationale:**
    *   There were no negative variances. The implementation was a direct and successful execution of the *mitigation plan* from the pre-mortem, which was more advanced than the original, simplistic task plan.
    *   **Feature/Component:** State Management & Data Fetching
        *   **Variance:** The initial plan was vague. The pre-mortem identified a risk of using a naive `effect()` for data fetching. The final implementation used a sophisticated RxJS pipeline.
        *   **Rationale:** The RxJS `switchMap` operator was chosen specifically to solve the classic rapid-input race condition. It automatically cancels previous, in-flight API requests when a new one is triggered, ensuring only the results for the *latest* filter criteria are ever processed. This is a more robust and declarative solution than manual cancellation logic.
        *   **Impact (Positive):** High. This pattern completely prevents a category of subtle, hard-to-debug race condition bugs and improves UI stability.

## 3. Technical Learnings & Discoveries

*   **3.1. Key Technical Challenges & Resolutions:**
    *   **Challenge 1:** Implementing a robust, race-condition-free data fetching mechanism based on user input.
        *   **Context:** As identified in the pre-mortem (Risk T1), simply triggering an API call in an `effect()` whenever a filter signal changes is dangerous. Rapid user input can lead to multiple concurrent API calls, with no guarantee of their resolution order, causing stale data to overwrite fresh data.
        *   **Resolution/Workaround:** The `ContractSearch` service implemented a formal RxJS pipeline to manage the entire data fetching lifecycle. This is the key technical achievement of this phase.
        *   **Illustrative Code Snippet (`contract-search.ts`):**
            ```typescript
            // ...
            this.filterTrigger$
              .pipe(
                startWith(undefined), // Trigger initial fetch
                debounceTime(300, this.scheduler), // Wait for user to stop typing
                map(() => this.#filters()), // Get latest filters
                distinctUntilChanged(/* ... */), // Avoid redundant calls
                tap(() => this.#state.update((s) => ({ ...s, loading: true }))), // Set loading state
                switchMap((filters) => { // Cancel previous requests, make new one
                  // ... http.get() logic
                })
              )
              .subscribe((response) => {
                // ... update state with response
              });
            ```
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   This RxJS pipeline within a signal-based service is now the **gold standard pattern** for handling state derived from asynchronous operations that are triggered by user input. All future features with similar requirements (e.g., search, filtering) must adopt this pattern. It should be formalized in the Angular design guides.
            
    *   **Challenge 2:** Overcoming persistent test failures to build a robust integration test suite.
        *   **Context:** After implementing the table layout, the existing tests for `ContractBrowsePage` were insufficient. A new integration suite was required, but it was plagued by a series of subtle failures.
        *   **Resolution/Workaround:** The resolution required a multi-step debugging process:
            1.  **Dependency Injection:** The initial failures were caused by not providing the standalone `Isk` and `TimeLeft` pipes to the `TestBed` configuration.
            2.  **Time-Based Flakiness:** The `TimeLeftPipe` test was brittle. This was resolved by using `jasmine.clock().mockDate()` to control time and make the test deterministic.
            3.  **Incorrect Assertions:** The most persistent failure (`Expected '1M' to contain '1,000,000.00 ISK'`) was due to a misunderstanding of the `Isk` pipe's behavior. The test expected a full currency format, but the pipe is designed to return a compact format. The fix was to inspect the pipe's source code and correct the test's expectation to match the actual, correct output.
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   When a test fails unexpectedly, do not assume the implementation is wrong. Always validate that the test's assertions and expectations are correct by reviewing the source code of the unit under test. This prevents time-consuming debugging loops based on false assumptions.

## 4. Process Learnings & Improvements

*   **4.1. Impact of Pre-Mortem Review:**
    *   This phase is a textbook example of a pre-mortem's value. The risks of race conditions and inconsistent state (F1, T1) were identified *before* any code was written. The mitigation strategies proposed (use `switchMap`, define clear state models) became the direct implementation plan, leading to a high-quality outcome from the start and preventing significant rework.

## 5. Cross-Cutting Concerns Review (Phase-Level Summary)

*   **Security:** Input from the search box is treated as data and sent as a URL parameter. It is not rendered as HTML, mitigating XSS risks.
*   **Observability:** Errors from the `HttpClient` are caught within the pipeline and logged to the console. The state is updated to show a user-friendly error message, preventing application crashes.
*   **Testing:** The use of an injection token for the RxJS `Scheduler` (`SEARCH_SCHEDULER`) is a key enabler for testing. It allows marble testing to be used to validate the timing-dependent logic (`debounceTime`, `switchMap`) in a synchronous, deterministic way.
*   **Accessibility (A11y):** The template includes `aria-label` attributes on interactive controls and `i18n-aria-label` for translation. The results container has `aria-live="polite"` to announce updates to screen readers.
*   **Internationalization (I18n):** All user-facing text in the template is correctly marked with `i18n` attributes for translation.

## 6. Technical Debt Deep Dive: Unresolved Phantom API Calls in Test Environment

*   **Issue:** During `ng test` execution, the test suite logs multiple `HttpErrorResponse` errors, indicating that real HTTP requests are being made to the backend API (`/api/v1/contracts/`). This occurs despite all 36 unit tests passing successfully.
*   **Impact:** High. This compromises the integrity and isolation of our test environment. Tests should never have external dependencies on a running backend. It also creates significant noise in test logs, making it difficult to spot legitimate test failures.
*   **Root Cause Analysis:** The issue stems from a deep and subtle interaction between the Angular testing framework (`TestBed`), the dependency injection system, and lazy-loaded modules. Specifically, when the main application test (`app.spec.ts`) triggers navigation to the `/contracts` route, the lazy-loaded `ContractsModule` is instantiated with its own dependency injector. The mock providers configured in the main test's `TestBed` are not being correctly inherited or prioritized by this child injector, causing the real `ContractSearch` service to be created, which then immediately attempts to fetch data.

*   **Chronicle of Failed Mitigation Attempts:**

    1.  **Initial Hypothesis: Missing Mocks in `app.spec.ts`**
        *   **Attempt:** Provided a simple mock for `ContractSearch` in the `providers` array of `TestBed.configureTestingModule` in `app.spec.ts`.
        *   **Result:** Failed. The lazy-loaded module did not receive the mock.

    2.  **Hypothesis: Incorrect Mocking of Lazy-Loaded Component Dependencies**
        *   **Attempt:** Used `TestBed.overrideProvider` for the `contractFilterResolver` in `app.spec.ts`, believing the resolver was the source of the unmocked dependency.
        *   **Result:** Failed. While the resolver was mocked correctly, the `ContractSearch` service itself was still the real implementation within the lazy-loaded module.

    3.  **Hypothesis: Test Isolation Failure in `app.spec.ts`**
        *   **Attempt:** Replaced the real application routes in `RouterTestingModule.withRoutes()` with a test-specific configuration that used a simple `StubComponent` for all routes. The goal was to test the main app's routing logic without actually loading the feature modules.
        *   **Result:** Failed catastrophically. This broke a valid test case that explicitly checks for successful lazy-loading, and it *still* did not solve the phantom API call issue.

    4.  **Hypothesis: `contract-browse-page.spec.ts` is the Culprit**
        *   **Attempt:** Investigated the component's own test file, believing its local `TestBed` configuration was faulty.
        *   **Result:** False alarm. The test setup in `contract-browse-page.spec.ts` was correct and properly isolated, using a simple mock object for the `ContractSearch` service.

    5.  **Hypothesis: `overrideProvider` is the Definitive Solution**
        *   **Attempt:** Correctly used `TestBed.overrideProvider` for *both* the `contractFilterResolver` and the `ContractSearch` service in `app.spec.ts`. This is the documented Angular best practice for overriding dependencies in lazy-loaded modules.
        *   **Result:** Failed. Inexplicably, even with this correct and advanced configuration, the phantom API calls persisted.

    6.  **Final Hypothesis: `RouterTestingModule` is Flawed**
        *   **Attempt:** Refactored the entire `app.spec.ts` test setup to abandon the legacy `RouterTestingModule` in favor of the modern, standalone-based `provideRouter` function. All mock providers were moved from `overrideProvider` calls into the main `providers` array, as is standard practice with this new API.
        *   **Result:** Failed. This fundamental change to the test setup had no effect on the outcome. The phantom API calls continued.

*   **Conclusion & Next Steps:**
    *   All standard and advanced mocking techniques available within the Angular testing framework have been exhausted without success. The problem lies at a deeper level of the framework's interaction with the Karma test runner and dependency injection scopes.
    *   **Recommendation:** This issue must be escalated to a human engineer for a deep-dive debugging session. Further attempts by an AI agent are unlikely to succeed and will be a waste of time. The engineer should focus on the `TestBed` configuration in `app.spec.ts` and the interaction with the lazy-loaded routes defined in `app.routes.ts`.

## 7. Unresolved Issues & Technical Debt

*   **Status:** Unresolved.
*   **Technical Debt Incurred:** High. A critical flaw in the test environment's isolation remains, as documented in detail in Section 6.

## 8. Recommendations for Subsequent Phases

*   **Technical Recommendations:**
    *   **Formalize the State Service Pattern:** The `ContractSearch` service pattern (private state signals, public computed signals, RxJS pipeline for async ops) should be documented as the official state management pattern in `design/angular/guides/04-state-management-and-rxjs.md`.
*   **New Memory Suggestion:**
    *   **Title:** Angular Signal State Service with RxJS Pipeline
    *   **Content:** "For managing asynchronous state in Angular features (e.g., data from API calls triggered by user input), the standard pattern is a signal-based injectable service. This service should use an RxJS pipeline featuring `debounceTime` and `switchMap` to handle the asynchronous action. `switchMap` is critical as it prevents race conditions by automatically cancelling previous stale requests when new ones are initiated. This pattern is exemplified by the `ContractSearch` service."
    *   **CorpusNames:** ["scarson/hangar-bay"]
    *   **Tags:** ["angular", "state_management", "rxjs", "signals", "best_practice"]
