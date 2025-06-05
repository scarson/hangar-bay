# Feature Spec: Alerts/Notifications

**Feature ID:** F007
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

---
**Instructions for Use:**
*   (Standard template instructions)
---

## 1. Feature Overview (Required)
*   This feature enables authenticated users (F004) to receive notifications when items on their watchlist (F006) meet specified criteria (e.g., a ship contract is available at or below their set maximum price). It can also potentially notify users about new results for their saved searches (F005).

## 2. User Stories (Required)
*   Story 1: As a logged-in user with items on my watchlist (F006), I want to be notified when a public contract becomes available for a watched ship type at or below my specified maximum price, so I don't miss good deals.
*   Story 2: As a logged-in user with saved searches (F005), I want to be optionally notified when new contracts matching a saved search appear, so I can stay updated on specific market segments.
*   Story 3: As a logged-in user, I want to be able to configure how I receive notifications (e.g., in-app, email [NEEDS_DISCUSSION: Email for MVP?]), so I can choose my preferred method.
*   Story 4: As a logged-in user, I want to view a list of my recent notifications within the application, so I can catch up on alerts I might have missed.

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: A backend process periodically checks active watchlists against current public ship contracts (from F001 data).
    *   Criterion 1.2: If a contract for a watched `type_id` is found at or below the user's `max_price` (if set), a notification is generated for the user.
    *   Criterion 1.3: Notifications are not repeatedly generated for the exact same contract unless a certain cooldown period has passed or the contract details changed significantly. [NEEDS_DISCUSSION: Notification de-duplication logic.]
*   **Story 2 Criteria (If in scope for MVP):**
    *   Criterion 2.1: A backend process periodically executes saved searches for users who have opted-in for notifications on those searches.
    *   Criterion 2.2: If new contracts (not seen before by this saved search alert) are found, a notification is generated.
    *   Criterion 2.3: Users can toggle notifications on/off per saved search.
*   **Story 3 Criteria:**
    *   Criterion 3.1: User has settings to enable/disable watchlist notifications.
    *   Criterion 3.2: User has settings to enable/disable saved search notifications (if F005 integration is in scope).
    *   Criterion 3.3: [If email is in scope] User can enable/disable email notifications and confirm their email address.
    *   Criterion 3.4: In-app notifications are displayed in a dedicated UI element (e.g., a notification bell/panel).
*   **Story 4 Criteria:**
    *   Criterion 4.1: An in-app notification center lists recent alerts for the user.
    *   Criterion 4.2: Users can mark notifications as read or dismiss them.
    *   Criterion 4.3: Notifications link to the relevant contract (F003) or search results (F002).

## 4. Scope (Required)
### 4.1. In Scope
*   Backend logic to match watchlist items against current contract data.
*   Backend logic to (optionally) execute saved searches and identify new results.
*   Generation of notification records.
*   In-app notification display system (e.g., a bell icon with a dropdown list).
*   User settings to manage notification preferences (at least on/off for types of alerts).
*   Storing and retrieving user notifications.
### 4.2. Out of Scope
*   Email notifications (Potential for V2, adds complexity of email service integration, templates, unsubscribe management). [NEEDS_DECISION: Confirm for MVP]
*   Push notifications to mobile/desktop (V_Future).
*   Highly customizable notification conditions beyond watchlist price and new saved search results.
*   Real-time, instant notifications (notifications are generated based on periodic checks).

## 5. Key Data Structures / Models (Optional, but often Required)
*   **`notifications` table:**
    *   `id`: INTEGER (Primary Key, Auto-increment)
    *   `user_id`: INTEGER (Foreign Key to `users` table, Indexed)
    *   `type`: VARCHAR (e.g., 'watchlist_match', 'saved_search_new_result')
    *   `message`: TEXT (The notification text)
    *   `related_item_id`: BIGINT (Optional, e.g., `contract_id` for watchlist match, `saved_search_id` for search alert)
    *   `related_item_type`: VARCHAR (Optional, e.g., 'contract', 'saved_search')
    *   `is_read`: BOOLEAN (Default: false)
    *   `created_at`: TIMESTAMP
*   **`user_notification_settings` table (or extend `users` table):**
    *   `user_id`: INTEGER (Primary Key, Foreign Key to `users` table)
    *   `enable_watchlist_alerts`: BOOLEAN (Default: true)
    *   `enable_saved_search_alerts`: BOOLEAN (Default: false)
    *   `enable_email_notifications`: BOOLEAN (Default: false) [If email in scope]
    *   `email_address_verified`: BOOLEAN (Default: false) [If email in scope]

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. Relies on data from F001 (contracts) and user data from F005 (saved searches), F006 (watchlists).
### 6.2. Exposed Hangar Bay API Endpoints
*   `GET /api/v1/me/notifications`
    *   Request: Query params for pagination (`page`, `limit`), filter by `is_read` (optional).
    *   Requires Authentication.
    *   Success Response: 200 OK, with a paginated JSON array of user's notifications.
*   `POST /api/v1/me/notifications/{notification_id}/mark-read`
    *   Request: Path parameter `notification_id`.
    *   Requires Authentication.
    *   Success Response: 200 OK or 204 No Content.
*   `POST /api/v1/me/notifications/mark-all-read`
    *   Request: No body.
    *   Requires Authentication.
    *   Success Response: 200 OK or 204 No Content.
*   `GET /api/v1/me/notification-settings`
    *   Request: No body.
    *   Requires Authentication.
    *   Success Response: 200 OK, with user's current notification settings.
*   `PUT /api/v1/me/notification-settings`
    *   Request: JSON body with settings fields to update.
    *   Requires Authentication.
    *   Success Response: 200 OK, with updated settings.

## 7. Workflow / Logic Flow (Optional)
**Watchlist Alert Generation (Backend Scheduled Task):**
1.  Periodically (e.g., every 5-15 minutes [NEEDS_DECISION: Frequency]):
    a.  Fetch all active watchlist items from `watchlist_items` for users with `enable_watchlist_alerts=true`.
    b.  For each watchlist item:
        i.  Query current ship contracts (F001 data) matching `type_id`.
        ii. If `max_price` is set on watchlist, filter contracts further by `price <= max_price`.
        iii. For each matching contract found:
            1.  Check if a notification for this user + contract + watchlist item already exists recently (de-duplication logic).
            2.  If no recent notification, create a new record in `notifications` table.
            3.  [If email in scope and user opted-in: queue email notification.]

**In-App Notification Display:**
1.  Frontend periodically polls `GET /api/v1/me/notifications?is_read=false&limit=1` (or uses WebSockets if implemented later) to check for new unread notifications.
2.  If new unread notifications exist, update UI (e.g., badge on bell icon).
3.  User clicks bell icon: Frontend fetches list from `GET /api/v1/me/notifications` and displays them.
4.  User clicks a notification: Navigate to relevant item (contract/search). Mark as read via API.

## 8. UI/UX Considerations (Optional)
*   Non-intrusive in-app notification indicator (e.g., bell icon with a badge for unread count).
*   Notification panel/dropdown listing recent notifications (ship name, price found, time).
*   Clear call to action in notifications (e.g., "View Contract").
*   User settings page for managing notification preferences.
*   [NEEDS_DESIGN: Mockups for notification display and settings.]

## 9. Error Handling & Edge Cases (Required)
*   Notification generation task failure: Log errors, ensure task retries or resumes.
*   Large number of watchlists/contracts: Ensure matching process is efficient.
*   Delay in F001 data: Notifications will be based on latest available aggregated data.
*   Email service failure (if email in scope): Log errors, retry sending emails.
*   API errors for notification management: Standard user-friendly messages.

## 10. Security Considerations (Required)
*   All API endpoints must enforce authentication.
*   User can only access/manage their own notifications and settings.
*   If email notifications are implemented, protect against email address spoofing or SSRF if email content can be influenced by external data. Use a reputable email sending service.
*   Validate all inputs for notification settings.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional)
*   The backend task for matching watchlists to contracts needs to be highly optimized, especially if many users have many watchlist items. Efficient database queries and indexing are crucial.
*   Polling for in-app notifications should be lightweight. Consider WebSockets for a more scalable real-time solution if polling becomes too frequent or heavy.
*   Frequency of checks vs. data freshness vs. server load needs balancing.

## 12. Dependencies (Optional)
*   F001 (Public Contract Aggregation & Display): Provides contract data to match against.
*   F004 (User Authentication - EVE SSO): Required for all user-specific operations.
*   F005 (Saved Searches): If saved search alerts are implemented.
*   F006 (Watchlists): Provides the items to be monitored.
*   Backend database, Task scheduler (Celery).
*   (Optional) Email sending service.

## 13. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: MVP scope for notification channels - In-app only, or include email? Email adds significant setup.]
*   [NEEDS_DECISION: Frequency of backend checks for watchlist matches and saved search updates.]
*   [NEEDS_DISCUSSION: Detailed de-duplication logic for notifications. E.g., don't notify for the same contract_id for the same user/watchlist_item within X hours? Or only if price changes?]
*   [NEEDS_DISCUSSION: Scope of saved search alerts for MVP. Is it just "new items found" or more complex criteria?]
*   [NEEDS_DISCUSSION: How to handle notifications for auctions where price changes? Notify on initial match, then again if price drops further below user's max_price?]
*   [NEEDS_DESIGN: What information exactly to show in a notification message?]
