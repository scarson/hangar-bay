# Feature Spec: Ship Browsing & Advanced Search/Filtering

**Feature ID:** F002
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

## 0. Authoritative ESI & EVE SSO References (Required Reading for ESI/SSO Integration)
*   **EVE Online API (ESI) Swagger UI / OpenAPI Spec:** [https://esi.evetech.net/ui/](https://esi.evetech.net/ui/) - *Primary source for all ESI endpoint definitions, request/response schemas, and parameters.*
*   **EVE Online Developers - ESI Overview:** [https://developers.eveonline.com/docs/services/esi/overview/](https://developers.eveonline.com/docs/services/esi/overview/) - *Official ESI developer documentation landing page.*
*   **EVE Online Developers - ESI Best Practices:** [https://developers.eveonline.com/docs/services/esi/best-practices/](https://developers.eveonline.com/docs/services/esi/best-practices/) - *Official ESI best practices guide.*
*   **EVE Online Developers - SSO Guidance:** [https://developers.eveonline.com/docs/services/sso/](https://developers.eveonline.com/docs/services/sso/) - *Official EVE Single Sign-On developer documentation.*

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
*   Story 3: As a user, I want to filter contracts by specific ship types (e.g., "Caracal", "Tristan") using dropdowns or autocomplete, so I can narrow down results to particular ships I'm interested in.
*   Story 4: As a user, I want to filter contracts by broad ship categories (e.g., Frigate, Cruiser, Battleship), so I can quickly narrow down results to general classes of ships.
*   Story 5: As a user, I want to filter contracts by region or solar system, so I can find contracts in specific locations.
*   Story 6: As a user, I want to filter contracts by price range, so I can find contracts within my budget.
*   Story 7: As a user, I want to filter contracts by contract type (item exchange, auction), so I can choose my preferred purchasing method.
*   Story 8: As a user, I want to sort the displayed contracts by various criteria (e.g., price, expiration date, date issued), so I can organize the results to my preference.
*   Story 9: As a user, I want to see an indicator on contracts that include additional non-ship items, and optionally filter by this, so I can distinguish between ship-only deals and packages.

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: A default view displays ship contracts in a paginated list.
    *   Criterion 1.2: Each item in the list shows key information as detailed in Section 15's 'Specific fields for list view' (Ship Type, Quantity, Total Price, Contract Type, Location, Time Remaining, Issuer Name).
    *   Criterion 1.3: Pagination controls (next, previous, page number) are functional.
*   **Story 2 Criteria:**
    *   Criterion 2.1: A search bar is available for keyword input.
    *   Criterion 2.2: Search results update to show contracts matching the keyword in the following fields: `contracts.title`, `contracts.start_location_name` (from F001), and the primary ship's name (derived from `esi_type_cache.name` via `contract_items`).
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
*   **Story 4 & New Story (Ship Category Filtering) Criteria:**
    *   Criterion 4.1 (was Story 3): Filtering options for specific ship types (via dropdown or autocomplete) are available.
    *   Criterion 4.2 (was Story 3): Applying a specific ship type filter updates the contract list accordingly.
    *   Criterion 4.3: Filtering options for broad ship market groups/categories (e.g., Frigate, Cruiser) are available, sourced from a cached list of EVE market groups.
    *   Criterion 4.4: Applying a ship category filter updates the contract list accordingly.
    *   Criterion 4.5: A backend endpoint (e.g., `/api/v1/ships/market_groups`) provides the list of filterable ship categories.
*   **Story 9 (Additional Items Indicator/Filter) Criteria:**
    *   Criterion 9.1: Contracts in the list view display a visual indicator if `contracts.contains_additional_items` (from F001) is true.
    *   Criterion 9.2: A filtering option (e.g., checkbox 'Includes other items') is available to show only contracts with additional items, only contracts without them, or both.
    *   Criterion 9.3: Applying this filter updates the contract list.

## 4. Scope (Required)
### 4.1. In Scope
*   User interface for displaying a list of ship contracts.
*   Keyword search functionality.
*   Filtering by: ship type/category, region/solar system, price range, contract type.
*   Sorting of contract list.
*   Pagination of contract list.
*   Display of basic contract details in the list view.
*   Interaction with backend API to fetch and filter contract data.
*   Filtering by broad ship categories (e.g., Frigate, Cruiser).
*   Displaying an indicator for contracts containing additional non-ship items, and filtering based on this.
### 4.2. Out of Scope
*   Detailed contract view (F003).
*   User authentication (F004) or personalized features (F005, F006, F007).
*   Saving searches (F005).
*   Real-time updates (data is as fresh as F001 provides).
*   Complex query language for search; simple keyword and predefined filters only for now.

## 5. Key Data Structures / Models (Optional, but often Required)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** If any model fields store user-facing text that might require translation (e.g., descriptions, names not from a fixed external source like ESI), ensure they are designed with internationalization in mind. Consult `../i18n-spec.md` for strategies. For F002, this primarily applies to any frontend-specific state or labels not directly from API data.
*   This feature primarily consumes data models defined in F001 (`contracts`, `contract_items`, `esi_type_cache`).
*   Frontend state management for search terms, filter values, sort order, pagination (e.g., using Angular services or component state).

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. Relies on data aggregated by F001. May indirectly consume ESI type/location resolution if not fully cached/provided by backend.
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `GET /api/v1/contracts/ships` (as defined in F001, but with extended query parameters)
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/contracts/ships
    HTTP_Method: GET
    Brief_Description: Provides a list of aggregated ship contracts, supporting advanced search, filtering, sorting, and pagination.
    Request_Query_Parameters_Schema_Ref: ShipContractQueryFilters (Backend validation will use a Pydantic model named `ShipContractQueryFilters`.)
        - page: integer (optional, default 1)
        - limit: integer (optional, default 20)
        - q: string (optional, keyword search)
        - ship_type_id: integer (optional) // For specific EVE Type ID of a ship
        - ship_market_group_id: integer (optional) // For broad EVE Market Group ID (e.g., Frigate, Cruiser)
        - region_id: integer (optional)
        - system_id: integer (optional)
        - min_price: decimal (optional)
        - max_price: decimal (optional)
        - contract_type: string (enum: 'item_exchange', 'auction', optional)
        - contains_additional_items: boolean (optional) // Filter based on the F001 flag
        - sort_by: string (enum: 'price', 'expiration_date', 'date_issued', optional, default 'expiration_date')
        - sort_order: string (enum: 'asc', 'desc', optional, default 'asc' for expiration_date, 'desc' for date_issued, 'asc' for price)
    Success_Response_Schema_Ref: PaginatedShipContractList (as per F001, containing key details for list view)
    Error_Response_Codes: 400 (Bad Request - validation error), 500 (Internal Server Error)
    AI_Action_Focus: Backend: Enhance F001's endpoint to support these additional query parameters for filtering and sorting against the `contracts` table and related data. Ensure efficient database queries with appropriate indexing. Frontend: Construct API requests based on user UI interactions.
    I18n_Considerations: API responses containing text for UI display (e.g., error messages not handled by frontend) should be internationalized or provide keys for frontend localization as per `../i18n-spec.md`. Data itself (ship names, etc.) is from ESI, typically in English.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 2:** `GET /api/v1/ships/market_groups`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/ships/market_groups
    HTTP_Method: GET
    Brief_Description: Provides a list of filterable ship market groups/categories (e.g., Frigate, Cruiser) for UI dropdowns.
    Request_Query_Parameters_Schema_Ref: N/A
    Success_Response_Schema_Ref: List[ShipMarketGroup] (Pydantic model: ShipMarketGroup with fields like group_id, group_name, parent_group_id)
    Error_Response_Codes: 500 (Internal Server Error, e.g., if cache is unavailable or data not populated)
    AI_Action_Focus: Implement FastAPI endpoint to serve cached ship market group data. Data is populated by a separate backend task (defined in F002, Section 15 notes initially, now part of core logic).
    I18n_Considerations: Group names are from ESI, typically in English.
    AI_HANGAR_BAY_API_ENDPOINT_END -->

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
*   A clear visual indicator (e.g., an icon or badge) should be present on list items for contracts that include additional non-ship items.
*   The filter panel should include distinct options for filtering by specific ship types (e.g., autocomplete search for 'Caracal') and by broad ship categories (e.g., dropdown for 'Frigates', 'Cruisers'). It should also include a filter for 'includes other items'.
*   [NEEDS_DESIGN: Mockups/wireframes for the browsing interface.]
*   **AI Assistant Guidance:** When generating UI components, ensure all display strings are prepared for localization using Angular's i18n mechanisms (e.g., `i18n` attribute, `$localize` tagged messages) as detailed in `../i18n-spec.md`. Ensure components are designed with accessibility in mind (keyboard navigation, ARIA attributes) as per `../accessibility-spec.md`.

## 9. Error Handling & Edge Cases (Required)
*   API errors (backend unavailable, invalid request): Display user-friendly error messages.
*   No results found: Display a clear "no results" message.
*   Invalid filter combinations: Prevent or handle gracefully.
*   Performance with large datasets: Ensure UI remains responsive even if backend takes time; consider debouncing search input.

## 10. Security Considerations (Required - Consult `../security-spec.md`)
*   All user inputs (search terms, filter values) must be validated and sanitized on the backend before being used in database queries to prevent injection attacks (e.g., NoSQL injection if applicable, though primarily SQL with F001).
*   Ensure API endpoints do not expose sensitive information not intended for public view.
*   Rate limiting on API endpoints if abuse is a concern.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional, but Recommended - Consult `../performance-spec.md`)
*   API response times for `GET /api/v1/contracts/ships` should be fast, even with multiple filters. This implies efficient database indexing on `contracts` and related tables (as per F001).
*   Frontend rendering performance for large lists (virtual scrolling if necessary, though pagination should mitigate this).
*   Minimize data transferred; only fetch necessary fields for the list view.

## 12. Accessibility Considerations (Optional, but Recommended - Consult `../accessibility-spec.md`)
*   Ensure all interactive elements (search input, filter dropdowns/buttons, sort controls, pagination) are fully keyboard accessible.
*   Use appropriate ARIA attributes for dynamic regions (e.g., the contract list updating), filter states, and interactive controls.
*   Ensure sufficient color contrast for text and UI elements.
*   Provide clear visual focus indicators.
*   Test with screen readers to ensure a good user experience.
*   Refer to `../accessibility-spec.md` for general guidelines and specific patterns.
*   **AI Assistant Guidance:** "Ensure all UI components developed for this feature adhere to WCAG 2.1 AA. Pay special attention to keyboard navigability, ARIA attributes for dynamic content (e.g., `aria-live` for search results), and focus management as outlined in `../accessibility-spec.md` and any feature-specific notes here. For example, when search results update, announce this to screen reader users."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `../i18n-spec.md`)
*   **Translatable Content:**
    *   All UI labels, button texts, placeholder texts, messages (e.g., "No results found", error messages) must be translatable.
    *   Column headers in the contract list.
*   **Locale-Specific Formatting:**
    *   Dates (e.g., expiration date, date issued) must be formatted according to the user's locale.
    *   Numbers (e.g., price) must be formatted according to the user's locale (currency symbol, decimal/thousands separators).
*   **Right-to-Left (RTL) Support:** Consider layout adjustments if RTL languages are to be supported.
*   Refer to `../i18n-spec.md` for specific Angular i18n patterns.
*   **AI Assistant Guidance:** "Ensure all user-facing strings in Angular components are externalized or marked for translation using Angular's `@angular/localize` (e.g., `i18n` attributes, `$localize` calls). Use Angular's `DatePipe`, `CurrencyPipe`, `DecimalPipe` for locale-aware formatting of dates and numbers. Refer to `../i18n-spec.md` for specific patterns."

## 14. Dependencies (Optional)
*   [F001 (Public Contract Aggregation & Display)](./F001-Public-Contract-Aggregation-Display.md): Provides the data.
*   [F003 (Detailed Ship Contract View)](./F003-Detailed-Ship-Contract-View.md): For navigation from list items.
*   Backend API.
*   Frontend framework (Angular).

## 15. Notes / Open Questions (Optional)
*   **Specific fields for list view**: Based on common EVE tools and F001 data, the list view will initially display:
    *   Ship Type (e.g., "Tristan", "Raven")
    *   Quantity (if >1 of same type, else 1)
    *   Total Price (contract price)
    *   Contract Type ("Auction" or "Item Exchange")
    *   Location (e.g., "Jita IV - Moon 4 - Caldari Navy Assembly Plant")
    *   Time Remaining (e.g., "2 days 4 hours", "12 hours")
    *   Issuer Name (Character name)
*   **Default sort order**: The default sort order for the contract list will be by **expiration date (soonest first)**. Users will be able to click column headers to change sorting.
*   **Filtering by ship attributes (e.g., meta level, tech level)**: This is a desirable future enhancement.
    *   **Data Source**: The `esi_type_cache` (from F001) will store all `dogma_attributes` for each ship type, which includes attributes like 'meta level' (dogma attribute ID 633) and 'tech level' (dogma attribute ID 422).
    *   **Backend Logic Required**:
        1.  **Attribute Mapping**: Maintain a backend configuration mapping user-friendly filter names (e.g., "meta_level") to their corresponding ESI dogma attribute IDs.
        2.  **API Enhancements**: The `/api/v1/contracts/ships` endpoint will accept new filter parameters (e.g., `meta_level_eq`, `tech_level_eq`).
        3.  **Database Query**: The backend will join `contracts` with `contract_items` and `esi_type_cache`. Queries will use JSON functions to extract and compare values from the `dogma_attributes` field in `esi_type_cache` against the provided filter parameters.
        4.  **Performance**: Consider GIN indexes (PostgreSQL) or expression indexes on the JSON `dogma_attributes` field if query performance becomes a concern.
*   **Filterable ship categories/groups**: This is now part of the MVP scope. The backend will periodically fetch ship market groups from ESI (`GET /v1/markets/groups/`), cache them, and provide them to the frontend via the `/api/v1/ships/market_groups` endpoint. Filtering will use the `ship_market_group_id` parameter against data in `esi_type_cache`.
*   **Indicator/Filter for Contracts with Additional Items**: F001 will provide a `contains_additional_items` flag for each contract. Consider using this in F002's UI to:
    *   Display an icon/indicator on list items if a ship contract also includes other non-ship items.
    *   Potentially offer a filter option (e.g., "Show only contracts with additional items" or "Hide contracts with additional items"). This is a lower priority enhancement for now.

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 16.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   [e.g., Pydantic for validating query parameters for the `/api/v1/contracts/ships` endpoint.]
    *   [e.g., SQLAlchemy for constructing dynamic queries based on filter parameters.]
*   Frontend (Angular):
    *   [e.g., `HttpClientModule` for API calls, Angular Material components for UI (table, pagination, form fields, buttons, dropdowns), RxJS for state management and handling asynchronous operations (e.g., debouncing search input).]
    *   [e.g., Angular Forms (`ReactiveFormsModule` or `FormsModule`) for managing search and filter inputs.]
    *   [e.g., `@angular/cdk/collections` for `DataSource` if using Material table, or virtual scrolling if lists become very long before pagination.]
    *   [e.g., `@angular/localize` for i18n.]

### 16.2. Critical Logic Points for AI Focus
*   [e.g., Frontend: State management for all search/filter criteria and pagination state.]
*   [e.g., Frontend: Constructing the correct API request to `/api/v1/contracts/ships` based on current UI state.]
*   [e.g., Frontend: Efficiently rendering the contract list and updating it when data changes.]
*   [e.g., Frontend: Implementing client-side aspects of sorting and pagination in conjunction with backend capabilities.]
*   [e.g., Backend: Parsing and validating all query parameters for the `/api/v1/contracts/ships` endpoint.]
*   [e.g., Backend: Building dynamic, performant SQL queries using SQLAlchemy based on the provided filters and search terms. Pay attention to potential performance issues with many optional filter conditions.]

### 16.3. Data Validation and Sanitization
*   [e.g., Frontend: Basic client-side validation for inputs like price range (e.g., min price <= max price).]
*   [e.g., Backend: Robust validation of all query parameters (type, range, enum values) using Pydantic or FastAPI's dependency injection features.]
*   [e.g., Backend: Ensure search terms are handled safely in SQL queries (SQLAlchemy generally handles this, but be mindful of how LIKE clauses are constructed if building raw SQL fragments).]

### 16.4. Test Cases for AI to Consider Generating
*   [e.g., Frontend (Angular - Component Tests): Test that filter changes trigger API calls with correct parameters.]
*   [e.g., Frontend: Test that pagination controls work correctly and update the displayed data.]
*   [e.g., Frontend: Test that sorting by different columns updates the API request and display.]
*   [e.g., Frontend: Test UI behavior for 'no results found' and API error states.]
*   [e.g., Frontend: Test accessibility features (keyboard navigation, ARIA attributes on generated components).]
*   [e.g., Backend (FastAPI - Integration Tests): Test the `/api/v1/contracts/ships` endpoint with various combinations of filters, search terms, sorting, and pagination parameters, verifying the SQL queries generated (if possible) and the correctness of the response.]

### 16.5. Specific AI Prompts or Instructions
*   [e.g., "Generate an Angular service (`ContractSearchService`) to manage API calls to `/api/v1/contracts/ships`, handle state for filters, search terms, pagination, and sorting. Use RxJS BehaviorSubjects for reactive state management."]
*   [e.g., "Create an Angular component (`ContractListComponent`) that displays the paginated list of contracts using Angular Material table, including sortable columns. It should consume the `ContractSearchService`."]
*   [e.g., "Create an Angular component (`ContractFilterPanelComponent`) containing controls for all specified filters (ship type, location, price, etc.) and emitting filter change events to be handled by a parent component or service."]
*   [e.g., "On the backend, extend the FastAPI route for `/api/v1/contracts/ships` to accept and process all new filter parameters. Ensure that database queries are constructed dynamically and efficiently using SQLAlchemy, leveraging indexes defined in F001."]
*   [e.g., "Implement keyword search functionality on the backend. The search should target fields like ship name (from `esi_type_cache`), contract title, and location name (resolved, potentially from a dedicated location cache as noted in F001). Consider using `ILIKE` for case-insensitive search in PostgreSQL."]
*   [e.g., "Ensure all user-facing text in generated Angular components uses `i18n` attributes or `$localize` for translation, and provide example entries for a localization file (e.g., .xlf) for new strings."]
*   [e.g., "When implementing UI components for this feature, apply Angular performance best practices (OnPush change detection, `trackBy` for lists) as detailed in `../performance-spec.md`."]
