# Feature Spec: Detailed Ship Contract View

**Feature ID:** F003
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
*   (Standard template instructions)
---

## 1. Feature Overview (Required)
*   This feature allows users to view comprehensive details of a single ship contract selected from the browsing/search results (F002). It will display all relevant information about the contract and the ship(s) it contains.

## 2. User Stories (Required)
*   Story 1: As a user, after clicking on a contract in the list view (F002), I want to see a dedicated page with all available details for that specific contract, so I can make an informed decision.
*   Story 2: As a user viewing a contract, I want to see detailed information about the ship(s) included (e.g., type, name, quantity, attributes, description from ESI), so I understand exactly what is being offered.
*   Story 3: As a user viewing a contract, I want to see all contract terms clearly (e.g., price, auction bid price if applicable, location, issuer, expiration date, volume, title), so I know the conditions of the offer.
*   Story 4: As a user, I want to easily navigate back to the search/browse results from the detailed view.

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: Clicking a contract in the F002 list view navigates the user to a unique URL for that contract's detailed view (e.g., `/contracts/{contract_id}`).
    *   Criterion 1.2: The detailed view page loads and displays information specific to the selected contract ID.
*   **Story 2 Criteria:**
    *   Criterion 2.1: For each ship item in the contract, its name, type, quantity, and relevant attributes (from `esi_type_cache.dogma_attributes`, displayed according to the 'Key Ship Attributes' and 'All Attributes' logic described in Section 15) are displayed.
    *   Criterion 2.2: The ship's ESI description is displayed.
    *   Criterion 2.3: If the contract contains multiple distinct ship types, details for each are shown.
*   **Story 3 Criteria:**
    *   Criterion 3.1: Contract price, type (auction/item_exchange), current bid (if auction and available from `contracts.current_bid`), location name, issuer name, date issued, and date expired are clearly displayed.
    *   Criterion 3.2: Contract title (if any) and total volume are displayed.
*   **Story 4 Criteria:**
    *   Criterion 4.1: A clear 'Back to results' link or breadcrumb navigation is present and functional.
*   **Story 2/3 Criteria (Additional Items):**
    *   Criterion X.X: If the contract contains additional non-ship items (as indicated by `contracts.contains_additional_items` and detailed in `contract_items`), these are listed in a dedicated 'Additional Included Items' section, showing at least item name and quantity.

## 4. Scope (Required)
### 4.1. In Scope
*   Displaying all relevant details for a single, specific public ship contract.
*   Fetching detailed contract information (if not already fully loaded by F002) from the backend.
*   Displaying detailed ship information (attributes, description) fetched from `esi_type_cache` (populated by F001).
*   Clear presentation of contract terms.
*   Navigation to/from this view.
### 4.2. Out of Scope
*   Modifying or interacting with the contract (e.g., placing bids, accepting contracts) – users do this in-game.
*   Displaying user's own private contracts or EVE Mail related to contracts.
*   Price history or market analysis for the ship type (could be a future feature).
*   Real-time updates to auction bids (data is as fresh as F001 provides).

## 5. Key Data Structures / Models (Optional, but often Required)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** If any model fields store user-facing text that might require translation (e.g., descriptions, names not from a fixed external source like ESI), ensure they are designed with internationalization in mind. Consult `../i18n-spec.md` for strategies. For F003, this applies to frontend state holding the detailed contract view and any UI-specific labels/section titles.
*   Primarily consumes data models defined in F001 (`contracts`, `contract_items`, `esi_type_cache`).
*   Frontend state (e.g., in an Angular service or component) to manage the currently viewed contract's comprehensive data, including resolved ship attributes and descriptions.

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. Relies on data aggregated by F001 and cached in `esi_type_cache`.
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `GET /api/v1/contracts/ships/{contract_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/contracts/ships/{contract_id}
    HTTP_Method: GET
    Brief_Description: Provides detailed information for a specific ship contract, including all items and resolved ship/item details.
    Request_Path_Parameters_Schema_Ref: contract_id: integer (Path parameter)
    Success_Response_Schema_Ref: DetailedShipContract (Define Pydantic model for backend, TypeScript interface for frontend. Should include full contract details from `contracts` table (including `contains_additional_items`), an array of all items from `contract_items` (both ship and non-ship), and for each item, its resolved details from `esi_type_cache` - name, description, dogma_attributes, dogma_effects, EVE image server URLs for render and icon.)
    Error_Response_Codes: 404 (Not Found - if contract_id does not exist or is not a ship contract), 500 (Internal Server Error)
    AI_Action_Focus: Backend: Implement endpoint to fetch the specified contract, join with its items, and for each item, join with `esi_type_cache` to provide comprehensive details. Frontend: Call this endpoint when navigating to the detailed view and use the response to populate the UI.
    I18n_Considerations: API error messages should be internationalized or provide keys. Data itself (ship names, descriptions) is from ESI, typically in English.
    AI_HANGAR_BAY_API_ENDPOINT_END -->

## 7. Workflow / Logic Flow (Optional)
1.  User clicks on a contract in the F002 list view.
2.  Frontend navigates to the detailed view URL (e.g., `/contracts/12345`).
3.  Frontend makes an API call to `GET /api/v1/contracts/ships/{contract_id}`.
4.  Backend retrieves the contract details and all its items from the database.
5.  For each item, backend retrieves full ship details (including attributes and description) from `esi_type_cache`.
6.  Backend constructs and returns a comprehensive JSON response.
7.  Frontend receives the data and renders the detailed contract view.

## 8. UI/UX Considerations (Optional)
*   Clear, well-organized layout to present a potentially large amount of information.
*   Sections for contract terms, ship(s) details.
*   Visual hierarchy to emphasize key information (price, ship name).
*   Display of ship renders using the EVE image server (e.g., `https://images.evetech.net/types/{type_id}/render?size=512`). A smaller icon might also be displayed.
*   Responsive design.
*   A distinct section should clearly list any 'Additional Included Items' if present, separate from the primary ship(s) details.
*   [NEEDS_DESIGN: Mockups/wireframes for the detailed contract view page.]
*   **AI Assistant Guidance:** When generating UI components, ensure all display strings are prepared for localization using Angular's i18n mechanisms (e.g., `i18n` attribute, `$localize` tagged messages) as detailed in `../i18n-spec.md`. Ensure components are designed with accessibility in mind (keyboard navigation, ARIA attributes, semantic HTML for data sections) as per `../accessibility-spec.md`.

## 9. Error Handling & Edge Cases (Required)
*   Contract ID not found (e.g., invalid URL, contract expired and cleaned up): Display a 404-like page or clear error message.
*   API errors: Display user-friendly error messages.
*   Missing ship details in cache (should be rare if F001 is robust): Display available information and perhaps a note about missing data.

## 10. Security Considerations (Required - Consult `../security-spec.md`)
*   Ensure `contract_id` path parameter is validated (e.g., as an integer) to prevent injection or path traversal type issues if the web framework doesn't handle it automatically.
*   Data displayed is from F001, so its integrity is paramount. No direct user input on this page that modifies data.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional, but Recommended - Consult `../performance-spec.md`)
*   API response time for `GET /api/v1/contracts/ships/{contract_id}` should be fast. Requires efficient querying of contract details and its items, and quick lookups in `esi_type_cache`.
*   Page load time for the detailed view should be quick.

## 12. Accessibility Considerations (Optional, but Recommended - Consult `../accessibility-spec.md`)
*   Ensure the page structure is semantic (e.g., using appropriate heading levels for sections like 'Contract Terms', 'Ship Details', 'Additional Items').
*   All interactive elements (e.g., 'Back' button, any toggles for attribute display) must be keyboard accessible.
*   Ship renders/icons (`<img>` tags) must have appropriate `alt` text (e.g., "Render of [Ship Name]").
*   Data tables or lists of attributes should be structured accessibly.
*   Sufficient color contrast for text and important visual elements.
*   Refer to `../accessibility-spec.md` for general guidelines.
*   **AI Assistant Guidance:** "Ensure the detailed view page is structured with semantic HTML. All interactive elements must be keyboard accessible. Provide meaningful `alt` text for ship images. When displaying lists of ship attributes, ensure they are presented in an accessible manner (e.g., definition lists or properly structured tables)."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `../i18n-spec.md`)
*   **Translatable Content:**
    *   All UI labels: Section titles (e.g., "Contract Details", "Ship Information", "Key Attributes", "Additional Included Items"), field labels (e.g., "Price:", "Expires:", "Issuer:"), button text (e.g., "Back to Results").
*   **Locale-Specific Formatting:**
    *   Dates (e.g., `date_issued`, `date_expired`) must be formatted according to the user's locale.
    *   Numbers (e.g., `price`, `volume`, ship attribute values if numeric) must be formatted according to the user's locale.
*   ESI-sourced data (ship names, descriptions, attribute names) will typically be in the default language fetched by F001 (e.g., English).
*   Refer to `../i18n-spec.md` for specific Angular i18n patterns.
*   **AI Assistant Guidance:** "Ensure all static user-facing strings in Angular components are externalized or marked for translation using Angular's `@angular/localize`. Use Angular's `DatePipe`, `CurrencyPipe`, `DecimalPipe` for locale-aware formatting of dates and numbers. Attribute names sourced from ESI can be displayed as-is, but UI labels for these attributes or their groupings should be translatable."

## 14. Dependencies (Optional)
*   [F001 (Public Contract Aggregation & Display)](./F001-Public-Contract-Aggregation-Display.md): Provides all underlying data.
*   [F002 (Ship Browsing & Advanced Search/Filtering)](./F002-Ship-Browsing-Advanced-Search-Filtering.md): Provides the entry point to this view.
*   Backend API.
*   Frontend framework (Angular).

## 15. Notes / Open Questions (Optional)
*   **Displaying Ship Attributes (`dogma_attributes`)**: A curated list of 'Key Ship Attributes' (e.g., resistances, EHP, capacitor, targeting, slots) will be displayed prominently. An option (e.g., 'All Attributes' toggle/tab) will allow users to view all other attributes. Attributes should be grouped logically (e.g., 'Tank', 'Capacitor').
*   **Handling Multiple Items in a 'Ship Contract'**: 
    *   The main focus will be on the primary ship item(s) with full details.
    *   A section titled 'Additional Included Items' will list all other non-primary-ship items from the contract.
    *   For these additional items, 'Item Name' (from `esi_type_cache`) and 'Quantity' will be displayed.
    *   F001 provides the `contracts.contains_additional_items` flag. This flag will be used by the backend to include all items in the API response and by the frontend to determine if the 'Additional Included Items' section should be displayed.
    *   `[POTENTIAL_ENHANCEMENT: Display a few key attributes for included non-ship items if they are modules, if data is readily available in esi_type_cache and UI impact is manageable.]`
*   **EVE Online Image Server**: The official image server `https://images.evetech.net/` will be used. 
    *   For ship renders: `types/{type_id}/render?size={size}` (e.g., size 256 or 512).
    *   For icons: `types/{type_id}/icon?size={size}` (e.g., size 64).
    *   These are CDN-backed and suitable for web use. Availability is good for ships.

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 16.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   [e.g., SQLAlchemy for joining `contracts`, `contract_items`, and `esi_type_cache` to build the detailed response.]
    *   [e.g., Pydantic for defining the `DetailedShipContract` response model.]
*   Frontend (Angular):
    *   [e.g., `ActivatedRoute` to get `contract_id` from URL, `HttpClientModule` for API calls, Angular Material components for layout and presentation (cards, lists, tables).]
    *   [e.g., Angular service to fetch detailed contract data.]
    *   [e.g., `@angular/localize` for i18n.]

### 16.2. Critical Logic Points for AI Focus
*   [e.g., Frontend: Correctly extracting `contract_id` from the route and triggering data fetch.]
*   [e.g., Frontend: Rendering the complex layout with all contract and ship details, including dynamically displaying ship attributes and images.]
*   [e.g., Frontend: Handling the 'Additional Included Items' section display logic.]
*   [e.g., Backend: Efficiently querying the database for a single contract ID and all related data from multiple tables (`contracts`, `contract_items`, `esi_type_cache`).]
*   [e.g., Backend: Constructing the EVE image server URLs for ship renders and icons based on `type_id` and desired sizes.]

### 16.3. Data Validation and Sanitization
*   [e.g., Backend: Validate `contract_id` path parameter is a valid integer.]
*   [e.g., Frontend: Gracefully handle cases where some optional data might be missing from the API response (though the API should aim to be comprehensive).]

### 16.4. Test Cases for AI to Consider Generating
*   [e.g., Frontend (Angular - Component Tests): Test rendering of all key contract details, ship attributes, ship description, and images.]
*   [e.g., Frontend: Test display of 'Additional Included Items' section when present.]
*   [e.g., Frontend: Test navigation back to search results.]
*   [e.g., Frontend: Test error handling if API returns 404 for a contract ID.]
*   [e.g., Backend (FastAPI - Integration Tests): Test the `/api/v1/contracts/ships/{contract_id}` endpoint for a valid ID, verifying the structure and accuracy of the entire JSON response, including nested item and ship details.]
*   [e.g., Backend: Test endpoint with an invalid/non-existent `contract_id` (expect 404).]

### 16.5. Specific AI Prompts or Instructions
*   [e.g., "Generate an Angular component (`ContractDetailViewComponent`) that takes a `contract_id` (e.g., via route parameter), fetches data using a service, and displays all contract and ship details as specified. Use Angular Material components for layout."]
*   [e.g., "Create an Angular service method `getContractDetails(contractId: number): Observable<DetailedShipContract>` to call the backend API endpoint."]
*   [e.g., "On the backend, implement the FastAPI route `/api/v1/contracts/ships/{contract_id}`. This route should fetch the contract, its items, and for each item, its full details from `esi_type_cache` (including `name`, `description`, `dogma_attributes`, `dogma_effects`). Construct image URLs for renders and icons. Return a `DetailedShipContract` Pydantic model."]
*   [e.g., "Develop a sub-component or template section for displaying ship attributes. It should take the `dogma_attributes` JSON from `esi_type_cache` and render them in a user-friendly, grouped manner. Include logic for a 'Key Attributes' summary and an 'All Attributes' view as per notes."]
*   [e.g., "Ensure all user-facing labels and section titles in the Angular component use `i18n` attributes or `$localize` for translation. Provide example .xlf entries."]
*   [e.g., "When displaying ship renders, use `https://images.evetech.net/types/{type_id}/render?size=512` and for icons `https://images.evetech.net/types/{type_id}/icon?size=64`. Ensure `alt` text is provided for accessibility."]
