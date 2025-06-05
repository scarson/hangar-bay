# Hangar Bay - Test Specification

## 1. Introduction

This document outlines the testing strategy and plan for the Hangar Bay application. A robust test suite is critical for ensuring application quality, reliability, security, and maintainability.

## 2. Testing Philosophy

*   **Test Pyramid:** Adhere to the testing pyramid model, emphasizing a large base of fast unit tests, a moderate number of integration tests, and a smaller number of comprehensive end-to-end tests.
*   **Automation:** Automate tests as much as possible to enable frequent execution, especially within the CI/CD pipeline.
*   **Early Testing:** Write tests concurrently with feature development (Test-Driven Development - TDD, or Behavior-Driven Development - BDD, where appropriate).
*   **Coverage:** Aim for high, meaningful test coverage of critical application logic. Coverage metrics will be tracked.
*   **Security Testing:** Integrate security testing throughout the development lifecycle (see Section 7).

## 3. Types of Tests

### 3.1. Unit Tests
*   **Scope:** Test individual functions, methods, or components in isolation.
*   **Backend (Python/FastAPI):** Test business logic, utility functions, individual API endpoint handlers (mocking external dependencies like ESI and database).
*   **Frontend (Angular):** Test individual components, services, pipes, and directives.

### 3.2. Integration Tests
*   **Scope:** Test interactions between components or modules.
*   **Backend:** Test API endpoints with a real (test) database, interactions with the caching layer (Valkey), and potentially mocked ESI interactions to verify request/response handling.
*   **Frontend:** Test component interactions, service integrations, and routing.

### 3.3. End-to-End (E2E) Tests
*   **Scope:** Test complete user flows through the deployed application (frontend through backend to database/cache).
*   **Focus:** Verify critical user scenarios, such as searching for contracts, applying filters, authenticating via EVE SSO (mocked SSO provider), managing watchlists, and receiving alerts (simulated).
*   **Caution:** E2E tests are typically slower and more brittle; reserve them for the most critical paths.

### 3.4. Performance Tests
*   **Scope:** Evaluate application responsiveness, scalability, and stability under load.
*   **Areas:** API endpoint performance, database query efficiency, ESI interaction latency impact.
*   *(Placeholder: Specific performance targets and scenarios to be defined)*

### 3.5. Usability Tests
*   *(Placeholder: To be considered, potentially manual or with user feedback sessions)*

## 4. Tools and Frameworks

*   **Backend (Python/FastAPI):**
    *   **Test Runner:** `pytest`
    *   **Mocking:** `pytest-mock`, `unittest.mock`
    *   **HTTP Client for API tests:** `httpx` (FastAPI's test client)
*   **Frontend (Angular):**
    *   **Unit Tests:** Karma (test runner), Jasmine (testing framework)
    *   **E2E Tests:** Protractor (though Angular is moving towards other solutions like Cypress or Playwright - *to be confirmed based on Angular best practices at implementation time*)
*   **Code Coverage:**
    *   Backend: `pytest-cov`
    *   Frontend: Istanbul (via Angular CLI)

## 5. Test Data Management

*   Use fixtures or factories to generate consistent test data.
*   For integration tests, use a dedicated test database that is reset before each test run or suite.
*   Avoid reliance on live ESI data for automated tests; use mocks or recorded responses.

## 6. CI/CD Integration

*   All automated tests (unit, integration, and critical E2E) MUST run as part of the Continuous Integration (CI) pipeline on every commit/merge request.
*   Builds MUST fail if tests do not pass.
*   Test coverage reports SHOULD be generated and monitored.

## 7. Security Testing

*   **Static Application Security Testing (SAST):** Integrate SAST tools (e.g., Bandit for Python, linters with security plugins) into the CI pipeline.
*   **Dynamic Application Security Testing (DAST):** Consider DAST tools for testing the running application against common web vulnerabilities.
*   **Dependency Scanning:** Use tools (e.g., `pip-audit` for Python, `npm audit` or Snyk for frontend) to check for known vulnerabilities in third-party libraries.
*   **Manual Penetration Testing:** Plan for periodic manual penetration testing by security professionals, especially before major releases.
*   Refer to `security-spec.md` for detailed security requirements that will inform security test cases.

## 8. Test Plan by Feature

*(Placeholder: This section will be populated with specific test cases and scenarios as features are defined and developed. Examples:)*
*   **EVE SSO Authentication:** Test login flow, token handling, logout.
*   **Contract Aggregation:** Test fetching, filtering, and display of contracts.
*   **Search & Filtering:** Test various search terms and filter combinations.
*   **Watchlists & Alerts:** Test creation, modification, deletion of watchlists, and alert triggering logic.
