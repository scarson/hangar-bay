# Feature Spec: Watchlists

**Feature ID:** F006
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-06
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
*   This feature allows authenticated users (F004) to create and manage a personal watchlist of specific ship types. Users can add ships they are interested in, potentially specifying a maximum price they are willing to pay, to easily track their availability or price changes (though active notification is F007).

## 2. User Stories (Required)
*   Story 1: As a logged-in user, I want to add a specific ship type (e.g., "Caracal") to my watchlist, so I can keep track of it.
*   Story 2: As a logged-in user, when adding a ship to my watchlist, I want to optionally set a maximum price I'm interested in, so I can filter or be alerted (by F007) based on this price.
*   Story 3: As a logged-in user, I want to view all items currently on my watchlist, showing the ship type and my specified maximum price (if any).
*   Story 4: As a logged-in user, I want to remove an item from my watchlist when I'm no longer interested in it.
*   Story 5: As a logged-in user, I want to be able to update the maximum price for an item on my watchlist.

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: A logged-in user can select a ship type (e.g., from a search on F002, or detailed view F003, or a dedicated search modal) and add it to their watchlist.
    *   Criterion 1.2: The ship type is successfully added to the user's watchlist data.
*   **Story 2 Criteria:**
    *   Criterion 2.1: When adding a ship, an optional input field for 'maximum price' is available.
    *   Criterion 2.2: If a price is entered, it is stored with the watchlist item.
*   **Story 3 Criteria:**
    *   Criterion 3.1: A logged-in user can access a page or section displaying their watchlist items.
    *   Criterion 3.2: Each item shows the ship name/type and the user-defined maximum price (if set).
    *   Criterion 3.3: The watchlist view primarily displays user-defined information (ship type, user's max price, notes). Displaying live market data (e.g., current lowest price) directly within this view is out of scope for F006 and will be handled by features that consume watchlist data, such as F007 (Alerts/Notifications).
*   **Story 4 Criteria:**
    *   Criterion 4.1: Each watchlist item has a "Remove" or "Delete" option.
    *   Criterion 4.2: Confirming removal deletes the item from the user's watchlist.
*   **Story 5 Criteria:**
    *   Criterion 5.1: Each watchlist item has an "Edit" option for the price.
    *   Criterion 5.2: User can update the maximum price, and it's saved.

## 4. Scope (Required)
### 4.1. In Scope
*   Allowing authenticated users to add specific EVE Online ship type IDs to a personal list.
*   Allowing users to optionally associate a maximum price with each watched ship type.
*   Storing and managing these watchlist items per user.
*   Displaying the user's watchlist.
*   Allowing users to remove items from their watchlist or update the price.
*   Backend API endpoints for CRUD operations on watchlist items.
### 4.2. Out of Scope
*   Active notifications/alerts when a watched item meets criteria (this is F007).
*   Comparing watchlist items against current market contracts directly within this feature's UI (F007 might use this data; F002 is for general browsing).
*   Complex analytics on watched items.
*   Sharing watchlists.

## 5. Key Data Structures / Models (Optional, but often Required)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** If any model fields store user-facing text that might require translation (e.g., descriptions, names not from a fixed external source like ESI), ensure they are designed with internationalization in mind. Consult `../i18n-spec.md` for strategies. For F006, `notes` is user-provided data; UI labels associated with it would need i18n. `type_id` resolves to a ship name from ESI, which has its own localization handling.

*   **`watchlist_items` table:**
    <!-- AI_HANGAR_BAY_DATA_MODEL_START
    Model_Name: WatchlistItem
    Brief_Description: Stores items a user is watching, typically specific ship types with optional price targets.
    Fields:
      - id: INTEGER (Primary Key, Auto-increment)
      - user_id: INTEGER (Foreign Key to `users.id` from F004, Indexed, Not Nullable)
      - type_id: INTEGER (EVE Online Type ID of the item, typically a ship, Indexed, Not Nullable)
      - max_price: DECIMAL(19,2) (Optional, user-defined maximum price willing to pay)
      - notes: TEXT (Optional, user-defined notes for this watchlist item)
      - created_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP)
      - updated_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP, On Update: CURRENT_TIMESTAMP)
    Constraints: Unique constraint on (`user_id`, `type_id`) - a user cannot watch the same `type_id` multiple times.
    AI_Action_Focus: Backend (SQLAlchemy model, Pydantic schema for API request/response). Ensure `user_id` is correctly linked to the authenticated user. `type_id` needs validation (is it a valid, published **ship** type ID; check against `esi_type_cache` category/group ID). `max_price` validation (positive value if provided). `notes` validation (e.g. length).
    I18n_Considerations: `notes` is user data. `type_id` resolves to a name from ESI (language based on ESI request). `max_price` is numeric.
    AI_HANGAR_BAY_DATA_MODEL_END -->

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   **ESI Endpoint 1 (Conditional):** `GET /v3/universe/types/{type_id}/`
    *   **Purpose:** Used conditionally to fetch details for a specific `type_id` (e.g., ship name, description) if this information is not already available from `esi_type_cache` (F001) or frontend context when adding an item to the watchlist. This ensures the watchlist can display accurate item names.
    *   **Key_Data_Points_To_Extract:** `name`, `description`, `group_id`, `category_id`, `published`, icon/render image URLs from ESI if needed directly.
    *   **Relevant_ESI_Scopes:** Public endpoint, no specific scopes required.
    *   **Caching_Considerations:** ESI cache headers should be respected. Data is relatively static but can change with game updates.
    *   **AI_Action_Focus:** If implementing, ensure calls are made only when necessary (e.g., `type_id` not found in local `esi_type_cache` or if more detail than cached is required). Leverage existing `esi_type_cache` from F001 first. Validate `type_id` is for a published item suitable for a watchlist (e.g., a ship).
    AI_Actionable_Checklist:
      - [ ] **Developer Action:** Verify endpoint path, parameters, request body (if any), and response schema against the official ESI Swagger UI: [https://esi.evetech.net/ui/](https://esi.evetech.net/ui/)
      - [ ] **Developer Action:** Review ESI Best Practices for this endpoint/category: [https://developers.eveonline.com/docs/services/esi/best-practices/](https://developers.eveonline.com/docs/services/esi/best-practices/)
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `POST /api/v1/me/watchlist-items`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/watchlist-items
    HTTP_Method: POST
    Brief_Description: Adds a new item to the authenticated user's watchlist.
    Request_Body_Schema_Ref: WatchlistItemCreate (Pydantic model: { type_id: int, max_price: Optional[Decimal], notes: Optional[str] })
    Success_Response_Schema_Ref: WatchlistItemDisplay (Pydantic model: { id: int, type_id: int, type_name: str, max_price: Optional[Decimal], notes: Optional[str], created_at: datetime, updated_at: datetime })
    Error_Response_Codes: 201 (Created), 400 (Bad Request - e.g., invalid type_id, invalid price), 401 (Unauthorized), 409 (Conflict - if type_id already on watchlist for user, if uniqueness enforced), 500.
    AI_Action_Focus: Backend: Requires authentication. Validate `type_id` (e.g., exists, is a ship). Store new item linked to `user_id`. Frontend: Allow user to select/input `type_id` (e.g. via search or from context), input optional price/notes.
    I18n_Considerations: API error messages should be internationalized or provide keys. `type_name` in response should be localized if possible via ESI.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 2:** `GET /api/v1/me/watchlist-items`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/watchlist-items
    HTTP_Method: GET
    Brief_Description: Retrieves all watchlist items for the authenticated user.
    Request_Query_Parameters_Schema_Ref: Optional pagination parameters.
    Success_Response_Schema_Ref: List[WatchlistItemDisplay]
    Error_Response_Codes: 200 (OK), 401 (Unauthorized), 500.
    AI_Action_Focus: Backend: Requires authentication. Fetch items for `user_id`. Resolve `type_id` to `type_name` using cached ESI data. Frontend: Display list to user.
    I18n_Considerations: `type_name` in response should be localized.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 3:** `GET /api/v1/me/watchlist-items/{item_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/watchlist-items/{item_id}
    HTTP_Method: GET
    Brief_Description: Retrieves a specific watchlist item by its ID for the authenticated user.
    Request_Path_Parameters_Schema_Ref: item_id: int
    Success_Response_Schema_Ref: WatchlistItemDisplay
    Error_Response_Codes: 200 (OK), 401 (Unauthorized), 403 (Forbidden - if user does not own item), 404 (Not Found), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify ownership. Fetch item. Resolve `type_name`. Frontend: Used for viewing/editing details.
    I18n_Considerations: `type_name` in response should be localized. Error messages.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 4:** `PUT /api/v1/me/watchlist-items/{item_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/watchlist-items/{item_id}
    HTTP_Method: PUT
    Brief_Description: Updates an existing watchlist item (e.g., price, notes) for the authenticated user.
    Request_Path_Parameters_Schema_Ref: item_id: int
    Request_Body_Schema_Ref: WatchlistItemUpdate (Pydantic model: { max_price: Optional[Decimal], notes: Optional[str] } - Note: `type_id` is not updatable, user should delete and re-add if `type_id` change is needed).
    Success_Response_Schema_Ref: WatchlistItemDisplay
    Error_Response_Codes: 200 (OK), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify ownership. Update specified fields. Frontend: Allow user to edit price/notes.
    I18n_Considerations: Error messages.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 5:** `DELETE /api/v1/me/watchlist-items/{item_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/watchlist-items/{item_id}
    HTTP_Method: DELETE
    Brief_Description: Deletes a specific watchlist item for the authenticated user.
    Request_Path_Parameters_Schema_Ref: item_id: int
    Success_Response_Schema_Ref: HTTP 204 No Content.
    Error_Response_Codes: 204 (No Content), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify ownership. Delete item. Frontend: Provide delete option with confirmation.
    I18n_Considerations: Error messages.
    AI_HANGAR_BAY_API_ENDPOINT_END -->

## 7. Workflow / Logic Flow (Optional)
**Adding to Watchlist:**
1.  User is viewing a ship (e.g., on F002, F003) or uses a dedicated 'Add to Watchlist' UI.
2.  User clicks "Add to Watchlist" for a ship type.
3.  UI prompts for optional max price (and notes, if included).
4.  User confirms.
5.  Frontend sends `POST /api/v1/me/watchlist-items` with `type_id` and any optional fields.
6.  Backend validates, stores in `watchlist_items` table linked to `user_id`.

**Viewing Watchlist:**
1.  User navigates to their watchlist page.
2.  Frontend calls `GET /api/v1/me/watchlist-items`.
3.  Backend retrieves items, resolves `type_id` to names (using `esi_type_cache` from F001).
4.  Frontend displays the list.

## 8. UI/UX Considerations (Optional)
*   Easy way to add items to watchlist from various parts of the site (e.g., contract lists, detail views).
*   Clear display of watchlist items, including ship name, image (if available from ESI type info), and user's set price.
*   Intuitive controls for editing price and removing items.
*   A dedicated page for managing the watchlist.
*   [NEEDS_DESIGN: Mockups for watchlist page and add-to-watchlist interactions.] *(AI Note: This item is a reminder for the design phase. Detailed mockups will be developed by the design team.)*
*   **AI Assistant Guidance:** When generating UI components, ensure all display strings (button labels like "Add to Watchlist", "Edit", "Remove"; form labels for "Max Price", "Notes"; titles like "My Watchlist"; confirmation messages) are prepared for localization using Angular's i18n mechanisms as detailed in `../i18n-spec.md`. Ensure forms for adding/editing watchlist items and lists of these items are accessible as per `../accessibility-spec.md`.

## 9. Error Handling & Edge Cases (Required)
*   Attempting to add a non-ship item or invalid `type_id`: API should validate `type_id` against known ship types (e.g., check categoryID from `esi_type_cache`).
*   User tries to add the same `type_id` multiple times: Prevent via database unique constraint (`user_id`, `type_id`). Inform user (e.g., 'This item is already on your watchlist. You can edit the existing entry.'). API should return 409 Conflict.
*   API errors: Standard user-friendly messages.
*   User tries to manage a watchlist item not belonging to them: API returns 403/404.

## 10. Security Considerations (Required - Consult `../security-spec.md`)
*   All API endpoints must enforce authentication and authorization.
*   Input validation for `type_id`, `max_price`, `notes`.
*   Ensure `user_id` is always taken from the authenticated session, not from user input.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional, but Recommended - Consult `../performance-spec.md`)
*   Fetching watchlist for a user should be fast (indexed query on `user_id` and `type_id`).
*   If the watchlist view shows current market data for each item, this could be performance-intensive and needs careful design (likely deferred to F007 logic).

## 12. Accessibility Considerations (Optional, but Recommended - Consult `../accessibility-spec.md`)
*   Forms for adding/editing watchlist items (type selection, price, notes) must be keyboard accessible with clear labels.
*   The list of watchlist items must be navigable via keyboard.
*   Actions per item (Edit, Remove) must be clearly labeled and keyboard accessible.
*   Confirmation dialogs (e.g., for remove) must be accessible and trap focus.
*   Feedback messages (e.g., "Item added to watchlist") should be announced to screen readers.
*   Ship type information (name, image) should have appropriate alt text or ARIA labels if interactive.
*   Refer to `../accessibility-spec.md` for general guidelines.
*   **AI Assistant Guidance:** "Ensure forms for watchlist items are built with semantic HTML and proper labels. List items should be focusable and actionable via keyboard. Use ARIA attributes where necessary, especially for dynamic content or status messages. Ensure interactive elements for adding items from other views (e.g., F002/F003) are also accessible."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `../i18n-spec.md`)
*   **Translatable Content:**
    *   UI Labels: "Add to Watchlist", "My Watchlist", "Ship Type", "Max Price", "Notes", "Edit Item", "Remove Item", "Confirm Removal?", "Yes", "No", "Cancel".
    *   Prompts & Messages: "Enter max price (optional):", "Enter notes (optional):", "Item added to watchlist.", "Error: This ship is already on your watchlist."
*   Ship names (derived from `type_id`) should be fetched from ESI in the user's selected language if supported by ESI, otherwise fallback to `en-us` (see memory 723f19ed).
*   User-provided `notes` are data and should not be translated.
*   Refer to `../i18n-spec.md` for specific Angular i18n patterns.
*   **AI Assistant Guidance:** "Ensure all static user-facing strings in Angular components for managing watchlist items are externalized or marked for translation. This includes button texts, modal titles, form labels, and confirmation messages. For ship names, ensure the service fetching ESI data requests appropriate language headers."

## 14. Dependencies (Optional)
*   F001 (Public Contract Aggregation & Display): For `esi_type_cache` to resolve ship names/details.
*   F004 (User Authentication - EVE SSO): Required for all operations.
*   Backend API & Database.

## 15. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: Allow duplicate `type_id` entries per user on watchlist? Recommendation: No, make `(user_id, type_id)` unique.]
*   [NEEDS_DISCUSSION: Add a 'notes' field per watchlist item? Could be useful for users.]
*   [NEEDS_DISCUSSION: Should the main watchlist view attempt to show if contracts meeting the price criteria are currently available? This blurs lines with F007 (Alerts) and adds significant complexity to this feature's direct view. Recommendation: Keep F006 focused on managing the list of desired items/prices; F007 handles checking against market.]
*   [NEEDS_DECISION: How does a user find `type_id`s to add? Search by name within an 'add to watchlist' modal? From F002/F003 views?]

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 16.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   SQLAlchemy for DB interaction with `watchlist_items` table.
    *   Pydantic for request/response models (`WatchlistItemCreate`, `WatchlistItemUpdate`, `WatchlistItemDisplay`).
    *   FastAPI `Depends` for authentication.
    *   A shared service/cache for EVE Online `type_id` to `type_name` resolution (leveraging `esi_type_cache` from F001).
*   Frontend (Angular):
    *   `HttpClientModule` for API calls.
    *   `FormsModule` or `ReactiveFormsModule` for input fields (max price, notes).
    *   Services to encapsulate watchlist logic and API interactions.
    *   Components to display the watchlist and manage items.
    *   Mechanism to select/input `type_id` (e.g., a type-ahead search component for ship names that resolves to `type_id`, or context from F002/F003).

### 16.2. Critical Logic Points for AI Focus
*   **Backend:**
    *   CRUD operations for `watchlist_items`, strictly enforcing user ownership.
    *   Validation of `type_id`: ensure it's a valid EVE Online type ID, and potentially that it corresponds to a watchable category (e.g., ships).
    *   Validation of `max_price` (e.g., positive decimal) and `notes` (e.g., length constraints).
    *   If `(user_id, type_id)` is unique, enforce this at the database and API level.
    *   Resolving `type_id` to `type_name` for display in API responses, using a robust caching mechanism for ESI data.
*   **Frontend:**
    *   Providing a user-friendly way to specify the `type_id` to watch (e.g., search by ship name, add from contract view).
    *   Displaying the watchlist with resolved ship names and user-set data.
    *   Handling CRUD operations via the Angular service.
    *   Forms for adding/editing `max_price` and `notes`.

### 16.3. Data Validation and Sanitization
*   Backend: Validate `type_id` against ESI data (existence, category). Validate `max_price` (numeric, non-negative). Validate `notes` (length, potentially strip harmful characters if displayed raw, though typically handled by frontend templating).
*   Frontend: Basic validation for `max_price` (numeric) and `notes` input fields.

### 16.4. Test Cases for AI to Consider Generating
*   **Backend (FastAPI - Integration Tests):**
    *   Test `POST /api/v1/me/watchlist-items`: create an item, verify DB record and response (including resolved `type_name`).
    *   Test adding an item with an invalid `type_id`.
    *   Test adding an item with a `type_id` that is already on the user's watchlist (if unique constraint is active).
    *   Test `GET /api/v1/me/watchlist-items`: retrieve list, verify content and resolved names.
    *   Test `PUT /api/v1/me/watchlist-items/{item_id}`: update price/notes, test ownership.
    *   Test `DELETE /api/v1/me/watchlist-items/{item_id}`: delete item, test ownership.
    *   Test all endpoints for unauthenticated access and access by other users.
*   **Frontend (Angular - Component/Service Tests):**
    *   Test adding a ship to the watchlist (mocking `type_id` selection).
    *   Test displaying the list of watchlist items, including ship names, prices, and notes.
    *   Test updating the `max_price` or `notes` for an item.
    *   Test removing an item from the watchlist with confirmation.

### 16.5. Specific AI Prompts or Instructions
*   **Backend (FastAPI):**
    *   "Create SQLAlchemy model `WatchlistItem` and Pydantic schemas `WatchlistItemCreate`, `WatchlistItemUpdate`, `WatchlistItemDisplay`. Include `user_id` (FK), `type_id` (integer), `max_price` (Decimal), and `notes` (Text). Enforce unique constraint on `(user_id, type_id)`."
    *   "Implement FastAPI CRUD endpoints for `/api/v1/me/watchlist-items`. All endpoints require authentication and must ensure user ownership. The GET endpoints should include a resolved `type_name` for each `type_id` by querying a cached ESI type information source."
    *   "Add validation to the POST endpoint to ensure `type_id` is a valid EVE Online ship type ID."
*   **Frontend (Angular):**
    *   "Create an Angular `WatchlistService` with methods for CRUD operations on watchlist items. GET methods should expect `type_name` in the response."
    *   "Create an Angular component to display the user's watchlist. Each item should show ship name, max price, notes, and allow editing price/notes and removing the item."
    *   "Develop a mechanism for users to add items to their watchlist. This could be a modal with a ship name search that resolves to `type_id`, or buttons on F002/F003 views."
    *   "Ensure all user-facing text is internationalized. Ship names will be provided by the backend already localized if possible."
