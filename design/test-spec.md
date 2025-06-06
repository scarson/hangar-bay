# Hangar Bay - Test Specification

## 1. Introduction

This document outlines the testing strategy and plan for the Hangar Bay application. A robust test suite is critical for ensuring application quality, reliability, security, and maintainability.

## 2. Testing Philosophy

*   **Test Pyramid:** Adhere to the testing pyramid model, emphasizing a large base of fast unit tests, a moderate number of integration tests, and a smaller number of comprehensive end-to-end tests.
*   **Automation:** Automate tests as much as possible to enable frequent execution, especially within the CI/CD pipeline.
*   **Early Testing:** Write tests concurrently with feature development (Test-Driven Development - TDD, or Behavior-Driven Development - BDD, where appropriate).
*   **Coverage:** Aim for high, meaningful test coverage of critical application logic. Coverage metrics will be tracked.
*   **Security Testing:** Integrate security testing throughout the development lifecycle (see Section 7).
*   **Accessibility Testing:** Integrate accessibility testing throughout the development lifecycle to ensure conformance with `accessibility-spec.md` (WCAG 2.1 AA minimum).

## 3. Types of Tests

### 3.1. Unit Tests
*   **Scope:** Test individual functions, methods, or components in isolation.
    *   **Backend (Python/FastAPI):** Test business logic, utility functions, individual API endpoint handlers (mocking external dependencies like ESI and database).

        *   **AI Implementation Pattern (FastAPI Unit Tests - pytest):**
            *   For new FastAPI endpoint functions, AI should generate test cases covering:
                *   Successful responses (200 OK) with expected data structure.
                *   Input validation errors (422 Unprocessable Entity).
                *   Authentication/Authorization errors (401/403).
                *   Mocking of service layer dependencies using `mocker` fixture from `pytest-mock`.
    *   **Frontend (Angular):** Test individual components, services, pipes, and directives.

        *   **AI Implementation Pattern (Angular Unit Tests - Jasmine/Karma):**
            *   When generating a new Angular component/service, AI should also generate a `.spec.ts` file with:
                *   Basic setup (`TestBed.configureTestingModule`, component fixture creation).
                *   A test for component creation (`expect(component).toBeTruthy();`).
                *   Placeholders or simple tests for public methods and key interactions.
                *   Mocks for service dependencies using `jasmine.createSpyObj`.

### 3.2. Integration Tests
*   **Scope:** Test interactions between components or modules.
*   **Backend:** Test API endpoints with a real (test) database, interactions with the caching layer (Valkey), and potentially mocked ESI interactions to verify request/response handling.
    *   **Frontend:** Test component interactions, service integrations, and routing.

        *   **AI Actionable Checklist (Angular Integration Tests):**
            *   [ ] Test that a parent component correctly passes data to a child component via `@Input()`.
            *   [ ] Test that a parent component correctly listens to events from a child component via `@Output()`.
            *   [ ] Test that a service method is called when a component action is performed.
            *   [ ] Test basic routing scenarios (e.g., navigating to a page displays the correct component).

### 3.3. End-to-End (E2E) Tests
*   **Scope:** Test complete user flows through the deployed application (frontend through backend to database/cache).
*   **Focus:** Verify critical user scenarios, such as searching for contracts, applying filters, authenticating via EVE SSO (mocked SSO provider), managing watchlists, and receiving alerts (simulated).
*   **Responsive Design Testing:** E2E tests MUST cover various viewport sizes (desktop, tablet, mobile - portrait and landscape) to ensure UI elements render correctly, are usable, and that no content is broken or inaccessible. This includes testing navigation, forms, and data displays across different screen dimensions.
    *   **Caution:** E2E tests are typically slower and more brittle; reserve them for the most critical paths.

        *   **AI Implementation Pattern (E2E Test Generation - e.g., Cypress/Playwright):**
            *   AI can be prompted to generate E2E test stubs for critical user flows described in feature specs.
            *   Example prompt: "Generate a Cypress test for the user login flow: visit login page, fill username, fill password, click submit, expect redirect to dashboard, expect welcome message."
            *   AI should use page object models (POM) for maintainability if feasible.

### 3.4. Performance Tests
*   **Scope:** Evaluate application responsiveness, scalability, and stability under load.
*   **Areas:** API endpoint performance, database query efficiency, ESI interaction latency impact.
*   *(Placeholder: Specific performance targets and scenarios to be defined)*

### 3.5. Usability Tests
*   *(Placeholder: To be considered, potentially manual or with user feedback sessions).*
*   **Responsive Design Aspect:** Usability testing SHOULD include evaluating the ease of use and overall experience on different devices and screen sizes, particularly mobile.

### 3.6. Accessibility Tests (A11y)
*   **Scope:** Verify conformance with WCAG 2.1 AA criteria as outlined in `accessibility-spec.md`.
*   **Automated Testing:** Utilize tools (e.g., Axe-core, Lighthouse) to automatically scan for common A11y violations. These tests should be integrated into component/E2E tests and the CI/CD pipeline.
*   **Manual Testing:** Essential for aspects that automated tools cannot fully cover:
    *   **Keyboard-Only Navigation:** Comprehensive testing of all interactive elements, focus order, visible focus indicators, and absence of keyboard traps.
    *   **Screen Reader Testing:** Test with major screen readers (NVDA, JAWS, VoiceOver on relevant platforms) to ensure content is announced correctly, ARIA attributes are effective, and user flows are understandable.
    *   **Zoom & Reflow:** Test content readability and functionality at 200% zoom and in reflowed views.
    *   **Color Contrast:** Verify contrasts manually or with tools where dynamic content might affect automated checks.
    *   **Content & Structure:** Verify semantic HTML usage, heading structure, link purpose, and form labeling.
*   **AI Coding Assistant Guidance:** The AI assistant should be prompted to generate code that passes automated A11y checks and to consider manual A11y testing scenarios when developing UI components.

    *   **AI Actionable Checklist (Accessibility Test Generation):**
        *   [ ] When AI generates a new UI component, prompt it to include an Axe-core scan in its unit/integration tests.
            *   Example (Angular with `@axe-core/angular`): `it('should pass accessibility scan', async () => { await TestBed.inject(AxeAngular).check(); });`
        *   [ ] For E2E tests of UI features, remind AI to include checks for keyboard navigability (e.g., tabbing through elements, activating controls) and visible focus states.

### 3.7. Internationalization (i18n) Tests
*   **Scope:** Verify that the application correctly displays and functions in different languages and locales as defined in `i18n-spec.md`.
*   **Key Areas for Testing:**
    *   **UI Element Translation:** Ensure all user-facing text elements (labels, buttons, messages, titles, `alt` text, `aria-label`s, etc.) are correctly translated and displayed for supported languages.
    *   **Layout Adaptability:** Test that UI layouts adapt to varying text lengths across different languages without breaking, overflowing, or truncating critical information. Pay attention to menus, buttons, and data tables.
    *   **Language Switching:** Verify that the language switching mechanism works correctly and persists the user's preference (if applicable).
    *   **Locale-Specific Formatting:** Test correct formatting of dates, times, numbers, and currencies according to the selected locale.
    *   **ESI API Language Parameter:** For features interacting with EVE ESI, verify that the correct `language` parameter is sent with API requests based on user locale or default fallback (`en-us`), and that responses are handled appropriately.
    *   **Character Encoding:** Ensure correct rendering of special characters and non-ASCII characters for all supported languages.
    *   **Right-to-Left (RTL) Support (Future):** If RTL languages are supported in the future, specific tests for layout mirroring and text direction will be required.
*   **Testing Strategies:**
    *   **Pseudo-localization:** Use pseudo-localization techniques early in development to identify i18n issues (e.g., text expansion, non-translatable strings).
    *   **Target Language Testing:** Perform testing with actual translated strings for key supported languages, focusing on UI rendering and functional correctness.
    *   **Automated Checks:** Where possible, automate checks for missing translation keys or basic rendering issues.
*   **AI Coding Assistant Guidance:** When AI generates UI components or features involving text, prompt it to consider how these will be tested for different languages and to ensure all text is externalized for translation.

    *   **AI Actionable Checklist (i18n Test Considerations):**
        *   [ ] For new UI components, check that all display strings are sourced from translation files.
        *   [ ] Test component layout with significantly longer or shorter pseudo-localized strings.
        *   [ ] If the component handles dates/numbers, verify they are formatted using locale-aware services.
        *   [ ] Verify `alt` text and `aria-label` attributes are translatable and included in i18n testing.

## 4. Tools and Frameworks

*   **Backend (Python/FastAPI):**
    *   **Test Runner:** `pytest`
    *   **Mocking:** `pytest-mock`, `unittest.mock`
    *   **HTTP Client for API tests:** `httpx` (FastAPI's test client)
*   **Frontend (Angular):**
    *   **Unit Tests:** Karma (test runner), Jasmine (testing framework)
    *   **E2E Tests:** Protractor (though Angular is moving towards other solutions like Cypress or Playwright - *to be confirmed based on Angular best practices at implementation time*). Tools should support viewport manipulation for responsive design testing.
*   **Code Coverage:**
    *   Backend: `pytest-cov`
    *   Frontend: Istanbul (via Angular CLI)
*   **Accessibility Testing Tools:**
    *   **Automated:** Axe-core (e.g., `@axe-core/angular` for integration with Angular tests, browser extensions for manual checks), Lighthouse (browser developer tools).
    *   **Screen Readers:** NVDA (Windows), JAWS (Windows), VoiceOver (macOS/iOS).

        *   **AI Implementation Pattern (Angular Test Setup for A11y):**
            *   Ensure `AxeAngular` is configured in `test.ts` or a test setup file if using `@axe-core/angular`.
            *   AI should be aware of how to import and inject `AxeAngular` into test suites.

## 5. Test Data Management

*   Use fixtures or factories to generate consistent test data.
*   For integration tests, use a dedicated test database that is reset before each test run or suite.
*   Avoid reliance on live ESI data for automated tests; use mocks or recorded responses.

## 6. CI/CD Integration

*   All automated tests (unit, integration, and critical E2E) MUST run as part of the Continuous Integration (CI) pipeline on every commit/merge request.
*   Builds MUST fail if tests do not pass.
*   Test coverage reports SHOULD be generated and monitored.
*   Automated accessibility scans (e.g., Axe-core) SHOULD be part of the CI pipeline, and critical violations MUST fail the build.

## 7. Security Testing

*   **Static Application Security Testing (SAST):** Integrate SAST tools (e.g., Bandit for Python, linters with security plugins) into the CI pipeline.
*   **Dynamic Application Security Testing (DAST):** Consider DAST tools for testing the running application against common web vulnerabilities.
*   **Dependency Scanning:** Use tools (e.g., `pip-audit` for Python, `npm audit` or Snyk for frontend) to check for known vulnerabilities in third-party libraries.
*   **Manual Penetration Testing:** Plan for periodic manual penetration testing by security professionals, especially before major releases.
    *   Refer to `security-spec.md` for detailed security requirements that will inform security test cases.

        *   **AI Actionable Checklist (Security Test Integration):**
            *   [ ] When setting up CI, instruct AI to include SAST tools (e.g., `bandit run -r . -ll` for Python).
            *   [ ] Instruct AI to include dependency vulnerability scanning (e.g., `pip-audit` for Python, `npm audit --audit-level=high` for Angular) in CI scripts.

## 8. Test Plan by Feature

*(Placeholder: This section will be populated with specific test cases and scenarios as features are defined and developed. Examples:)*
*   **EVE SSO Authentication:** Test login flow, token handling, logout.
*   **Contract Aggregation:** Test fetching, filtering, and display of contracts.
*   **Search & Filtering:** Test various search terms and filter combinations.
*   **Watchlists & Alerts:** Test creation, modification, deletion of watchlists, and alert triggering logic.
*   **(General for all features):** All feature test plans MUST include specific test cases for accessibility (see `accessibility-spec.md`) and internationalization (see `i18n-spec.md`). This includes verifying UI in different languages, layout adaptability, and correct locale-specific data handling.
