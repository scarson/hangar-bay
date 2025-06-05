# Feature Spec: Ship Browsing & Advanced Search/Filtering

**Feature ID:** F002
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

---
**Instructions for Use:**
*   This template provides a structured format for defining individual features.
*   **Required** sections MUST be completed for every feature by filling in feature-specific details.
*   Evaluate each **Optional** section for its applicability to the current feature. If applicable, include and complete it. If not, it can be omitted or marked as "N/A".
*   Replace bracketed placeholders `[like this]` with feature-specific information.
*   The goal is to provide clear, concise, and comprehensive information to guide development and testing.
---

## 1. Feature Overview (Required)
*   This feature enables users to browse, search, and apply advanced filters to the aggregated public ship contracts. Users will be able to find specific ships or types of ship contracts based on various criteria.
*   It provides the primary user interface for interacting with the contract data collected by F001.

## 2. User Stories (Required)
*   Story 1: As a user, I want to see a paginated list of all available ship contracts, so I can browse current offerings.
*   Story 2: As a user, I want to perform a keyword search (e.g., ship name, partial name, system name), so I can quickly find specific contracts.
*   Story 3: As a user, I want to filter contracts by ship type (e.g., Frigate, Cruiser, Battleship, specific ship like "Caracal"), so I can narrow down results to ships I'm interested in.
*   Story 4: As a user, I want to filter contracts by region or solar system, so I can find contracts in specific locations.
*   Story 5: As a user, I want to filter contracts by price range, so I can find contracts within my budget.
*   Story 6: As a user, I want to filter contracts by contract type (item exchange, auction), so I can choose my preferred purchasing method.
*   Story 7: As a user, I want to sort the displayed contracts by various criteria (e.g., price, expiration date, date issued), so I can organize the results to my preference.
*   [FURTHER_DETAIL_REQUIRED: User story for viewing basic contract details in the list view.]

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: A default view displays ship contracts in a paginated list.
    *   Criterion 1.2: Each item in the list shows key information (e.g., ship name, price, location, expiration).
    *   Criterion 1.3: Pagination controls (next, previous, page number) are functional.
*   **Story 2 Criteria:**
    *   Criterion 2.1: A search bar is available for keyword input.
    *   Criterion 2.2: Search results update to show contracts matching the keyword in relevant fields (ship name, title, location name [NEEDS_DISCUSSION: which fields?]).
*   **Story 3 Criteria:**
    *   Criterion 3.1: Filtering options for ship categories (e.g., Frigate, Destroyer) and specific ship types (via dropdown or autocomplete) are available.
    *   Criterion 3.2: Applying a ship type filter updates the contract list accordingly.
*   **Story 4 Criteria:**
    *   Criterion 4.1: Filtering options for EVE regions and solar systems are available.
    *   Criterion 4.2: Applying a location filter updates the contract list.
*   **Story 5 Criteria:**
    *   Criterion 5.1: Input fields for minimum and maximum price are available.
    *   Criterion 5.2: Applying a price filter updates the contract list.
*   **Story 6 Criteria:**
    *   Criterion 6.1: Filtering options for contract type (item exchange, auction) are available.
    *   Criterion 6.2: Applying a contract type filter updates the contract list.
*   **Story 7 Criteria:**
    *   Criterion 7.1: Sorting controls are available for price (asc/desc), expiration date (asc/desc), and date issued (asc/desc).
    *   Criterion 7.2: Applying a sort order updates the contract list.

## 4. Scope (Required)
### 4.1. In Scope
*   User interface for displaying a list of ship contracts.
*   Keyword search functionality.
*   Filtering by: ship type/category, region/solar system, price range, contract type.
*   Sorting of contract list.
*   Pagination of contract list.
*   Display of basic contract details in the list view.
*   Interaction with backend API to fetch and filter contract data.
### 4.2. Out of Scope
*   Detailed contract view (F003).
*   User authentication (F004) or personalized features (F005, F006, F007).
*   Saving searches (F005).
*   Real-time updates (data is as fresh as F001 provides).
*   Complex query language for search; simple keyword and predefined filters only for now.

## 5. Key Data Structures / Models (Optional, but often Required)
*   This feature primarily consumes data models defined in F001 (`contracts`, `contract_items`, `esi_type_cache`).
*   Frontend state management for search terms, filter values, sort order, pagination.

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. Relies on data aggregated by F001. May indirectly consume ESI type/location resolution if not fully cached/provided by backend.
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `GET /api/v1/contracts/ships` (as defined in F001, but with extended query parameters)
    *   Request:
        *   Query parameters for pagination (e.g., `page`, `limit`).
        *   Query parameters for search (e.g., `q` for keyword).
        *   Query parameters for filtering (e.g., `ship_type_id`, `ship_category_id`, `region_id`, `system_id`, `min_price`, `max_price`, `contract_type`).
        *   Query parameters for sorting (e.g., `sort_by=price`, `sort_order=asc`).
    *   Success Response: JSON array of ship contracts matching criteria. Status 200.
    *   Error Responses: Standard API error responses.

## 7. Workflow / Logic Flow (Optional)
1.  User navigates to the ship browsing page.
2.  Frontend makes an initial API call to `GET /api/v1/contracts/ships` with default parameters (e.g., page 1, default sort).
3.  Backend queries the database (data populated by F001) based on parameters and returns a paginated list of contracts.
4.  Frontend displays the list.
5.  User interacts with search input, filter controls, or sort options.
6.  Frontend makes a new API call to `GET /api/v1/contracts/ships` with updated parameters.
7.  Backend re-queries and returns the updated list.
8.  Frontend updates the display.

## 8. UI/UX Considerations (Optional)
*   Clear layout for contract list, search bar, filter panel.
*   Responsive design for various screen sizes.
*   Intuitive filter controls (dropdowns, sliders for price range, checkboxes).
*   Indication of active filters.
*   Loading indicators during API calls.
*   Clear pagination controls.
*   Each contract entry in the list should be clickable to navigate to the detailed view (F003).
*   [NEEDS_DESIGN: Mockups/wireframes for the browsing interface.]

## 9. Error Handling & Edge Cases (Required)
*   API errors (backend unavailable, invalid request): Display user-friendly error messages.
*   No results found: Display a clear "no results" message.
*   Invalid filter combinations: Prevent or handle gracefully.
*   Performance with large datasets: Ensure UI remains responsive even if backend takes time; consider debouncing search input.

## 10. Security Considerations (Required)
*   All user inputs (search terms, filter values) must be validated and sanitized on the backend before being used in database queries to prevent injection attacks (e.g., NoSQL injection if applicable, though primarily SQL with F001).
*   Ensure API endpoints do not expose sensitive information not intended for public view.
*   Rate limiting on API endpoints if abuse is a concern.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional)
*   API response times for `GET /api/v1/contracts/ships` should be fast, even with multiple filters. This implies efficient database indexing on `contracts` and related tables (as per F001).
*   Frontend rendering performance for large lists (virtual scrolling if necessary, though pagination should mitigate this).
*   Minimize data transferred; only fetch necessary fields for the list view.

## 12. Dependencies (Optional)
*   F001 (Public Contract Aggregation & Display): Provides the data.
*   F003 (Detailed Ship Contract View): For navigation from list items.
*   Backend API.
*   Frontend framework (Angular).

## 13. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: Specific fields to include in the list view for each contract.]
*   [NEEDS_DECISION: Default sort order.]
*   [NEEDS_DISCUSSION: How to handle filtering by ship attributes (e.g., meta level, tech level) if desired in the future? Requires more detailed `esi_type_cache` and backend logic.]
*   [NEEDS_DISCUSSION: Exact list of filterable ship categories/groups. Should this be dynamic based on available data or a fixed list?]
