# Feature Spec: Watchlists

**Feature ID:** F006
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

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
    *   Criterion 3.3: [NEEDS_DISCUSSION: Should this view also show current market availability or lowest price for watched items? This adds complexity and dependency on F001/F002 data feeds directly into this view.]
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
*   **`watchlist_items` table:**
    *   `id`: INTEGER (Primary Key, Auto-increment)
    *   `user_id`: INTEGER (Foreign Key to `users` table from F004, Indexed)
    *   `type_id`: INTEGER (EVE Online Type ID of the ship, Indexed)
    *   `max_price`: DECIMAL (Optional, user-defined maximum price)
    *   `notes`: TEXT (Optional, user-defined notes for the item) [NEEDS_DISCUSSION: Add notes field?]
    *   `created_at`: TIMESTAMP
    *   `updated_at`: TIMESTAMP

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. May need `GET /v3/universe/types/{type_id}/` if displaying ship names/details not already cached or provided by frontend context when adding.
### 6.2. Exposed Hangar Bay API Endpoints
*   `POST /api/v1/me/watchlist-items`
    *   Request: JSON body with `type_id` (integer), optional `max_price` (decimal), optional `notes` (string).
    *   Requires Authentication.
    *   Success Response: 201 Created, with the new watchlist item object.
*   `GET /api/v1/me/watchlist-items`
    *   Request: No body.
    *   Requires Authentication.
    *   Success Response: 200 OK, with a JSON array of the user's watchlist items (including resolved type names from `esi_type_cache`).
*   `GET /api/v1/me/watchlist-items/{item_id}`
    *   Request: Path parameter `item_id`.
    *   Requires Authentication (user must own the item).
    *   Success Response: 200 OK, with the specific watchlist item.
*   `PUT /api/v1/me/watchlist-items/{item_id}`
    *   Request: JSON body with optional `max_price` (decimal), optional `notes` (string).
    *   Requires Authentication (user must own the item).
    *   Success Response: 200 OK, with the updated watchlist item.
*   `DELETE /api/v1/me/watchlist-items/{item_id}`
    *   Request: Path parameter `item_id`.
    *   Requires Authentication (user must own the item).
    *   Success Response: 204 No Content.

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
*   [NEEDS_DESIGN: Mockups for watchlist page and add-to-watchlist interactions.]

## 9. Error Handling & Edge Cases (Required)
*   Attempting to add a non-ship item or invalid `type_id`: API should validate `type_id` against known ship types (e.g., check categoryID from `esi_type_cache`).
*   User tries to add the same `type_id` multiple times: [NEEDS_DECISION: Allow (e.g., if different notes/prices are desired, though price is editable) or prevent duplicates by `type_id` per user? Generally, prevent direct duplicates of type_id.]
*   API errors: Standard user-friendly messages.
*   User tries to manage a watchlist item not belonging to them: API returns 403/404.

## 10. Security Considerations (Required)
*   All API endpoints must enforce authentication and authorization.
*   Input validation for `type_id`, `max_price`, `notes`.
*   Ensure `user_id` is always taken from the authenticated session, not from user input.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional)
*   Fetching watchlist for a user should be fast (indexed query on `user_id` and `type_id`).
*   If the watchlist view shows current market data for each item, this could be performance-intensive and needs careful design (likely deferred to F007 logic).

## 12. Dependencies (Optional)
*   F001 (Public Contract Aggregation & Display): For `esi_type_cache` to resolve ship names/details.
*   F004 (User Authentication - EVE SSO): Required for all operations.
*   Backend API & Database.

## 13. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: Allow duplicate `type_id` entries per user on watchlist? Recommendation: No, make `(user_id, type_id)` unique.]
*   [NEEDS_DISCUSSION: Add a 'notes' field per watchlist item? Could be useful for users.]
*   [NEEDS_DISCUSSION: Should the main watchlist view attempt to show if contracts meeting the price criteria are currently available? This blurs lines with F007 (Alerts) and adds significant complexity to this feature's direct view. Recommendation: Keep F006 focused on managing the list of desired items/prices; F007 handles checking against market.]
*   [NEEDS_DECISION: How does a user find `type_id`s to add? Search by name within an 'add to watchlist' modal? From F002/F003 views?]
