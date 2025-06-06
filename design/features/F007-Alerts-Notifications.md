# Feature Spec: Alerts/Notifications

**Feature ID:** F007
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
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** Notification messages need careful i18n design. Consider storing message template keys and parameters rather than fully rendered messages if complex localization is needed. Consult `../i18n-spec.md`.

*   **`notifications` table:**
    <!-- AI_HANGAR_BAY_DATA_MODEL_START
    Model_Name: Notification
    Brief_Description: Stores individual notification records for users.
    Fields:
      - id: INTEGER (Primary Key, Auto-increment)
      - user_id: INTEGER (Foreign Key to `users.id`, Indexed, Not Nullable)
      - type: VARCHAR(50) (Enum-like: 'watchlist_match', 'saved_search_new_result', 'system_message', Not Nullable)
      - message_key: VARCHAR(255) (Optional, key for a localized message template)
      - message_params: JSONB (Optional, parameters for the message template, e.g., {ship_name: 'Caracal', price: '1000000 ISK'})
      - rendered_message: TEXT (The actual notification text, potentially pre-rendered using message_key and params in the backend, or a simple direct message)
      - related_item_id: BIGINT (Optional, e.g., `contract_id` for watchlist match, `saved_search_id` for search alert)
      - related_item_type: VARCHAR(50) (Optional, e.g., 'contract', 'saved_search', 'ship_type')
      - related_item_url: VARCHAR(2048) (Optional, direct URL to the related item in the frontend)
      - is_read: BOOLEAN (Default: false, Indexed)
      - created_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP)
    AI_Action_Focus: Backend (SQLAlchemy model, Pydantic schema). Logic for constructing/rendering messages. Ensure `user_id` linkage. `related_item_url` helps frontend navigation.
    I18n_Considerations: `message_key` and `message_params` are for i18n. `rendered_message` should be generated in the user's preferred language.
    AI_HANGAR_BAY_DATA_MODEL_END -->

*   **`user_notification_settings` table (or extend `users` table):**
    <!-- AI_HANGAR_BAY_DATA_MODEL_START
    Model_Name: UserNotificationSetting
    Brief_Description: Stores notification preferences for each user.
    Fields:
      - user_id: INTEGER (Primary Key, Foreign Key to `users.id`, Not Nullable)
      - enable_watchlist_alerts: BOOLEAN (Default: true)
      - enable_saved_search_alerts: BOOLEAN (Default: false) [NEEDS_DISCUSSION: Scope of saved search alerts for MVP.]
      - enable_email_notifications: BOOLEAN (Default: false) [Future: If email in scope]
      - email_address: VARCHAR(255) (Optional) [Future: If email in scope]
      - email_address_verified: BOOLEAN (Default: false) [Future: If email in scope]
      - updated_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP, On Update: CURRENT_TIMESTAMP)
    AI_Action_Focus: Backend (SQLAlchemy model, Pydantic schema). API for users to update their settings.
    I18n_Considerations: UI for these settings needs localization.
    AI_HANGAR_BAY_DATA_MODEL_END -->

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   N/A directly. Relies on data from F001 (contracts) and user data from F005 (saved searches), F006 (watchlists).
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `GET /api/v1/me/notifications`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/notifications
    HTTP_Method: GET
    Brief_Description: Retrieves notifications for the authenticated user, supporting pagination and filtering.
    Request_Query_Parameters_Schema_Ref: { page: Optional[int]=1, limit: Optional[int]=10, is_read: Optional[bool] }
    Success_Response_Schema_Ref: PaginatedResponse[NotificationDisplay] (NotificationDisplay includes id, type, rendered_message, related_item_url, is_read, created_at)
    Error_Response_Codes: 200 (OK), 401 (Unauthorized), 500.
    AI_Action_Focus: Backend: Requires authentication. Fetch notifications for `user_id`. Frontend: Display in notification panel.
    I18n_Considerations: `rendered_message` should be localized.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 2:** `POST /api/v1/me/notifications/{notification_id}/mark-read`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/notifications/{notification_id}/mark-read
    HTTP_Method: POST
    Brief_Description: Marks a specific notification as read for the authenticated user.
    Request_Path_Parameters_Schema_Ref: notification_id: int
    Success_Response_Schema_Ref: HTTP 204 No Content or NotificationDisplay (updated notification).
    Error_Response_Codes: 200/204 (OK), 401 (Unauthorized), 403 (Forbidden - if user does not own notification), 404 (Not Found), 500.
    AI_Action_Focus: Backend: Requires authentication. Verify ownership. Update `is_read` flag. Frontend: Call when user interacts with/views a notification.
    I18n_Considerations: Error messages.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 3:** `POST /api/v1/me/notifications/mark-all-read`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/notifications/mark-all-read
    HTTP_Method: POST
    Brief_Description: Marks all unread notifications as read for the authenticated user.
    Success_Response_Schema_Ref: HTTP 204 No Content.
    Error_Response_Codes: 204 (OK), 401 (Unauthorized), 500.
    AI_Action_Focus: Backend: Requires authentication. Update `is_read` for all user's unread notifications. Frontend: Provide a 'Mark all as read' button.
    I18n_Considerations: None directly.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 4:** `GET /api/v1/me/notification-settings`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/notification-settings
    HTTP_Method: GET
    Brief_Description: Retrieves the current notification settings for the authenticated user.
    Success_Response_Schema_Ref: UserNotificationSettingDisplay (Pydantic model reflecting UserNotificationSetting table, excluding sensitive fields like email if not verified for this context)
    Error_Response_Codes: 200 (OK), 401 (Unauthorized), 500.
    AI_Action_Focus: Backend: Requires authentication. Fetch settings for `user_id`. Frontend: Populate settings page.
    I18n_Considerations: None directly for API, but UI displaying these settings needs i18n.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 5:** `PUT /api/v1/me/notification-settings`
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me/notification-settings
    HTTP_Method: PUT
    Brief_Description: Updates notification settings for the authenticated user.
    Request_Body_Schema_Ref: UserNotificationSettingUpdate (Pydantic model: { enable_watchlist_alerts: Optional[bool], enable_saved_search_alerts: Optional[bool] } - email fields deferred for MVP)
    Success_Response_Schema_Ref: UserNotificationSettingDisplay
    Error_Response_Codes: 200 (OK), 400 (Bad Request), 401 (Unauthorized), 500.
    AI_Action_Focus: Backend: Requires authentication. Validate input. Update settings for `user_id`. Frontend: Allow user to toggle preferences.
    I18n_Considerations: Error messages.
    AI_HANGAR_BAY_API_ENDPOINT_END -->

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
*   **AI Assistant Guidance:** When generating UI components for notifications (indicator, panel, list items) and settings, ensure all display strings are prepared for localization (see `../i18n-spec.md`). All interactive elements must be accessible (see `../accessibility-spec.md`), including ARIA attributes for dynamic updates like unread counts or new notification arrivals.

## 9. Error Handling & Edge Cases (Required)
*   Notification generation task failure: Log errors, ensure task retries or resumes.
*   Large number of watchlists/contracts: Ensure matching process is efficient.
*   Delay in F001 data: Notifications will be based on latest available aggregated data.
*   Email service failure (if email in scope): Log errors, retry sending emails.
*   API errors for notification management: Standard user-friendly messages.

## 10. Security Considerations (Required - Consult `../security-spec.md`)
*   All API endpoints must enforce authentication.
*   User can only access/manage their own notifications and settings.
*   If email notifications are implemented, protect against email address spoofing or SSRF if email content can be influenced by external data. Use a reputable email sending service.
*   Validate all inputs for notification settings.
*   Refer to `security-spec.md`.

## 11. Performance Considerations (Optional, but Recommended - Consult `../performance-spec.md`)
*   The backend task for matching watchlists to contracts needs to be highly optimized, especially if many users have many watchlist items. Efficient database queries and indexing are crucial.
*   Polling for in-app notifications should be lightweight. Consider WebSockets for a more scalable real-time solution if polling becomes too frequent or heavy.
*   Frequency of checks vs. data freshness vs. server load needs balancing.

## 12. Accessibility Considerations (Optional, but Recommended - Consult `../accessibility-spec.md`)
*   Notification Indicator (e.g., bell icon): Must be keyboard focusable if interactive. Unread count should be announced by screen readers. Consider `aria-live` regions for announcing new notifications non-intrusively.
*   Notification Panel/List: Must be keyboard navigable. Each notification item should be focusable. Actions (mark read, view item) must be accessible.
*   Notification Messages: Ensure they are clear and understandable. If they contain links, links should be descriptive.
*   Settings Page: Standard form accessibility applies (labels, fieldsets, keyboard navigation).
*   Refer to `../accessibility-spec.md` for general guidelines.
*   **AI Assistant Guidance:** "Implement the in-app notification display using ARIA roles like `alert` or `status` for announcements, or a more structured list for a notification panel. Ensure keyboard navigation and that interactive elements within notifications are operable. Settings page should use semantic HTML for forms."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `../i18n-spec.md`)
*   **Translatable Content:**
    *   UI Labels: "Notifications", "Mark all as read", "Settings", "Enable Watchlist Alerts", "Enable Saved Search Alerts", specific notification type descriptions (e.g., "New item matching your watchlist criteria").
    *   Notification Messages: These are dynamic. Use a system of message template keys and localized parameters (e.g., `notifications.watchlist_match_message_key = "A {ship_name} is available for {price}!"`). Parameters like ship names come from ESI (localized there if possible) or are user data.
    *   Dates/Times in notifications should be localized.
*   Refer to `../i18n-spec.md` for specific Angular i18n patterns and backend message generation strategies.
*   **AI Assistant Guidance:** "For backend, design notification generation to use i18n keys and parameters. Store the key and params in the `notifications` table, and render the message in the user's locale when retrieved via API or just before sending (if push/email were in scope). For frontend, ensure all static UI text in notification components and settings is externalized. Use Angular's date pipe for localized dates."

## 14. Dependencies (Optional)
*   F001 (Public Contract Aggregation & Display): Provides contract data to match against.
*   F004 (User Authentication - EVE SSO): Required for all user-specific operations.
*   F005 (Saved Searches): If saved search alerts are implemented.
*   F006 (Watchlists): Provides the items to be monitored.
*   Backend database, Task scheduler (Celery).
*   (Optional) Email sending service.

## 15. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: MVP scope for notification channels - In-app only, or include email? Email adds significant setup.]
*   [NEEDS_DECISION: Frequency of backend checks for watchlist matches and saved search updates.]
*   [NEEDS_DISCUSSION: Detailed de-duplication logic for notifications. E.g., don't notify for the same contract_id for the same user/watchlist_item within X hours? Or only if price changes?]
*   [NEEDS_DISCUSSION: Scope of saved search alerts for MVP. Is it just "new items found" or more complex criteria?]
*   [NEEDS_DISCUSSION: How to handle notifications for auctions where price changes? Notify on initial match, then again if price drops further below user's max_price?]
*   [NEEDS_DESIGN: What information exactly to show in a notification message?]

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 16.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   SQLAlchemy for DB interaction with `notifications` and `user_notification_settings` tables.
    *   Pydantic for request/response models.
    *   Celery (or similar, e.g., `arq`, `FastAPI BackgroundTasks` for simpler cases) for scheduled tasks (checking watchlists/searches).
    *   Mechanism for i18n key-based message templating.
*   Frontend (Angular):
    *   `HttpClientModule` for API calls.
    *   Services for managing notifications and settings.
    *   Components for notification display (bell icon, panel/list) and settings page.
    *   Polling mechanism for new notifications (or WebSockets if chosen later for real-time).
    *   Angular's i18n tools for UI text and date/number formatting.

### 16.2. Critical Logic Points for AI Focus
*   **Backend (Scheduled Tasks - Celery):**
    *   Task to iterate through active watchlists (F006), query current contracts (F001 data), and identify matches based on `type_id` and `max_price`.
    *   Task (if F005 alerts in scope) to iterate through opted-in saved searches, execute them, and identify new results.
    *   Efficient querying and matching logic.
    *   Notification de-duplication logic (e.g., don't re-notify for the exact same contract match within a short timeframe unless state changes significantly).
    *   Generation of `Notification` records with appropriate `message_key`, `message_params`, `rendered_message` (localized), and `related_item_url`.
*   **Backend (API):**
    *   Endpoints for retrieving notifications (paginated, filterable by `is_read`).
    *   Endpoints for marking notifications as read (single, all).
    *   Endpoints for managing user notification settings.
    *   Strict user ownership enforcement for all data.
*   **Frontend:**
    *   Service to poll for new unread notifications and manage notification state.
    *   UI component for a notification indicator (e.g., bell icon with unread count).
    *   UI component for a notification panel/list, allowing interaction (mark read, navigate to item).
    *   UI for notification settings page.

### 16.3. Data Validation and Sanitization
*   Backend: Validate user input for notification settings (boolean flags).
*   Backend: Ensure `related_item_id` and `related_item_type` are handled safely when constructing `related_item_url` to prevent open redirect vulnerabilities if any part of the URL comes from less trusted sources (though typically these are internally generated).

### 16.4. Test Cases for AI to Consider Generating
*   **Backend (Celery Tasks - Unit/Integration Tests):**
    *   Test watchlist matching task: correct notification generated when a contract meets criteria; no notification if not.
    *   Test saved search alert task (if in scope): new results trigger notification.
    *   Test notification de-duplication logic.
    *   Test localization of generated `rendered_message`.
*   **Backend (FastAPI API - Integration Tests):**
    *   Test `GET /api/v1/me/notifications` with pagination and filters.
    *   Test marking notifications as read (single, all).
    *   Test getting and updating notification settings.
    *   Test all endpoints for user ownership and authentication.
*   **Frontend (Angular - Component/Service Tests):**
    *   Test notification service polling and unread count updates.
    *   Test display of notifications in panel/list.
    *   Test interaction with notifications (mark read, navigation).
    *   Test notification settings page functionality.

### 16.5. Specific AI Prompts or Instructions
*   **Backend (Models & Tasks):**
    *   "Create SQLAlchemy models `Notification` and `UserNotificationSetting` and corresponding Pydantic schemas as detailed in Section 5."
    *   "Develop a Celery task that periodically checks active user watchlists against current contract data. If a contract matches a watchlist item's `type_id` and is at or below its `max_price`, generate a `Notification` record. Implement de-duplication to avoid repeat notifications for the same event within a defined period. Ensure notification messages are constructed using i18n keys and parameters."
    *   (If F005 alerts in scope) "Develop a Celery task for saved search alerts..."
*   **Backend (API):**
    *   "Implement FastAPI endpoints for `/api/v1/me/notifications` (GET, POST for mark-read) and `/api/v1/me/notification-settings` (GET, PUT) as detailed in Section 6.2. Ensure all require authentication and enforce user ownership."
*   **Frontend (Angular):**
    *   "Create an Angular `NotificationService` that polls `GET /api/v1/me/notifications` for unread notifications, manages a list of notifications, and provides methods to mark notifications as read."
    *   "Create an Angular `NotificationIconComponent` that displays an icon (e.g., bell) and an unread notification count from `NotificationService`."
    *   "Create an Angular `NotificationPanelComponent` that displays a list of notifications, allowing users to click them (to navigate to `related_item_url`) and mark them as read."
    *   "Create an Angular `NotificationSettingsComponent` to manage user preferences by calling the settings API endpoints."
    *   "Ensure all UI text is internationalized and dates/times are localized."
