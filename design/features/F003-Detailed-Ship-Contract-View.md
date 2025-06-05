# Feature Spec: Detailed Ship Contract View

**Feature ID:** F003
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

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
    *   Criterion 2.1: For each ship item in the contract, its name, type, quantity, and relevant attributes (e.g., from `esi_type_cache`'s `dogma_attributes`) are displayed.
    *   Criterion 2.2: The ship's ESI description is displayed.
    *   Criterion 2.3: If the contract contains multiple distinct ship types, details for each are shown.
*   **Story 3 Criteria:**
    *   Criterion 3.1: Contract price, type (auction/item_exchange), current bid (if auction and available), location name, issuer name, date issued, and date expired are clearly displayed.
    *   Criterion 3.2: Contract title (if any) and total volume are displayed.
*   **Story 4 Criteria:**
    *   Criterion 4.1: A clear 'Back to results' link or breadcrumb navigation is present and functional.

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
*   Primarily consumes data models defined in F001 (`contracts`, `contract_items`, `esi_type_cache`).
*   Frontend state to manage the currently viewed contract's data.

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. Relies on data aggregated by F001 and cached in `esi_type_cache`.
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `GET /api/v1/contracts/ships/{contract_id}`
    *   Request: Path parameter `contract_id`.
    *   Success Response: JSON object containing detailed information for the specified contract, including all items and their resolved ship details (name, attributes, description from `esi_type_cache`). Status 200.
    *   Error Responses: 404 if contract not found or not a ship contract; standard API errors.

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
*   [NEEDS_DESIGN: Mockups/wireframes for the detailed contract view page.]

## 9. Error Handling & Edge Cases (Required)
*   Contract ID not found (e.g., invalid URL, contract expired and cleaned up): Display a 404-like page or clear error message.
*   API errors: Display user-friendly error messages.
*   Missing ship details in cache (should be rare if F001 is robust): Display available information and perhaps a note about missing data.

## 10. Security Considerations (Required)
*   Ensure `contract_id` path parameter is validated (e.g., as an integer) to prevent injection or path traversal type issues if the web framework doesn't handle it automatically.
*   Data displayed is from F001, so its integrity is paramount. No direct user input on this page that modifies data.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional)
*   API response time for `GET /api/v1/contracts/ships/{contract_id}` should be fast. Requires efficient querying of contract details and its items, and quick lookups in `esi_type_cache`.
*   Page load time for the detailed view should be quick.

## 12. Dependencies (Optional)
*   F001 (Public Contract Aggregation & Display): Provides all underlying data.
*   F002 (Ship Browsing & Advanced Search/Filtering): Provides the entry point to this view.
*   Backend API.
*   Frontend framework (Angular).

## 13. Notes / Open Questions (Optional)
*   **Displaying Ship Attributes (`dogma_attributes`)**: A curated list of 'Key Ship Attributes' (e.g., resistances, EHP, capacitor, targeting, slots) will be displayed prominently. An option (e.g., 'All Attributes' toggle/tab) will allow users to view all other attributes. Attributes should be grouped logically (e.g., 'Tank', 'Capacitor').
*   **Handling Multiple Items in a 'Ship Contract'**: 
    *   The main focus will be on the primary ship item(s) with full details.
    *   A section titled 'Additional Included Items' will list all other non-primary-ship items from the contract.
    *   For these additional items, 'Item Name' (from `esi_type_cache`) and 'Quantity' will be displayed.
    *   F001's `is_ship_contract` logic should correctly identify contracts primarily for ships. Consider adding a boolean like `contains_additional_items` at the contract level in the Hangar Bay DB, derived by F001.
    *   `[POTENTIAL_ENHANCEMENT: Display a few key attributes for included non-ship items if they are modules, if data is readily available in esi_type_cache and UI impact is manageable.]`
*   **EVE Online Image Server**: The official image server `https://images.evetech.net/` will be used. 
    *   For ship renders: `types/{type_id}/render?size={size}` (e.g., size 256 or 512).
    *   For icons: `types/{type_id}/icon?size={size}` (e.g., size 64).
    *   These are CDN-backed and suitable for web use. Availability is good for ships.
