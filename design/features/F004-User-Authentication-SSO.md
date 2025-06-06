# Feature Spec: User Authentication (EVE SSO)

**Feature ID:** F004
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
*   This feature implements user authentication for Hangar Bay using EVE Online's Single Sign-On (SSO) OAuth 2.0 flow. This will allow users to log in with their EVE characters, enabling personalized features like saved searches and watchlists.

## 2. User Stories (Required)
*   Story 1: As an unregistered user, I want to be able to log in to Hangar Bay using my EVE Online account, so I can access personalized features.
*   Story 2: As a logged-in user, I want my session to be securely maintained, so I don't have to log in repeatedly.
*   Story 3: As a logged-in user, I want to be able to log out of Hangar Bay, so I can end my session securely.
*   Story 4: As a Hangar Bay system, I want to securely manage EVE SSO tokens (access, refresh) for authenticated users, so I can make ESI calls on their behalf if needed for future features and maintain their session.

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: A "Login with EVE Online" button is present and visible.
    *   Criterion 1.2: Clicking the button redirects the user to the EVE Online SSO authorization page.
    *   Criterion 1.3: After successful EVE SSO authorization, the user is redirected back to Hangar Bay.
    *   Criterion 1.4: The system retrieves an authorization code, exchanges it for an access token and refresh token from EVE SSO.
    *   Criterion 1.5: User's character information (CharacterID, CharacterName, CharacterOwnerHash) is retrieved by validating the ID token JWT received from EVE SSO (using the JWKS URI) and/or by calling the ESI `/oauth/verify` endpoint with the access token.
    *   Criterion 1.6: A user account is created or updated in the Hangar Bay database linked to the EVE CharacterID. If an account exists for the CharacterID but the CharacterOwnerHash (obtained from the ID token/ESI `/oauth/verify`) mismatches the stored one, the existing record is updated with the new owner hash and tokens; Hangar Bay data associated with this user record follows the character.
    *   Criterion 1.7: The user is considered logged in, and the UI reflects this (e.g., shows character name, logout button).
*   **Story 2 Criteria:**
    *   Criterion 2.1: A secure session management mechanism is in place, utilizing secure, HTTPOnly cookies with a defined lifespan (e.g., 7 days), backed by a server-side session store (e.g., Valkey).
    *   Criterion 2.2: Users remain logged in across browser sessions until the session expires or they log out.
    *   Criterion 2.3: Access tokens are refreshed automatically using the refresh token before they expire if an ESI call is about to be made on behalf of the user and the current token is invalid or nearing expiry. For MVP, proactive background ESI calls (e.g., for watchlist updates when the user is not active) are not in scope for this feature; token refresh is primarily triggered by user activity requiring ESI interaction.
*   **Story 3 Criteria:**
    *   Criterion 3.1: A "Logout" button/link is available to logged-in users.
    *   Criterion 3.2: Clicking logout invalidates the user's session on Hangar Bay.
    *   Criterion 3.3: Logout from Hangar Bay invalidates the Hangar Bay session. It does not attempt to revoke the EVE SSO refresh token at the provider, aligning with standard OAuth client behavior. Users can manage third-party application authorizations via their EVE Online account settings.
*   **Story 4 Criteria:**
    *   Criterion 4.1: Access tokens and refresh tokens are stored securely (e.g., encrypted at rest).
    *   Criterion 4.2: Refresh tokens are used to obtain new access tokens when current ones expire.
    *   Criterion 4.3: Token handling adheres to OAuth 2.0 best practices (e.g., state parameter for CSRF protection, PKCE if applicable for public clients, though backend app is confidential client).

## 4. Scope (Required)
### 4.1. In Scope
*   Integration with EVE Online SSO (OAuth 2.0).
*   User login and logout functionality.
*   Secure management of EVE SSO tokens (access and refresh tokens).
*   Creation/management of basic user profiles in Hangar Bay DB (CharacterID, CharacterName, token info).
*   Session management for logged-in users.
*   Requesting **no ESI scopes** for the F004 authentication feature itself. User identification (CharacterID, Name, OwnerHash) is obtained from the ID token. ESI scopes (e.g., for reading contracts, market data, etc.) will be requested by other features (F005-F007) as needed. The `users.esi_scopes` field will store any scopes granted for those subsequent features.
### 4.2. Out of Scope
*   Requesting ESI scopes beyond basic authentication and character identification for this feature (other features may request more scopes).
*   User registration via email/password (only EVE SSO).
*   Role-based access control (RBAC) beyond simple authenticated vs. unauthenticated status (unless future features require it).
*   Two-factor authentication (relies on EVE SSO's 2FA).

## 5. Key Data Structures / Models (Optional, but often Required)
<!-- AI_NOTE_TO_HUMAN: For AI processing, please try to include a structured comment block like the example below for each significant data model. -->
*   Describe any new or significantly modified data structures, database tables, or object models relevant to this feature.
*   Include field names, data types, and brief descriptions.
*   **AI Assistant Guidance:** If any model fields store user-facing text that might require translation (e.g., descriptions, names not from a fixed external source like ESI), ensure they are designed with internationalization in mind. Consult `../i18n-spec.md` for strategies. For F004, `character_name` is sourced from ESI. Any Hangar Bay specific user-configurable text fields added in the future would need i18n consideration.

*   **`users` table:**
    <!-- AI_HANGAR_BAY_DATA_MODEL_START
    Model_Name: User
    Brief_Description: Stores Hangar Bay user information, linked to an EVE Online character.
    Fields:
      - id: INTEGER (Primary Key, Auto-increment)
      - character_id: BIGINT (Unique, EVE Online Character ID, Indexed)
      - character_name: VARCHAR(255)
      - owner_hash: VARCHAR(255) (From ESI character verification, Indexed)
      - esi_access_token: TEXT (Encrypted)
      - esi_access_token_expires_at: TIMESTAMP WITH TIME ZONE
      - esi_refresh_token: TEXT (Encrypted)
      - esi_scopes: TEXT (Comma-separated list of ESI scopes granted by the user for other features, e.g., F005-F007; F004 itself requests no scopes)
      - last_login_at: TIMESTAMP WITH TIME ZONE
      - created_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP)
      - updated_at: TIMESTAMP WITH TIME ZONE (Default: CURRENT_TIMESTAMP, On Update: CURRENT_TIMESTAMP)
    Relationships: (e.g., One-to-many with SavedSearches, WatchlistItems - to be defined in their respective features)
    AI_Action_Focus: Backend (SQLAlchemy model, Pydantic schema for API responses). Ensure robust encryption for token fields. Implement logic for creating/updating user records upon SSO callback.
    I18n_Considerations: `character_name` is from ESI. Other fields are internal or timestamps.
    AI_HANGAR_BAY_DATA_MODEL_END -->
*   **Session store data:** (Managed by web framework/session library, e.g., Valkey-backed sessions for FastAPI)
    *   `session_id`: VARCHAR (Key in Valkey)
    *   `user_id`: INTEGER (Foreign Key to `users.id`)
    *   `character_id`: BIGINT
    *   `character_name`: VARCHAR
    *   `expires_at`: TIMESTAMP (Managed by session middleware)

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   EVE SSO OAuth Endpoints:
    *   Authorization URL: `https://login.eveonline.com/v2/oauth/authorize`
    AI_Actionable_Checklist:
      - [ ] **Developer Action:** Verify endpoint path, parameters, and expected flow against the official EVE SSO documentation: [https://developers.eveonline.com/docs/services/sso/](https://developers.eveonline.com/docs/services/sso/)
      - [ ] **Developer Action:** Review EVE SSO Best Practices and Security guide: [https://developers.eveonline.com/docs/services/sso/best-practices-and-security/](https://developers.eveonline.com/docs/services/sso/best-practices-and-security/)
    *   *(Note: These checklist items are for developer verification during implementation. The specified endpoints are standard for EVE SSO.)*
    *   Token URL: `https://login.eveonline.com/v2/oauth/token`
    AI_Actionable_Checklist:
      - [ ] **Developer Action:** Verify endpoint path, parameters, and expected flow against the official EVE SSO documentation: [https://developers.eveonline.com/docs/services/sso/](https://developers.eveonline.com/docs/services/sso/)
      - [ ] **Developer Action:** Review EVE SSO Best Practices and Security guide: [https://developers.eveonline.com/docs/services/sso/best-practices-and-security/](https://developers.eveonline.com/docs/services/sso/best-practices-and-security/)
    *   *(Note: These checklist items are for developer verification during implementation. The specified endpoints are standard for EVE SSO.)*
    *   JWKS URI (for token verification): `https://login.eveonline.com/oauth/jwks`
    AI_Actionable_Checklist:
      - [ ] **Developer Action:** Verify endpoint path, parameters, and expected flow against the official EVE SSO documentation: [https://developers.eveonline.com/docs/services/sso/](https://developers.eveonline.com/docs/services/sso/)
      - [ ] **Developer Action:** Review EVE SSO Best Practices and Security guide: [https://developers.eveonline.com/docs/services/sso/best-practices-and-security/](https://developers.eveonline.com/docs/services/sso/best-practices-and-security/)
    *   *(Note: These checklist items are for developer verification during implementation. The specified endpoints are standard for EVE SSO.)*
*   ESI Endpoint for Access Token Verification (Optional/Secondary):
    *   `GET https://esi.evetech.net/oauth/verify`
        *   Requires authentication with the access token.
        *   Response includes: `CharacterID`, `CharacterName`, `ExpiresOn`, `Scopes`, `TokenType`, `CharacterOwnerHash`.
        *   Primary user identification should come from validating the ID token JWT locally.
        *   This endpoint can be used to verify an access token's validity or check its associated scopes if needed before an ESI call.
        AI_Actionable_Checklist:
          - [ ] **Developer Action:** Verify endpoint path, parameters, and response schema against the official ESI Swagger UI ([https://esi.evetech.net/ui/](https://esi.evetech.net/ui/)) and EVE SSO Documentation.
          - [ ] **Developer Action:** Review ESI Best Practices for this endpoint.
        *(Note: These checklist items are for developer verification during implementation.)*
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `/auth/sso/login` (GET)
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /auth/sso/login
    HTTP_Method: GET
    Brief_Description: Initiates the EVE SSO OAuth 2.0 flow by redirecting the user to the EVE Online authorization URL.
    Request_Path_Parameters_Schema_Ref: None
    Request_Query_Parameters_Schema_Ref: Optional 'next' URL (string) for redirect after successful login. Must be validated by the backend to prevent open redirect vulnerabilities (e.g., ensure it's a relative path or points to an allowed domain).
    Success_Response_Schema_Ref: HTTP 302 Redirect to EVE Online SSO.
    Error_Response_Codes: 500 (If unable to generate state or construct redirect URL).
    AI_Action_Focus: Backend: Generate and store a CSRF `state` token. Construct the EVE SSO authorization URL with appropriate `client_id`, `redirect_uri`, `scope`, and `state`. Frontend: A simple link or button that directs the user to this backend endpoint.
    I18n_Considerations: Error messages if any presented directly from this endpoint should be internationalized.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 2:** `/auth/sso/callback` (GET)
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /auth/sso/callback
    HTTP_Method: GET
    Brief_Description: Handles the callback from EVE SSO after user authorization. Exchanges authorization code for tokens, verifies character, creates/updates user record, and establishes a session.
    Request_Query_Parameters_Schema_Ref: `code` (authorization_code from EVE SSO), `state` (CSRF token from Hangar Bay).
    Success_Response_Schema_Ref: HTTP 302 Redirect to a logged-in area (e.g., dashboard or 'next' URL).
    Error_Response_Codes: 400 (Bad Request - e.g., state mismatch, missing code), 500 (Internal Server Error - e.g., failed token exchange, DB error).
    AI_Action_Focus: Backend: CRITICAL. Verify `state`. Exchange `code` for tokens (ID token, access token, refresh token) with EVE SSO. **Primarily, validate the ID token JWT locally using JWKS to get CharacterID, Name, OwnerHash.** Find/Create user in DB (handling CharacterOwnerHash changes as per Criterion 1.6). Store tokens securely. Create Hangar Bay session. Frontend: Generally no direct interaction; browser is redirected here by EVE SSO.
    I18n_Considerations: User-facing error pages resulting from failures in this flow must be internationalized.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 3:** `/auth/sso/logout` (POST recommended, GET for simplicity if no side effects beyond logout)
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /auth/sso/logout
    HTTP_Method: POST
    Brief_Description: Logs the currently authenticated user out of Hangar Bay by invalidating their session.
    Request_Body_Schema_Ref: None
    Success_Response_Schema_Ref: HTTP 200 OK or HTTP 302 Redirect to homepage/login page.
    Error_Response_Codes: 500 (If session invalidation fails).
    AI_Action_Focus: Backend: Invalidate/delete the user's session. Clear session cookie. Frontend: A button that triggers a request to this endpoint.
    I18n_Considerations: Any confirmation messages should be internationalized.
    AI_HANGAR_BAY_API_ENDPOINT_END -->
*   **Endpoint 4:** `/api/v1/me` (GET)
    <!-- AI_HANGAR_BAY_API_ENDPOINT_START
    API_Path: /api/v1/me
    HTTP_Method: GET
    Brief_Description: Retrieves information about the currently authenticated user (e.g., CharacterID, CharacterName).
    Request_Path_Parameters_Schema_Ref: None
    Success_Response_Schema_Ref: UserPublic (Pydantic model/TS Interface: e.g., { character_id: int, character_name: str }).
    Error_Response_Codes: 401 (Unauthorized - if no valid session), 500.
    AI_Action_Focus: Backend: Requires authentication. Retrieve user details from session or DB. Frontend: Call this to get current user info for display or conditional UI rendering.
    I18n_Considerations: `character_name` is from ESI.
    AI_HANGAR_BAY_API_ENDPOINT_END -->

## 7. Workflow / Logic Flow (Optional)
**Login Flow:**
1.  User clicks "Login with EVE Online".
2.  Hangar Bay backend generates a unique `state` parameter for CSRF protection and stores it in the user's session (or a temporary cookie).
3.  User is redirected to EVE SSO authorization URL with `response_type=code`, `client_id`, `redirect_uri`, `scope`, and `state`.
4.  User authenticates with CCP and authorizes Hangar Bay.
5.  EVE SSO redirects user back to Hangar Bay's `/auth/sso/callback` with an `authorization_code` and the original `state`.
6.  Hangar Bay backend verifies the `state` parameter.
7.  Backend makes a POST request to EVE SSO token URL with `grant_type=authorization_code`, `code`, `client_id`, and `client_secret` (if confidential client).
8.  EVE SSO responds with `access_token`, `refresh_token`, `expires_in`.
9.  Backend validates the ID token JWT (using EVE SSO's JWKS URI) to obtain `CharacterID`, `CharacterName`, `CharacterOwnerHash`. (Optionally, it may also call ESI `/oauth/verify` with the access token for further verification or to get associated scopes if needed immediately, though scope checking is typically deferred until the scope is actually required by a feature).
10. Backend finds or creates a user in its `users` table based on `CharacterID`.
11. Securely store/update tokens and expiry for the user.
12. Establish a session for the user (e.g., set secure HTTPOnly session cookie).
13. Redirect user to a logged-in landing page or their previous page.

**Logout Flow:**
1.  User clicks "Logout".
2.  Frontend sends request to `/auth/sso/logout`.
3.  Backend invalidates the user's session (e.g., deletes session from store, clears session cookie).
4.  Redirect user to homepage or login page.

**Access Token Refresh (Conceptual - may not be user-facing):**
1.  Before making an ESI call requiring auth, check if `access_token` is close to expiry.
2.  If yes, use `refresh_token` to request a new `access_token` from EVE SSO token URL (`grant_type=refresh_token`).
3.  Update stored `access_token` and its new expiry.

## 8. UI/UX Considerations (Optional)
*   Clear "Login with EVE Online" button, possibly using official EVE branding assets if permitted.
*   Display of logged-in user (e.g., character name, portrait if fetched) in the UI header/navigation.
*   Clear "Logout" option.
*   Graceful handling of SSO errors (e.g., user denies authorization, EVE SSO down) with user-friendly messages.
*   **AI Assistant Guidance:** When generating UI components for login/logout, ensure all display strings (button text, status messages, error messages) are prepared for localization using Angular's i18n mechanisms (e.g., `i18n` attribute, `$localize` tagged messages) as detailed in `../i18n-spec.md`. Ensure interactive elements like login/logout buttons are accessible (keyboard navigable, proper ARIA roles if custom components are used) as per `../accessibility-spec.md`.

## 9. Error Handling & Edge Cases (Required)
*   EVE SSO unavailable or returns errors: Log, inform user, retry if appropriate.
*   User denies authorization on EVE SSO: Redirect back to Hangar Bay with a message.
*   Invalid `state` parameter on callback: Abort login, potential CSRF attempt.
*   Failure to exchange authorization code for tokens: Log, inform user.
*   Failure to verify character with access token: Log, inform user.
*   Secure token storage failure: Critical error, log, potentially prevent login.
*   Refresh token becomes invalid: User needs to re-authenticate fully.

## 10. Security Considerations (Required - Consult `../security-spec.md`)
*   **CRITICAL:** Adherence to OAuth 2.0 (RFC 6749) and OAuth 2.0 Security Best Current Practice (RFC 6819).
*   Use `state` parameter to prevent CSRF during SSO callback.
*   PKCE (RFC 7636) should be considered if the client acts more like a public client (e.g., SPA making direct calls), but for a traditional web app with a backend, the confidential client flow with a `client_secret` is typical.
*   Secure storage of `client_secret` (if applicable), access tokens, and refresh tokens (encryption at rest is mandatory).
*   Use HTTPS for all communications (Hangar Bay frontend, backend, EVE SSO, ESI).
*   Secure, HTTPOnly, SameSite session cookies.
*   Validate ESI token issuer and claims if using JWTs directly (EVE SSO provides JWKS URI).
*   Protect callback endpoint from misuse.
*   Regularly review EVE Online developer documentation for security updates related to SSO.
*   Refer to `security-spec.md` for general and specific guidelines (e.g., token handling, encryption standards).

## 11. Performance Considerations (Optional, but Recommended - Consult `../performance-spec.md`)
*   SSO login flow involves multiple redirects and API calls; ensure it's as streamlined as possible.
*   Database lookups/writes for user accounts should be efficient.
*   Session store access should be fast (Valkey is good for this).

## 12. Accessibility Considerations (Optional, but Recommended - Consult `../accessibility-spec.md`)
*   Login/Logout buttons must be keyboard accessible and have clear focus indicators.
*   If using EVE Online branded login buttons, ensure they meet accessibility contrast ratios or provide an accessible alternative.
*   Any error messages or feedback related to the login/logout process must be announced by screen readers (e.g., using ARIA live regions if dynamic).
*   The user's login status (e.g., display of character name) should be presented in a way that's clear to assistive technologies.
*   Refer to `../accessibility-spec.md` for general guidelines.
*   **AI Assistant Guidance:** "Ensure login and logout buttons are standard HTML buttons or accessible custom components. Provide clear visual focus states. Error messages related to authentication should be programmatically associated with input fields if applicable, or announced via ARIA live regions."

## 13. Internationalization (i18n) Considerations (Optional, but Recommended - Consult `../i18n-spec.md`)
*   **Translatable Content:**
    *   UI Text: "Login with EVE Online", "Logout", "Login successful", "Login failed: [reason]", "Logged out successfully", etc.
*   **Non-Translatable Content (from ESI):**
    *   Character names are provided by EVE SSO/ESI and are typically not translated by the client application.
*   Refer to `../i18n-spec.md` for specific Angular i18n patterns.
*   **AI Assistant Guidance:** "Ensure all static user-facing strings in Angular components related to authentication (buttons, labels, messages) are externalized or marked for translation using Angular's `@angular/localize`. Error messages from the backend should ideally be translatable keys or messages."

## 14. Dependencies (Optional)
*   EVE Online SSO service.
*   Backend database (e.g., PostgreSQL).
*   Session storage (e.g., Valkey).
*   Encryption library for token storage.
*   OAuth 2.0 client library for the backend language/framework (e.g., Python's `requests-oauthlib` or framework-specific integrations).

## 15. Notes / Open Questions (Optional)
*   **[DECIDED]:** Initial ESI scopes: **None**. F004 focuses on authentication. User identification (CharacterID, Name, OwnerHash) is derived from the ID token. Other features (F005-F007) will request specific ESI scopes as needed, which will then be stored in `users.esi_scopes`.
*   **[DECIDED]:** Strategy for refresh token failure/revocation: If a refresh token is invalid (e.g., revoked by user, expired due to EVE policy): 1. Invalidate the Hangar Bay session for the user. 2. Clear the invalid refresh token and associated access token from the Hangar Bay database. 3. Redirect the user to the login page. 4. Display a clear message (e.g., "Your session has expired or authorization was revoked. Please log in again.").
*   **[CLARIFIED]:** Token verification: Primarily rely on **local validation of the ID token JWT** using EVE SSO's JWKS URI (`https://login.eveonline.com/oauth/jwks`) to get user details (CharacterID, Name, OwnerHash). The ESI endpoint `GET /oauth/verify` can be used with an access token for secondary verification or to check its associated scopes. The access token itself is used for ESI calls and should generally be treated as opaque by Hangar Bay, though it might also be a JWT.
*   **[DECIDED]:** Session duration for Hangar Bay: Implement a longer-lived session (e.g., 7 days) managed by a secure, HTTPOnly cookie. Actual ability to perform ESI-authenticated actions will depend on valid and refreshable EVE tokens.
*   **[DECIDED]:** CharacterOwnerHash: Store and verify on each login. If the `CharacterOwnerHash` for a `CharacterID` mismatches the stored one, update the existing `users` record with the new `owner_hash` and new tokens. This allows Hangar Bay specific data (e.g., watchlists) to follow the character if it's transferred to another EVE account.

## 16. AI Implementation Guidance (Optional)
<!-- AI_NOTE_TO_HUMAN: This section is specifically for providing direct guidance to an AI coding assistant. -->

### 16.1. Key Libraries/Framework Features to Use
*   Backend (FastAPI):
    *   OAuth 2.0 client library (e.g., `Authlib`, `requests-oauthlib`, or FastAPI plugins like `fastapi-sso`).
    *   Session management library (e.g., `starlette-session` with Valkey or JWT-based sessions).
    *   Cryptography library for encrypting tokens at rest (e.g., `cryptography`).
    *   SQLAlchemy for DB interaction, Pydantic for data models.
*   Frontend (Angular):
    *   `HttpClientModule` for API calls.
    *   Angular Router for navigation.
    *   `@angular/localize` for i18n.

### 16.2. Critical Logic Points for AI Focus
*   **Backend:**
    *   Implementing the full OAuth 2.0 Authorization Code Grant flow with EVE SSO.
    *   Secure generation and validation of the `state` parameter (CSRF protection).
    *   Secure handling and storage of `client_id` and `client_secret`.
    *   Secure exchange of authorization code for access/refresh tokens.
    *   Verification of EVE SSO tokens (e.g., using JWKS for JWTs, or calling ESI `GET /verify/`).
    *   Creation and update of user records in the database, including secure (encrypted) storage of tokens.
    *   Robust session creation, management (e.g., secure HTTPOnly cookies), and invalidation.
    *   Mechanism for using refresh tokens to obtain new access tokens (may be a separate scheduled task or on-demand logic).
*   **Frontend:**
    *   Initiating the login flow by redirecting to the backend's `/auth/sso/login` endpoint.
    *   Handling logout requests.
    *   Displaying user login status (e.g., character name, logout button).
    *   Requesting user information from `/api/v1/me`.

### 16.3. Data Validation and Sanitization
*   Backend: Validate all incoming data from EVE SSO callback (`code`, `state`).
*   Backend: Validate responses from EVE SSO token endpoint and ESI `/verify/` endpoint.
*   Frontend: Handle potential errors from backend API calls gracefully.

### 16.4. Test Cases for AI to Consider Generating
*   **Backend (FastAPI - Integration/Unit Tests):**
    *   Test `/auth/sso/login` redirects correctly.
    *   Test `/auth/sso/callback` with valid code and state (mock EVE SSO responses) leading to user creation/login and session establishment.
    *   Test `/auth/sso/callback` with invalid state, missing code, or error from EVE SSO.
    *   Test `/auth/sso/logout` invalidates session.
    *   Test `/api/v1/me` returns correct user info when authenticated, and 401 when not.
    *   Test token encryption/decryption logic.
    *   Test access token refresh logic (if implemented).
*   **Frontend (Angular - Component/Service Tests):**
    *   Test login button navigates to backend login URL.
    *   Test logout button calls backend logout and updates UI.
    *   Test display of user information after successful login.
    *   Test UI state for unauthenticated users.

### 16.5. Specific AI Prompts or Instructions
*   **Backend (FastAPI):**
    *   "Implement the EVE Online SSO OAuth2 Authorization Code Grant flow. Create endpoints for `/auth/sso/login` (redirect to EVE), `/auth/sso/callback` (handle code, exchange for tokens, verify user via ESI `/verify/` or JWT validation, create/update user in DB, establish session), and `/auth/sso/logout` (invalidate session). Use [chosen OAuth library] and [chosen session library]."
    *   "Define SQLAlchemy model for `users` table including fields for `character_id`, `character_name`, encrypted `esi_access_token`, `esi_refresh_token`, `esi_access_token_expires_at`, and `esi_scopes`. Create corresponding Pydantic models."
    *   "Implement secure encryption and decryption for ESI tokens stored in the database."
    *   "Create an `/api/v1/me` endpoint that returns basic information for the authenticated user."
*   **Frontend (Angular):**
    *   "Create an `AuthService` in Angular to manage authentication state, initiate login (by navigating to backend `/auth/sso/login`), handle logout (by calling backend `/auth/sso/logout`), and fetch current user data (from backend `/api/v1/me`)."
    *   "Create UI components for a 'Login with EVE Online' button and a 'Logout' button. Update a shared UI area (e.g., header) to display the logged-in character's name or the login button based on auth state."
    *   "Ensure all user-facing text in authentication-related components is internationalized using `@angular/localize`."
