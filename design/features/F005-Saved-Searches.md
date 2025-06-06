# Feature Spec: Saved Searches

**Feature ID:** F005
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
*   This feature allows authenticated users (via F004) to save their currently applied search criteria (keywords and filters from F002) for quick re-execution later. Users can name their saved searches and manage them.

## 2. User Stories (Required)
*   Story 1: As a logged-in user, I want to be able to save my current search (keywords and applied filters) with a custom name, so I can easily run the same search again in the future.
*   Story 2: As a logged-in user, I want to see a list of my saved searches, so I can choose one to execute.
*   Story 3: As a logged-in user, when I click on a saved search, I want the search criteria to be applied and the results displayed (as in F002), so I don't have to manually re-enter them.
*   Story 4: As a logged-in user, I want to be able to delete a saved search I no longer need, so I can manage my list of saved searches.
*   Story 5: As a logged-in user, I might want to update an existing saved search (e.g., rename it, or update its criteria) [NEEDS_DISCUSSION: Scope for MVP - update criteria or just rename/delete?].

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: While viewing search results (F002), a logged-in user has a "Save Search" button/option.
    *   Criterion 1.2: Clicking "Save Search" prompts the user to enter a name for the search.
    *   Criterion 1.3: Upon providing a name and confirming, the current search parameters (keywords, filters) are stored against the user's account with the given name.
*   **Story 2 Criteria:**
    *   Criterion 2.1: A logged-in user can access a page or section displaying their saved searches (e.g., in a user dashboard or dropdown menu).
    *   Criterion 2.2: Each saved search in the list displays its name.
*   **Story 3 Criteria:**
    *   Criterion 3.1: Clicking on a saved search name/link automatically populates the search/filter controls (F002) with the saved criteria.
    *   Criterion 3.2: The search results are automatically updated based on these applied criteria.
*   **Story 4 Criteria:**
    *   Criterion 4.1: Each saved search in the list has a "Delete" option.
    *   Criterion 4.2: Confirming deletion removes the saved search from the user's account.
*   **Story 5 Criteria (If in scope for MVP):**
    *   Criterion 5.1: An option to "Edit" or "Rename" a saved search is available.
    *   Criterion 5.2: Renaming updates the saved search's name.
    *   Criterion 5.3: [If updating criteria is in scope] Editing allows modification of the saved search parameters and re-saving.

## 4. Scope (Required)
### 4.1. In Scope
*   Storing named search parameter sets (keywords, selected filters from F002) per authenticated user.
*   Listing, applying (re-executing), and deleting saved searches for the logged-in user.
*   UI elements for saving, listing, applying, and deleting saved searches.
*   Backend API endpoints to support these operations.
*   Renaming saved searches.
### 4.2. Out of Scope
*   Sharing saved searches with other users.
*   Automatic notifications based on saved searches (this is F007 - Alerts/Notifications).
*   Complex management features like tagging or organizing saved searches into folders (future enhancement).
*   Updating the criteria of an existing saved search by overwriting with current filters (MVP might only support rename/delete, then re-save as new). [NEEDS_DECISION]

## 5. Key Data Structures / Models (Optional, but often Required)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** If any model fields store user-facing text that might require translation (e.g., descriptions, names not from a fixed external source like ESI), ensure they are designed with internationalization in mind. Consult `../i18n-spec.md` for strategies. For F005, the `name` field of `saved_searches` is user-provided data; UI labels associated with it would need i18n.

*   **`saved_searches` table:**
    <!-- AI_HANGAR_BAY_DATA_MODEL_START
    Model_Name: SavedSearch
    Brief_Description: Stores user-defined saved search criteria.
    Fields:
      - id: INTEGER (Primary Key, Auto-increment)
      - user_id: INTEGER (Foreign Key to `users.id` from F004, Indexed, Not Nullable)
      - name: VARCHAR(255) (User-defined name for the search, Not Nullable)
      - search_parameters: JSONB (Stores the actual search criteria from F002, Not Nullable)
      - created_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP)
      - updated_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP, On Update: CURRENT_TIMESTAMP)
    Constraints: Unique constraint on (`user_id`, `name`) - a user cannot have two saved searches with the same name.
    AI_Action_Focus: Backend (SQLAlchemy model, Pydantic schema for API request/response). Ensure `user_id` is correctly linked to the authenticated user. `search_parameters` will store the filter state from F002.
    I18n_Considerations: `name` is user data. `search_parameters` are internal filter values.
    AI_HANGAR_BAY_DATA_MODEL_END -->

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A for this feature directly.
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `POST /api/v1/me/saved-searches`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/saved-searches
    HTTP_Method: POST
    Brief_Description: Creates a new saved search for the authenticated user.
    Request_Body_Schema_Ref: SavedSearchCreate (Pydantic model: { name: str, search_parameters: dict })
    Success_Response_Schema_Ref: SavedSearch (Pydantic model: { id: int, name: str, search_parameters: dict, created_at: datetime, updated_at: datetime })
    Error_Response_Codes: 201 (Created), 400 (Bad Request - e.g., missing name, invalid parameters), 401 (Unauthorized), 409 (Conflict - if name already exists for user), 500.
    AI_Action_Focus: Backend: Requires authentication. Validate input. Store new saved search linked to `user_id`. Frontend: Send current F002 filter state and user-provided name.
    I18n_Considerations: API error messages should be internationalized or provide keys.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 2:** `GET /api/v1/me/saved-searches`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/saved-searches
    HTTP_Method: GET
    Brief_Description: Retrieves all saved searches for the authenticated user.
    Request_Query_Parameters_Schema_Ref: Optional pagination parameters.
    Success_Response_Schema_Ref: List[SavedSearch]
    Error_Response_Codes: 200 (OK), 401 (Unauthorized), 500.
    AI_Action_Focus: Backend: Requires authentication. Fetch all saved searches for `user_id`. Frontend: Display list to user.
    I18n_Considerations: None directly for this endpoint.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 3:** `GET /api/v1/me/saved-searches/{search_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/saved-searches/{search_id}
    HTTP_Method: GET
    Brief_Description: Retrieves a specific saved search by its ID for the authenticated user.
    Request_Path_Parameters_Schema_Ref: search_id: int
    Success_Response_Schema_Ref: SavedSearch
    Error_Response_Codes: 200 (OK), 401 (Unauthorized), 403 (Forbidden - if user does not own search), 404 (Not Found), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify `user_id` owns `search_id`. Fetch specific search. Frontend: Used when user selects a search to apply/view details.
    I18n_Considerations: API error messages should be internationalized or provide keys.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 4:** `PUT /api/v1/me/saved-searches/{search_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/saved-searches/{search_id}
    HTTP_Method: PUT
    Brief_Description: Updates an existing saved search (e.g., rename) for the authenticated user.
    Request_Path_Parameters_Schema_Ref: search_id: int
    Request_Body_Schema_Ref: SavedSearchUpdate (Pydantic model: { name: Optional[str], search_parameters: Optional[dict] } - Note: Updating search_parameters might be deferred post-MVP).
    Success_Response_Schema_Ref: SavedSearch
    Error_Response_Codes: 200 (OK), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 409 (Conflict - if new name already exists), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify ownership. Update specified fields. Frontend: Allow user to rename. (Updating criteria is complex, MVP might be rename only).
    I18n_Considerations: API error messages should be internationalized or provide keys.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 5:** `DELETE /api/v1/me/saved-searches/{search_id}`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/saved-searches/{search_id}
    HTTP_Method: DELETE
    Brief_Description: Deletes a specific saved search for the authenticated user.
    Request_Path_Parameters_Schema_Ref: search_id: int
    Success_Response_Schema_Ref: HTTP 204 No Content.
    Error_Response_Codes: 204 (No Content), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify ownership. Delete search. Frontend: Provide delete option with confirmation.
    I18n_Considerations: API error messages should be internationalized or provide keys.
    AI_HANGAR_BAY_API_ENDPOINT_END -->

## 7. Workflow / Logic Flow (Optional)
**Saving a Search:**
1.  User configures search/filters on F002 UI.
2.  User clicks "Save Search".
3.  UI prompts for a name.
4.  User enters name, confirms.
5.  Frontend sends `POST /api/v1/me/saved-searches` with name and current `search_parameters` (extracted from F002 UI state).
6.  Backend validates, stores in `saved_searches` table linked to `user_id` from session.
7.  Backend returns new saved search object.

**Applying a Saved Search:**
1.  User views their list of saved searches.
2.  User clicks on a saved search.
3.  Frontend fetches the specific saved search via `GET /api/v1/me/saved-searches/{search_id}` (or uses already loaded data).
4.  Frontend populates the F002 search/filter UI elements with `search_parameters`.
5.  Frontend triggers a new search in F002 using these parameters.

## 8. UI/UX Considerations (Optional)
*   "Save Search" button clearly visible on the F002 interface when filters are active or keywords entered.
*   Modal or inline form for naming the search.
*   Accessible list of saved searches (e.g., dropdown in nav, dedicated page in user profile).
*   Clear options to apply, rename, and delete each saved search in the list.
*   Confirmation before deleting a saved search.
*   [NEEDS_DESIGN: Mockups for saved search interactions.]
*   **AI Assistant Guidance:** When generating UI components, ensure all display strings (button labels like "Save Search", "Rename", "Delete"; prompts like "Enter a name for your search"; confirmation messages; list titles like "My Saved Searches") are prepared for localization using Angular's i18n mechanisms as detailed in `../i18n-spec.md`. Ensure forms for naming/renaming and lists of saved searches are accessible as per `../accessibility-spec.md`.

## 9. Error Handling & Edge Cases (Required)
*   Attempting to save a search without a name: Prompt user for a name.
*   Saving a search with a duplicate name for the same user: [NEEDS_DECISION: Allow or prevent? If prevent, inform user.]
*   API errors (not authenticated, server error): Display user-friendly messages.
*   User tries to access/delete a saved search not belonging to them: API should return 403 Forbidden or 404 Not Found.
*   No saved searches: Display an appropriate message in the list view.

## 10. Security Considerations (Required - Consult `../security-spec.md`)
*   All API endpoints must enforce authentication and authorization (user can only manage their own saved searches).
*   `search_parameters` (JSON) stored in the database must be handled carefully. While user-input, it defines query structures. Ensure that when these parameters are later used to query the main contract data, they are still subject to proper validation and sanitization in the F002 backend logic to prevent any form of injection if the parameters were maliciously crafted and somehow bypassed frontend controls during saving.
*   Input validation for `name` (e.g., length, character set) to prevent XSS if names are displayed unescaped (though modern frontend frameworks usually handle this).
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional, but Recommended - Consult `../performance-spec.md`)
*   Listing saved searches should be fast (querying `saved_searches` table by `user_id`).
*   The `search_parameters` JSON blob size should be monitored if it becomes excessively large, though typically it will be small.

## 12. Accessibility Considerations (Optional, but Recommended - Consult `../accessibility-spec.md`)
*   The "Save Search" button/form must be keyboard accessible.
*   Input fields for naming/renaming searches must have clear labels associated with them.
*   The list of saved searches must be navigable using a keyboard (e.g., if it's a list of links or buttons).
*   Actions per saved search (Apply, Rename, Delete) must be clearly labeled and keyboard accessible.
*   Confirmation dialogs (e.g., for delete) must be accessible, trapping focus appropriately.
*   Feedback messages (e.g., "Search saved", "Error saving search") should be announced to screen readers.
*   Refer to `../accessibility-spec.md` for general guidelines.
*   **AI Assistant Guidance:** "Ensure forms for saving/editing searches are built with semantic HTML and proper labels. List items for saved searches should be focusable and actionable via keyboard. Use ARIA attributes where necessary to convey state (e.g., `aria-live` for status messages)."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `../i18n-spec.md`)
*   **Translatable Content:**
    *   UI Labels: "Save Search", "Name", "Saved Searches", "Apply", "Rename", "Delete", "Confirm Deletion?", "Yes", "No", "Cancel".
    *   Prompts & Messages: "Enter a name for this search:", "Search saved successfully.", "Error: Search name already exists.", "Are you sure you want to delete this saved search?"
*   User-provided saved search names are data and should not be translated.
*   The `search_parameters` are internal filter identifiers and values, not typically translated.
*   Refer to `../i18n-spec.md` for specific Angular i18n patterns.
*   **AI Assistant Guidance:** "Ensure all static user-facing strings in Angular components for managing saved searches are externalized or marked for translation. This includes button texts, modal titles, labels, and confirmation messages."

## 14. Dependencies (Optional)
*   [F002 (Ship Browsing & Advanced Search/Filtering)](./F002-Ship-Browsing-Advanced-Search-Filtering.md): Provides the search criteria to be saved.
*   [F004 (User Authentication & SSO)](./F004-User-Authentication-SSO.md): Required for identifying the user to associate saved searches with. a user.
*   Backend API & Database.

## 15. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: For MVP, does "Update Saved Search" mean just rename, or also update the criteria? Updating criteria is more complex. Initial thought: MVP = rename & delete; to change criteria, delete and re-save.]
*   [NEEDS_DECISION: Allow duplicate names for saved searches for the same user? Probably best to enforce unique names per user.]
*   [NEEDS_DISCUSSION: Maximum number of saved searches per user? Initially, probably no limit, but consider for future scaling.]
*   [NEEDS_DISCUSSION: How to handle if a filter option used in a saved search becomes obsolete (e.g., a region is removed from EVE, or a ship type is removed)? The saved search might become un-runnable or return no results. Inform user? Silently ignore invalid parts of criteria?]

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 16.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   SQLAlchemy for DB interaction with `saved_searches` table.
    *   Pydantic for request/response models (`SavedSearchCreate`, `SavedSearchUpdate`, `SavedSearch`).
    *   FastAPI `Depends` for authentication and user identification.
*   Frontend (Angular):
    *   `HttpClientModule` for API calls.
    *   `FormsModule` or `ReactiveFormsModule` for the 'name search' input.
    *   Services to encapsulate saved search logic and API interactions.
    *   Components to display the list of saved searches and the 'save search' UI.

### 16.2. Critical Logic Points for AI Focus
*   **Backend:**
    *   CRUD operations for `saved_searches`, strictly enforcing that operations are tied to the authenticated `user_id`.
    *   Validation of `name` (e.g., non-empty, potentially unique per user - see Notes).
    *   Storing `search_parameters` as a JSON blob correctly.
*   **Frontend:**
    *   Capturing the current filter state from F002's search/filter components to form the `search_parameters` object.
    *   Displaying the list of saved searches and handling user interactions (apply, rename, delete).
    *   When 'applying' a saved search: fetching its `search_parameters` and re-populating/triggering the F002 search UI and logic.
    *   Handling UI for naming a new search and renaming an existing one.

### 16.3. Data Validation and Sanitization
*   Backend: Validate `name` of saved search (length, required). Enforce uniqueness per user if decided.
*   Backend: `search_parameters` are trusted as they originate from the F002 UI state, but the F002 feature itself must ensure its parameters are safe when constructing actual database queries for contracts.
*   Frontend: Basic validation for the 'name' input field.

### 16.4. Test Cases for AI to Consider Generating
*   **Backend (FastAPI - Integration Tests):**
    *   Test `POST /api/v1/me/saved-searches`: create a search, verify DB record and response.
    *   Test `GET /api/v1/me/saved-searches`: retrieve list, verify content.
    *   Test `GET /api/v1/me/saved-searches/{search_id}`: retrieve specific, test ownership (user A cannot get user B's search).
    *   Test `PUT /api/v1/me/saved-searches/{search_id}`: rename search, test ownership.
    *   Test `DELETE /api/v1/me/saved-searches/{search_id}`: delete search, test ownership.
    *   Test all endpoints for unauthenticated access (expect 401).
    *   Test creating a search with a duplicate name for the same user (expect 409 if uniqueness is enforced).
*   **Frontend (Angular - Component/Service Tests):**
    *   Test 'Save Search' button captures current filters and prompts for name.
    *   Test saving a search calls the correct service method and updates UI (e.g., adds to list).
    *   Test displaying the list of saved searches.
    *   Test clicking a saved search applies its parameters to the F002 filter state and triggers a search.
    *   Test renaming a saved search.
    *   Test deleting a saved search with confirmation.

### 16.5. Specific AI Prompts or Instructions
*   **Backend (FastAPI):**
    *   "Create SQLAlchemy model `SavedSearch` and Pydantic schemas `SavedSearchCreate`, `SavedSearchUpdate`, `SavedSearchDisplay` for saved searches. Include `user_id` (FK to User), `name`, and `search_parameters` (JSONB). Enforce unique constraint on `(user_id, name)`."
    *   "Implement FastAPI CRUD endpoints for `/api/v1/me/saved-searches`. All endpoints require authentication and must ensure operations are performed only on the authenticated user's own saved searches."
*   **Frontend (Angular):**
    *   "Create an Angular `SavedSearchService` with methods to: `createSavedSearch(name: string, params: any)`, `getSavedSearches()`, `getSavedSearchById(id: number)`, `updateSavedSearch(id: number, name: string)`, `deleteSavedSearch(id: number)`."
    *   "Create an Angular component to display a list of saved searches. Each item should allow applying, renaming, and deleting the search."
    *   "Integrate a 'Save Search' button into the F002 feature's UI. On click, it should capture current filter parameters from F002's state, prompt for a name, and call `SavedSearchService.createSavedSearch()`."
    *   "When a saved search is 'applied', populate the filter controls of F002 with its `search_parameters` and trigger a new search."
    *   "Ensure all user-facing text (buttons, prompts, etc.) is internationalized."
