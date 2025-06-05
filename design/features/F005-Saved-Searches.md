# Feature Spec: Saved Searches

**Feature ID:** F005
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

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
*   **`saved_searches` table:**
    *   `id`: INTEGER (Primary Key, Auto-increment)
    *   `user_id`: INTEGER (Foreign Key to `users` table from F004, Indexed)
    *   `name`: VARCHAR (User-defined name for the search)
    *   `search_parameters`: JSONB (Stores the actual search criteria, e.g., `{"keyword": "caracal", "region_id": 10000002, "max_price": 50000000}`)
    *   `created_at`: TIMESTAMP
    *   `updated_at`: TIMESTAMP

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A for this feature directly.
### 6.2. Exposed Hangar Bay API Endpoints
*   `POST /api/v1/me/saved-searches`
    *   Request: JSON body with `name` (string) and `search_parameters` (JSON object).
    *   Requires Authentication.
    *   Success Response: 201 Created, with the new saved search object.
*   `GET /api/v1/me/saved-searches`
    *   Request: No body.
    *   Requires Authentication.
    *   Success Response: 200 OK, with a JSON array of the user's saved searches (`id`, `name`, `search_parameters`).
*   `GET /api/v1/me/saved-searches/{search_id}`
    *   Request: Path parameter `search_id`.
    *   Requires Authentication (and user must own the search).
    *   Success Response: 200 OK, with the specific saved search object.
*   `PUT /api/v1/me/saved-searches/{search_id}`
    *   Request: JSON body with `name` (for renaming) and/or `search_parameters` (if updating criteria is in scope).
    *   Requires Authentication (and user must own the search).
    *   Success Response: 200 OK, with the updated saved search object.
*   `DELETE /api/v1/me/saved-searches/{search_id}`
    *   Request: Path parameter `search_id`.
    *   Requires Authentication (and user must own the search).
    *   Success Response: 204 No Content.

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

## 9. Error Handling & Edge Cases (Required)
*   Attempting to save a search without a name: Prompt user for a name.
*   Saving a search with a duplicate name for the same user: [NEEDS_DECISION: Allow or prevent? If prevent, inform user.]
*   API errors (not authenticated, server error): Display user-friendly messages.
*   User tries to access/delete a saved search not belonging to them: API should return 403 Forbidden or 404 Not Found.
*   No saved searches: Display an appropriate message in the list view.

## 10. Security Considerations (Required)
*   All API endpoints must enforce authentication and authorization (user can only manage their own saved searches).
*   `search_parameters` (JSON) stored in the database must be handled carefully. While user-input, it defines query structures. Ensure that when these parameters are later used to query the main contract data, they are still subject to proper validation and sanitization in the F002 backend logic to prevent any form of injection if the parameters were maliciously crafted and somehow bypassed frontend controls during saving.
*   Input validation for `name` (e.g., length, character set) to prevent XSS if names are displayed unescaped (though modern frontend frameworks usually handle this).
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional)
*   Listing saved searches should be fast (querying `saved_searches` table by `user_id`).
*   The `search_parameters` JSON blob size should be monitored if it becomes excessively large, though typically it will be small.

## 12. Dependencies (Optional)
*   F002 (Ship Browsing & Advanced Search/Filtering): Provides the search criteria to be saved.
*   F004 (User Authentication - EVE SSO): Required for identifying and associating saved searches with a user.
*   Backend API & Database.

## 13. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: For MVP, does "Update Saved Search" mean just rename, or also update the criteria? Updating criteria is more complex. Initial thought: MVP = rename & delete; to change criteria, delete and re-save.]
*   [NEEDS_DECISION: Allow duplicate names for saved searches for the same user? Probably best to enforce unique names per user.]
*   [NEEDS_DISCUSSION: Maximum number of saved searches per user? Initially, probably no limit, but consider for future scaling.]
*   [NEEDS_DISCUSSION: How to handle if a filter option used in a saved search becomes obsolete (e.g., a region is removed from EVE, or a ship type is removed)? The saved search might become un-runnable or return no results. Inform user? Silently ignore invalid parts of criteria?]
