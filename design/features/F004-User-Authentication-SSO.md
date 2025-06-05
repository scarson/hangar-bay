# Feature Spec: User Authentication (EVE SSO)

**Feature ID:** F004
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

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
    *   Criterion 1.5: User's character information (CharacterID, Name) is retrieved using the access token (`GET /verify/` endpoint or similar from new ESI structure).
    *   Criterion 1.6: A user account is created or updated in the Hangar Bay database linked to the EVE CharacterID.
    *   Criterion 1.7: The user is considered logged in, and the UI reflects this (e.g., shows character name, logout button).
*   **Story 2 Criteria:**
    *   Criterion 2.1: A secure session management mechanism is in place (e.g., secure HTTPOnly cookies, server-side session store).
    *   Criterion 2.2: Users remain logged in across browser sessions until the session expires or they log out.
    *   Criterion 2.3: Access tokens are refreshed automatically using the refresh token before they expire, without requiring user re-authentication, if active ESI calls are needed for the user. [NEEDS_DISCUSSION: Scope of background ESI calls for MVP features like saved searches/watchlists.]
*   **Story 3 Criteria:**
    *   Criterion 3.1: A "Logout" button/link is available to logged-in users.
    *   Criterion 3.2: Clicking logout invalidates the user's session on Hangar Bay.
    *   Criterion 3.3: [NEEDS_DISCUSSION: Should logout also attempt to revoke the EVE SSO token? Generally not standard for OAuth clients unless specifically required.]
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
*   Requesting necessary ESI scopes for authentication (e.g., `publicData` or a minimal scope if only character ID/name is needed initially).
### 4.2. Out of Scope
*   Requesting ESI scopes beyond basic authentication and character identification for this feature (other features may request more scopes).
*   User registration via email/password (only EVE SSO).
*   Role-based access control (RBAC) beyond simple authenticated vs. unauthenticated status (unless future features require it).
*   Two-factor authentication (relies on EVE SSO's 2FA).

## 5. Key Data Structures / Models (Optional, but often Required)
*   **`users` table:**
    *   `id`: INTEGER (Primary Key, Auto-increment)
    *   `character_id`: BIGINT (Unique, EVE Online Character ID)
    *   `character_name`: VARCHAR
    *   `owner_hash`: VARCHAR (From ESI, if available and needed for verification)
    *   `esi_access_token`: VARCHAR (Encrypted)
    *   `esi_access_token_expires_at`: TIMESTAMP
    *   `esi_refresh_token`: VARCHAR (Encrypted)
    *   `esi_scopes`: TEXT (Comma-separated list of granted ESI scopes)
    *   `last_login_at`: TIMESTAMP
    *   `created_at`: TIMESTAMP
    *   `updated_at`: TIMESTAMP
*   **Session store data:** (Managed by web framework/session library, e.g., Valkey-backed sessions)
    *   `session_id`: VARCHAR
    *   `user_id`: INTEGER (Foreign Key to `users` table)
    *   `expires_at`: TIMESTAMP

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   EVE SSO OAuth Endpoints:
    *   Authorization URL: `https://login.eveonline.com/v2/oauth/authorize`
    *   Token URL: `https://login.eveonline.com/v2/oauth/token`
    *   JWKS URI (for token verification): `https://login.eveonline.com/oauth/jwks`
*   ESI Endpoint for Character Verification (after token acquisition):
    *   `GET https://esi.evetech.net/verify/` (or equivalent in current ESI spec if path changed)
        *   Requires authentication with the new access token.
        *   Fields: `CharacterID`, `CharacterName`, `Scopes`, `TokenType`, `CharacterOwnerHash`.
### 6.2. Exposed Hangar Bay API Endpoints
*   `/auth/sso/login` (GET): Initiates the EVE SSO flow by redirecting the user to EVE's authorization URL.
*   `/auth/sso/callback` (GET): The redirect URI registered with EVE SSO. Handles the authorization code, exchanges it for tokens, verifies character, creates/updates user, and establishes session.
*   `/auth/sso/logout` (POST or GET): Logs the user out by invalidating their session.
*   `/api/v1/me` (GET): Returns information about the currently authenticated user (e.g., character name). Requires authentication.

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
9.  Backend calls ESI `GET /verify/` (or equivalent) using the new `access_token` to get `CharacterID`, `CharacterName`, etc.
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

## 9. Error Handling & Edge Cases (Required)
*   EVE SSO unavailable or returns errors: Log, inform user, retry if appropriate.
*   User denies authorization on EVE SSO: Redirect back to Hangar Bay with a message.
*   Invalid `state` parameter on callback: Abort login, potential CSRF attempt.
*   Failure to exchange authorization code for tokens: Log, inform user.
*   Failure to verify character with access token: Log, inform user.
*   Secure token storage failure: Critical error, log, potentially prevent login.
*   Refresh token becomes invalid: User needs to re-authenticate fully.

## 10. Security Considerations (Required)
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

## 11. Performance Considerations (Optional)
*   SSO login flow involves multiple redirects and API calls; ensure it's as streamlined as possible.
*   Database lookups/writes for user accounts should be efficient.
*   Session store access should be fast (Valkey is good for this).

## 12. Dependencies (Optional)
*   EVE Online SSO service.
*   Backend database (e.g., PostgreSQL).
*   Session storage (e.g., Valkey).
*   Encryption library for token storage.
*   OAuth 2.0 client library for the backend language/framework (e.g., Python's `requests-oauthlib` or framework-specific integrations).

## 13. Notes / Open Questions (Optional)
*   [NEEDS_DECISION: Initial ESI scopes to request. Start minimal (e.g., `publicData` or just enough for character ID/name) and add more as features require them? Or request a broader set upfront? Minimal is generally better practice.]
*   [NEEDS_DISCUSSION: Detailed strategy for handling refresh token failure/revocation by EVE. How to prompt user for re-auth gracefully?]
*   [NEEDS_CLARIFICATION: Current ESI endpoint for JWT-based token verification if `GET /verify/` is deprecated or there's a newer preferred method. EVE SSO typically returns JWT access tokens which can be verified locally using the JWKS.]
*   [NEEDS_DISCUSSION: Session duration for Hangar Bay. How long should users remain logged in?]
*   [NEEDS_DISCUSSION: Should Hangar Bay store `CharacterOwnerHash` and verify it on each login? This helps detect character transfers but adds complexity.]
