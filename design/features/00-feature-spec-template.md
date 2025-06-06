# Feature Spec: [Feature Name]

**Feature ID:** [e.g., F001]
**Creation Date:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**Status:** [e.g., Draft, In Review, Approved, In Development, Completed]

---
**Instructions for Use:**
*   This template provides a structured format for defining individual features.
*   **Required** sections MUST be completed for every feature by filling in feature-specific details.
*   Evaluate each **Optional** section for its applicability to the current feature. If applicable, include and complete it. If not, it can be omitted or marked as "N/A".
*   Replace bracketed placeholders `[like this]` with feature-specific information.
*   The goal is to provide clear, concise, and comprehensive information to guide development and testing.
---

## 0. Authoritative ESI & EVE SSO References (Required Reading for ESI/SSO Integration)
*   **EVE Online API (ESI) Swagger UI / OpenAPI Spec:** [https://esi.evetech.net/ui/](https://esi.evetech.net/ui/) - *Primary source for all ESI endpoint definitions, request/response schemas, and parameters.*
*   **EVE Online Developers - ESI Overview:** [https://developers.eveonline.com/docs/services/esi/overview/](https://developers.eveonline.com/docs/services/esi/overview/) - *Official ESI developer documentation landing page.*
*   **EVE Online Developers - ESI Best Practices:** [https://developers.eveonline.com/docs/services/esi/best-practices/](https://developers.eveonline.com/docs/services/esi/best-practices/) - *Official ESI best practices guide.*
*   **EVE Online Developers - SSO Guidance:** [https://developers.eveonline.com/docs/services/sso/](https://developers.eveonline.com/docs/services/sso/) - *Official EVE Single Sign-On developer documentation.*

## 1. Feature Overview (Required)
*   Briefly describe the feature and its primary purpose. What problem does it solve or what value does it add?
*   [Description]

## 2. User Stories (Required)
*   List the user stories associated with this feature.
*   Format: "As a [type of user], I want to [perform an action] so that [I can achieve a goal]."
    *   Story 1: [As a...]
    *   Story 2: [As a...]
    *   ...

## 3. Acceptance Criteria (Required)
*   For each user story, define specific, measurable, achievable, relevant, and time-bound (SMART) criteria that must be met for the story to be considered complete and the feature to be accepted.
*   **Story 1 Criteria:**
    *   Criterion 1.1: [Description]
    *   Criterion 1.2: [Description]
*   **Story 2 Criteria:**
    *   Criterion 2.1: [Description]
    *   ...

## 4. Scope (Required)
### 4.1. In Scope
*   Clearly list what functionalities and components are included in this feature.
    *   [Item 1]
    *   [Item 2]
### 4.2. Out of Scope
*   Clearly list what is *not* part of this feature, to avoid scope creep. This might include related functionalities planned for later or explicitly excluded.
    *   [Item 1]
    *   [Item 2]

## 5. Key Data Structures / Models (Optional, but often Required)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** If any model fields store user-facing text that might require translation (e.g., descriptions, names not from a fixed external source like ESI), ensure they are designed with internationalization in mind. Consult `i18n-spec.md` for strategies (e.g., storing keys for translation vs. storing multiple language versions).
*   **Example Table: `watchlist_items`**
    *   `id`: INTEGER (Primary Key, Auto-increment)
    *   `user_id`: INTEGER (Foreign Key to `users` table)
    *   `ship_type_id`: INTEGER (EVE Online Type ID)
    *   `max_price`: DECIMAL
    *   `created_at`: TIMESTAMP
    *   `updated_at`: TIMESTAMP

<!-- AI_DATA_MODEL_START: ExampleModel
{
  "id": "INTEGER (Primary Key, Auto-increment, Description: Unique identifier)",
  "user_id": "INTEGER (Foreign Key to users table, Description: ID of the associated user)",
  "name": "STRING (Max length: 100, Required, Description: Name of the item)",
  "is_active": "BOOLEAN (Default: true, Description: Status flag)",
  "details": "JSONB (Optional, Description: Flexible field for additional properties)"
}
AI_DATA_MODEL_END: ExampleModel -->

## 6. API Endpoints Involved (Optional)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include structured comment blocks like the examples below for ESI and Hangar Bay APIs. -->
### 6.1. Consumed ESI API Endpoints
*   List any EVE ESI API endpoints this feature will interact with.
*   Specify:
    *   HTTP Method and Path (e.g., `GET /v1/contracts/public/{region_id}/`)
    *   Key data fields to be extracted.
    *   Relevant ESI scopes required (if any).
    *   Caching considerations.
*   **Endpoint 1:**
    *   Path: [...]
    *   Fields: [...]

<!-- AI_ESI_API_ENDPOINT_START
ESI_Endpoint_ID: GetContractsPublicRegionId
Path: GET /v1/contracts/public/{region_id}/
Purpose: Retrieve public contracts in a region.
Key_Data_Points_To_Extract: contract_id, type, issuer_id, price, volume, date_issued, date_expired, location_id
Relevant_ESI_Scopes: N/A (public)
Caching_Considerations: Adhere to ESI cache headers (typically 300s).
AI_Action_Focus: Implement robust pagination and error handling. Cache responses appropriately.
AI_Actionable_Checklist:
  - [ ] **AI Action:** Verify endpoint path, parameters, request body (if any), and response schema against the official ESI Swagger UI: [https://esi.evetech.net/ui/](https://esi.evetech.net/ui/)
  - [ ] **AI Action:** Review ESI Best Practices for this endpoint/category: [https://developers.eveonline.com/docs/services/esi/best-practices/](https://developers.eveonline.com/docs/services/esi/best-practices/)
AI_ESI_API_ENDPOINT_END -->

### 6.2. Exposed Hangar Bay API Endpoints
*   Define any new or modified backend API endpoints this feature will expose for the frontend or other services.
*   Specify:
    *   HTTP Method and Path (e.g., `POST /api/v1/watchlist`)
    *   Request Payload Structure (with example).
    *   Success Response Structure (with example, status code).
    *   Error Response Structures (with examples, status codes).
*   **Endpoint 1:**
    *   Path: [...]
    *   Request: [...]
    *   Success Response: [...]
    *   Error Responses: [...]

<!-- AI_HANGAR_BAY_API_ENDPOINT_START
Endpoint_ID: CreateWatchlistItem
Path: POST /api/v1/watchlist
Purpose: Allows an authenticated user to add an item to their watchlist.
Request_Payload_Schema_Ref: WatchlistItemCreate (Define Pydantic model for this)
Key_Request_Data_Points: ship_type_id, max_price, notification_preferences (optional)
Success_Response_Code: 201 Created
Success_Response_Schema_Ref: WatchlistItemRead (Define Pydantic model for this)
Error_Response_Codes: 400 (Bad Request - validation error), 401 (Unauthorized), 404 (User not found / Ship type not found), 409 (Conflict - item already exists)
AI_Action_Focus: Implement FastAPI endpoint with Pydantic models for request/response. Ensure proper authentication and authorization. Validate input thoroughly.
I18n_Considerations: Ensure API responses containing text for UI display are internationalized or provide keys for frontend localization as per `i18n-spec.md`.
AI_HANGAR_BAY_API_ENDPOINT_END -->

<!-- AI_HANGAR_BAY_API_ENDPOINT_START (EVE SSO Example - adapt as needed for F004)
API_Path: https://login.eveonline.com/v2/oauth/authorize (Not a direct API call, but a redirect)
HTTP_Method: GET (User's browser is redirected here)
Brief_Description: EVE Online SSO Authorization Endpoint.
Request_Query_Parameters_Schema_Ref: response_type=code, redirect_uri, client_id, scope, state, (Optional: code_challenge, code_challenge_method for PKCE)
AI_Action_Focus: Backend: Construct the correct authorization URL. Frontend: Redirect user to this URL.
I18n_Considerations: N/A for the endpoint itself, but surrounding UI text needs i18n.
AI_Actionable_Checklist:
  - [ ] **AI Action:** Verify parameters and flow against the official EVE SSO Documentation: [https://developers.eveonline.com/docs/services/sso/](https://developers.eveonline.com/docs/services/sso/)
AI_HANGAR_BAY_API_ENDPOINT_END -->

## 7. Workflow / Logic Flow (Optional)
*   Describe the step-by-step workflow or logic for the feature.
*   This can be a numbered list, a simple flowchart described in text, or pseudo-code.
*   Example:
    1.  User clicks "Add to Watchlist" on a ship.
    2.  Frontend sends request to `POST /api/v1/watchlist` with `ship_type_id` and `max_price`.
    3.  Backend validates input (user authenticated, valid `ship_type_id`, numeric `max_price`).
    4.  If validation fails, return 4xx error.
    5.  Backend stores the item in the `watchlist_items` table.
    6.  Backend returns 201 Created with the new watchlist item.

## 8. UI/UX Considerations (Optional)
*   Describe key UI elements, user interactions, or visual design considerations.
*   Reference mockups or wireframes if they exist (e.g., "Refer to mockup `watchlist-add-modal.png`").
*   Focus on what the user sees and does.
*   **Internationalization & Localization:** Describe any UI elements or text that will require translation. Note if any content needs to be adapted for different locales (e.g., date formats, number formats). Reference `i18n-spec.md` for general guidelines.
*   [Description of UI/UX elements]
*   **AI Assistant Guidance:** When generating UI components, ensure all display strings are prepared for localization using Angular's i18n mechanisms (e.g., `i18n` attribute, `$localize` tagged messages) as detailed in `i18n-spec.md`.

## 9. Error Handling & Edge Cases (Required)
*   Identify potential error conditions, edge cases, and how the system should behave.
*   Example:
    *   ESI API unavailable: System should retry X times with exponential backoff, then log error and inform user if applicable.
    *   Invalid user input (e.g., non-numeric price): Return a clear error message to the user.
    *   User attempts to add duplicate watchlist item: System should inform user item already exists.

## 10. Security Considerations (Required - Consult `security-spec.md`)
*   Identify any feature-specific security concerns and how they will be addressed.
*   Reference relevant sections in `security-spec.md` or OWASP guidelines.
*   Examples:
    *   Input validation for all user-supplied data (see Section 3 of `security-spec.md`).
    *   Ensure only authenticated users can modify their own watchlist items (Authorization).
    *   Protection against mass assignment if using ORM for data creation/updates.

## 11. Performance Considerations (Optional, but Recommended - Consult `performance-spec.md`)
*   Consult `performance-spec.md` for general application performance targets and design principles.
*   Identify any feature-specific performance requirements or potential bottlenecks not covered by the general spec.
*   Examples:
    *   **Target:** This feature's primary API endpoint should respond within X ms under Y load (refer to `performance-spec.md` for P95/P99 targets and adapt if this feature is unusually complex).
    *   **Consideration:** Large data processing for this feature might require asynchronous handling to maintain UI responsiveness (see patterns in `performance-spec.md`).
    *   **Optimization:** Identify specific database queries critical to this feature and ensure they are optimized (see indexing and query guidelines in `performance-spec.md`).

## 12. Accessibility Considerations (Optional, but Recommended - Consult `accessibility-spec.md`)
*   Identify any feature-specific accessibility challenges or requirements beyond the general guidelines in `accessibility-spec.md`.
*   Examples:
    *   **ARIA Roles & Attributes:** Specify any particular ARIA roles, states, or properties needed for custom components or complex interactions related to this feature.
    *   **Keyboard Navigation:** Detail expected keyboard interaction patterns for any interactive elements unique to this feature.
    *   **Focus Management:** Describe any specific focus management requirements, especially for dynamic content or modal dialogs.
*   **AI Assistant Guidance:** "Ensure all UI components developed for this feature adhere to WCAG 2.1 AA. Pay special attention to keyboard navigability, ARIA attributes for dynamic content, and focus management as outlined in `accessibility-spec.md` and any feature-specific notes here."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `i18n-spec.md`)
*   Identify any feature-specific internationalization or localization challenges beyond the general guidelines in `i18n-spec.md`.
*   Examples:
    *   **Translatable Content:** List specific user-facing strings, labels, or messages introduced by this feature that require translation.
    *   **Locale-Specific Formatting:** Note any data (dates, numbers, currencies) that needs locale-specific formatting.
    *   **Right-to-Left (RTL) Support:** If applicable, highlight any UI elements that might require special attention for RTL layouts.
*   **AI Assistant Guidance:** "Ensure all user-facing strings are externalized or marked for translation using the project's i18n framework (Angular's `@angular/localize` or FastAPI-Babel). Refer to `i18n-spec.md` for specific patterns and handling of pluralization or genderization if applicable."

## 14. Dependencies (Optional)
*   List any dependencies this feature has on other features, modules, or external services (beyond ESI).
*   Example:
    *   Depends on Feature F002 (User Authentication) being complete.
    *   Requires SMTP service to be configured for email notifications.

## 15. Notes / Open Questions (Optional)
*   Record any outstanding questions, assumptions made, or points for further discussion.
*   [Note 1]
*   [Question 1]

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 14.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   [e.g., `Depends` for authentication, Pydantic for data validation, SQLAlchemy for ORM]
    *   [e.g., BackgroundTasks for non-blocking operations]
    *   [e.g., FastAPI-Babel for i18n if serving translated strings directly from backend]
*   Frontend (Angular):
    *   [e.g., `HttpClientModule` for API calls, Angular Material components for UI, RxJS for state management]
    *   [e.g., `@angular/localize` for i18n]
    *   [e.g., Specific CDK features like `FocusTrap` or `LiveAnnouncer`]

### 14.2. Critical Logic Points for AI Focus
*   [e.g., Ensure atomic operations for database writes related to financial transactions (if any).]
*   [e.g., Detail specific error handling logic for ESI API rate limits or downtimes.]
*   [e.g., Algorithm for matching watchlist criteria to new contracts.]

### 14.3. Data Validation Checklist for AI (Backend)
*   Incoming data for `[Field Name 1]`: [Validation rule, e.g., must be positive integer, must be valid EVE Online type ID]
*   Incoming data for `[Field Name 2]`: [Validation rule, e.g., string, max length 255, not empty]
*   Ensure all ESI IDs are validated against known valid ranges or patterns if possible.

### 14.4. AI Testing Focus
*   **Unit Tests:**
    *   [e.g., Test all data transformation functions thoroughly.]
    *   [e.g., Mock ESI calls and test API endpoint logic in isolation.]
    *   [e.g., For Angular, test component logic, service methods.]
*   **Integration Tests:**
    *   [e.g., Test API endpoint with a test database to verify data persistence.]
    *   [e.g., Test interaction between frontend services and backend API (mocked backend).]
*   **E2E Test Scenarios (High-Level - AI can generate stubs/outlines):**
    *   [e.g., User successfully adds an item to watchlist and receives a confirmation.]
    *   [e.g., User attempts to add an item with invalid data and sees an error message.]

### 14.5. Specific AI Prompts or Instructions
*   [e.g., "When generating the service for this feature, ensure all public methods have comprehensive JSDoc/TSDoc comments."]
*   [e.g., "Pay close attention to the retry logic specified in section 9 (Error Handling) when interacting with the ESI API."]
*   [e.g., "Ensure all database interactions for this feature adhere to the query optimization and indexing guidelines in `performance-spec.md`."]
*   [e.g., "When implementing UI components for this feature, apply Angular performance best practices (OnPush, trackBy, lazy loading) as detailed in `performance-spec.md`."]
*   [e.g., "Generate all user-facing text in Angular components using i18n attributes, and provide a sample .xlf or .json entry for each new string, as per `i18n-spec.md`."]
*   [e.g., "Ensure all new UI components are keyboard accessible and include necessary ARIA attributes for screen readers, following `accessibility-spec.md`."]
