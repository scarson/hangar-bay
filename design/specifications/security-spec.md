# Hangar Bay - Security Specification

This document provides detailed security guidelines, standards, and technology-specific considerations for the Hangar Bay application. It complements the general Security section in the main `design-spec.txt`.

## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

## Core Security Principles

The security posture of Hangar Bay is founded on modern principles designed to protect against evolving threats. These principles should guide all security-related decisions and implementations:

*   **Assume Breach:** Operate under the assumption that attackers may have already compromised or will eventually compromise some part of the system. This mindset shifts focus from perimeter defense alone to include robust internal security, detection, and response capabilities.
*   **Zero Trust Architecture (ZTA):** Do not inherently trust any user, device, application, or network, regardless of whether it is internal or external to the organization's traditional network perimeter.
    *   **Verify Explicitly:** Always authenticate and authorize based on all available data points, including user identity, device health, service or workload context, and other relevant attributes.
    *   **Least Privilege Access:** Grant only the minimum necessary access rights and permissions required for a user or service to perform its designated function. Review and revoke unnecessary privileges regularly.
    *   **Microsegmentation:** Divide the network and application environment into smaller, isolated segments to limit the blast radius of a security incident. Enforce strict access controls between segments.
*   **Defense in Depth:** Implement multiple layers of security controls. If one control fails or is bypassed, other controls are in place to continue protecting assets.
*   **Security by Design:** Integrate security considerations into every phase of the software development lifecycle (SDLC), from initial design and requirements gathering through development, testing, deployment, and maintenance.
*   **Data Minimization:** Collect and retain only the data that is strictly necessary for the application's functionality. Reduce the attack surface and the potential impact of a data breach.

These principles, particularly "Assume Breach" and "Zero Trust," inform decisions such as encrypting all internal traffic (including to the database), strictly validating all inputs, and enforcing least privilege access.

## 1. Cryptography

### 1.1. Encryption in Transit

*   **TLS Requirement:** All external network traffic to and from the Hangar Bay application (including user-to-frontend, frontend-to-backend, backend-to-ESI, backend-to-database if over a network) MUST be encrypted using Transport Layer Security (TLS) version 1.2 or, preferably, TLS 1.3.
*   **Cipher Suites:** Only cipher suites that provide Perfect Forward Secrecy (PFS) MUST be used. This ensures that if a long-term server private key is compromised, past session keys (and thus past encrypted traffic) cannot be decrypted.
    *   For TLS 1.3, PFS is inherent in all cipher suites.
    *   For TLS 1.2, prefer ECDHE-based cipher suites (e.g., `ECDHE-ECDSA-AES128-GCM-SHA256`, `ECDHE-RSA-AES256-GCM-SHA384`). Avoid static key exchange ciphers (non-PFS).
*   **Certificate Management:** Use strong, valid X.509 certificates from a reputable Certificate Authority (CA). Implement automated certificate renewal (e.g., via Let's Encrypt with Certbot or integrated cloud provider solutions).
*   **HTTP Strict Transport Security (HSTS):** Implement HSTS to instruct browsers to only connect to the application via HTTPS. Include `preload` directive for maximum effectiveness.

    *   **AI Actionable Checklist (TLS & HSTS):**
        *   [ ] Verify TLS 1.3 is enabled and preferred on the web server (Nginx/Caddy/etc.).
        *   [ ] Verify TLS 1.2 is supported with PFS cipher suites only.
        *   [ ] Confirm HSTS header (`Strict-Transport-Security`) is set with `max-age` (e.g., 31536000), `includeSubDomains`, and `preload`.
        *   [ ] Check for automated certificate renewal (e.g., Let's Encrypt cron job or cloud provider integration).
        *   [ ] Ensure backend to ESI API calls use HTTPS.
        *   [ ] Ensure backend to PostgreSQL calls use TLS (aligns with Zero Trust principles - all internal traffic encrypted).

    *   **AI Implementation Pattern (TLS & HSTS):**
        *   Use a library like `certbot` for automated certificate renewal.
        *   Configure web server (e.g., Nginx) to prefer TLS 1.3 and use PFS cipher suites.
        *   Set HSTS header in web server configuration.

### 1.2. Encryption at Rest

*   **Principle of Data Minimization:** Do not store sensitive data if it is not absolutely necessary for core application functionality. You can't lose what you don't have.
*   **Scope:** This applies to data stored in the primary database (PostgreSQL), caching layer (Valkey, if persisting data or storing sensitive items), and any other persistent storage.
*   **Sensitive Data Requiring Encryption at Rest:**
    *   EVE SSO refresh tokens MUST be encrypted at rest in the database.
    *   User alert configurations or watchlist parameters, if they contain user-defined sensitive thresholds or notes, should be encrypted.
    *   Any other Personally Identifiable Information (PII) or user-specific sensitive data that must be stored.
*   **Encryption Methods:**
    *   **Database-Level Encryption:**
        *   Consider PostgreSQL's Transparent Data Encryption (TDE) capabilities if offered by the hosting environment, or full-disk encryption at the infrastructure level.
        *   Utilize PostgreSQL's `pgcrypto` extension for column-level encryption of specific sensitive fields (e.g., refresh tokens). This provides more granular control.
    *   **Application-Level Encryption:** For highly sensitive data, consider encrypting it within the application before storing it in the database. This requires careful key management.
    *   **Key Management:** Securely manage all encryption keys. Avoid hardcoding keys. Use a dedicated key management service (KMS) if available (e.g., AWS KMS, Azure Key Vault, HashiCorp Vault) or secure configuration management practices.
*   **Valkey Security:** While primarily a cache, if Valkey is configured for persistence or used to store sensitive session-like data, ensure its persistence files are protected by underlying file system permissions and disk encryption if possible. Valkey itself can be password protected.

    *   **AI Actionable Checklist (Encryption at Rest):**
        *   [ ] Identify all sensitive data fields requiring encryption (e.g., EVE SSO refresh tokens, specific user preferences).
        *   [ ] For PostgreSQL, implement column-level encryption using `pgcrypto` for identified fields.
        *   [ ] Ensure encryption keys are managed securely (e.g., environment variables, KMS), NOT hardcoded.
        *   [ ] If Valkey persists sensitive data, ensure `requirepass` is configured and persistence files are on an encrypted volume if possible.
        *   [ ] Verify application logic correctly encrypts data before writing and decrypts after reading.

### 1.3. Post-Quantum Cryptography (PQC) Aspiration

*   **Goal:** To enhance long-term data security against potential future threats from quantum computers.
*   **Strategy:** Monitor the standardization and maturation of NIST-approved Post-Quantum Cryptography algorithms (e.g., CRYSTALS-Kyber for Key Encapsulation Mechanisms - KEMs, CRYSTALS-Dilithium for digital signatures).
*   **Adoption Criteria:** Investigate and plan for the adoption of PQC for key exchange in TLS (e.g., via hybrid modes combining classical ECDHE with a PQC KEM) and potentially for other cryptographic functions (e.g., data-at-rest encryption, digital signatures on software updates) if applicable, under the following conditions:
    1.  Mature, well-vetted, and audited library support becomes available for the chosen technology stack (backend, frontend, web servers).
    2.  Integration does not introduce significant, unacceptable performance degradation.
    3.  Integration does not introduce undue complexity that could lead to implementation errors.
    4.  Industry best practices and standards for PQC deployment in web applications become clearer.
*   **Current Focus:** While PQC is an important future consideration, the immediate priority is the robust implementation of strong, classical cryptography (TLS 1.2/1.3 with PFS).

### 1.4. Secure Secret Storage and Management

*   **Principle:** Plaintext secrets (e.g., API keys, database passwords, ESI client secrets, private certificates, encryption keys) MUST NEVER be hardcoded in source code, committed to version control, embedded in configuration files that are not encrypted, or stored in insecure locations.
*   **Risks of Plaintext Secrets:**
    *   **Compromise via Code Exposure:** If the codebase is leaked, becomes open source unintentionally, or is accessed by unauthorized individuals, all embedded secrets are compromised.
    *   **Compromise via Configuration Files:** Unencrypted configuration files in deployment packages or accessible on a compromised server expose secrets.
    *   **Difficult Rotation:** Secrets embedded in code or files require code changes and redeployments for rotation, increasing complexity and risk.
    *   **Auditability Challenges:** Tracking access and usage of hardcoded secrets is difficult.
*   **Recommended Practices for Secret Management:**
    1.  **Environment Variables:** Load secrets from environment variables at runtime.
        *   For local development, use `.env` files (which MUST be gitignored) to populate environment variables. The `app/backend/.env.example` file serves as a template.
        *   In production/staging environments, inject environment variables through the hosting platform's secure mechanisms (e.g., Docker secrets, Kubernetes Secrets, PaaS environment variable configuration).
    2.  **Secrets Management Services:** For higher security needs and more complex environments, utilize dedicated secrets management services.
        *   Examples: HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, Google Cloud Secret Manager.
        *   These services provide secure storage, access control, auditing, and often automated rotation capabilities.
    3.  **Configuration Files (Encrypted):** If secrets must be in configuration files, the files themselves must be encrypted at rest, and decrypted only in memory at runtime using a master key managed securely (e.g., via a KMS or environment variable). This is generally more complex than using environment variables or dedicated services.
*   **Specific Application to Hangar Bay:**
    *   `ESI_CLIENT_SECRET`, `DATABASE_URL` (specifically the password component), and any other sensitive credentials for the backend MUST be managed via environment variables as the primary method.
    *   Encryption keys used for application-level or database-level encryption (Section 1.2) MUST also be managed as secrets, not hardcoded.

    *   **AI Actionable Checklist (Secure Secret Management):**
        *   [ ] Verify no plaintext secrets (API keys, passwords, client secrets, encryption keys) are present in source code (e.g., `config.py`, `main.py`).
        *   [ ] Verify no plaintext secrets are present in committed configuration files (e.g., `app/backend/.env.example` should only contain placeholders or non-sensitive defaults).
        *   [ ] Confirm `.env` files (containing actual secrets for local development) are listed in `.gitignore`.
        *   [ ] Ensure backend application (`config.py`) is configured to load all secrets from environment variables.
        *   [ ] Document the procedure for injecting secrets into production/staging environments (e.g., platform-specific instructions).
        *   [ ] If a secrets management service is adopted, document its usage and integration.

## 2. Authentication and Authorization

Details on EVE SSO token handling, session management, and API key security.

### 2.1. EVE SSO Integration
*   **OAuth 2.0 Flow:** Strictly adhere to the EVE Online OAuth 2.0 flow for authentication.
*   **State Parameter:** Use a cryptographically secure, unguessable `state` parameter to prevent CSRF attacks during the OAuth flow.
*   **PKCE (Proof Key for Code Exchange):** Implement PKCE (RFC 7636) if supported by EVE SSO for public clients (like a web frontend) to mitigate authorization code interception attacks.
*   **Token Storage (Backend):**
    *   Access Tokens: May be stored in a secure server-side session or passed to the frontend for API calls. If passed to frontend, ensure they are short-lived.
    *   Refresh Tokens: MUST be stored securely in the backend database, encrypted at rest (see Section 1.2). They should NEVER be exposed to the frontend.
*   **Token Usage:** Access tokens are used to make authenticated calls to ESI. Refresh tokens are used by the backend to obtain new access tokens when they expire.
*   **Scope Minimization:** Request only the minimum necessary ESI scopes required for the application's functionality.

    *   **AI Implementation Pattern (EVE SSO Backend - FastAPI):**
        *   Use a library like `Authlib` or `httpx-oauth` for handling OAuth 2.0 flow.
        *   Store refresh tokens encrypted in the PostgreSQL database.
        *   Implement endpoints for `/login`, `/callback`, `/logout`.
        *   `/login`: Redirects user to EVE SSO authorization URL with `state` and `code_challenge` (for PKCE).
        *   `/callback`: Verifies `state`, exchanges authorization code for tokens (with `code_verifier` for PKCE), stores refresh token, creates a session/JWT for the frontend.
        *   `/logout`: Invalidates local session/JWT, potentially revokes EVE SSO tokens if ESI provides such an endpoint and it's appropriate.
        *   Protect backend API endpoints requiring authentication using FastAPI's `Depends` with a security scheme (e.g., OAuth2PasswordBearer or custom JWT handler).

### 2.2. Frontend Session Management (If applicable)
*   If using JWTs passed to the frontend:
    *   Store JWTs securely (e.g., `HttpOnly`, `Secure`, `SameSite=Lax` or `Strict` cookies). Avoid `localStorage` for JWTs due to XSS risks.
    *   JWTs should be short-lived.
    *   Implement silent refresh mechanism using the refresh token (via a secure backend endpoint) to get new JWTs before they expire.

### 2.3. Authorization / Access Control
*   Once authenticated, ensure users can only access their own data or perform actions permitted by their roles (if roles are defined beyond 'authenticated user').
*   Example: A user should not be able to view or modify another user's watchlist.

    *   **AI Implementation Pattern (FastAPI Authorization):**
        *   In API endpoints dealing with user-specific resources, always fetch the resource based on the authenticated user's ID (obtained from the JWT/session) AND the resource ID from the path/query.
        *   Example: `GET /watchlist/{item_id}` should ensure `item_id` belongs to the current `user_id`.

## 3. Input Validation and Output Encoding

Crucial for preventing injection attacks (XSS, SQLi, etc.).

### 3.1. Input Validation (Backend - FastAPI)
*   **Pydantic Models:** Leverage FastAPI's use of Pydantic models for automatic request body validation. Define strict types, constraints (e.g., `min_length`, `max_length`, `gt`, `lt`, `pattern`).
*   **Path/Query Parameters:** FastAPI also validates path and query parameters based on type hints and `Query`/`Path` annotations.
*   **ESI Data:** Treat data from ESI as untrusted input. Validate IDs, expected data types, and structure before processing or storing.
*   **Business Logic Validation:** Perform additional validation based on business rules (e.g., ensuring a ship ID is a valid EVE Online ship type ID).

    *   **AI Implementation Pattern (FastAPI Input Validation):**
        *   Define Pydantic models for all request bodies.
        *   Use type hints and validation decorators (`Query`, `Path`, `Body`) for all endpoint parameters.
        *   Example: `async def get_item(item_id: int = Path(..., gt=0), q: Optional[str] = Query(None, min_length=3, max_length=50)):`
        *   For ESI data, after fetching, pass it through a Pydantic model for validation before further use.

### 3.2. Output Encoding (Frontend - Angular)
*   **Angular's Built-in Sanitization:** Angular automatically sanitizes values interpolated into templates (`{{ value }}`) to prevent XSS. Trust Angular's built-in mechanisms.
*   **`[innerHTML]` and `[outerHTML]`:** Avoid using these if possible. If absolutely necessary, ensure the HTML is sanitized using Angular's `DomSanitizer` (`bypassSecurityTrustHtml`).
*   **Attribute Binding:** Be cautious when binding to attributes that can execute code (e.g., `href` with `javascript:` URLs, `style` with `url()`). Angular helps, but be mindful.

    *   **AI Implementation Pattern (Angular Output Encoding):**
        *   Primarily rely on Angular's default interpolation: `<div>{{ userProvidedContent }}</div>`.
        *   If dynamic HTML is unavoidable: `constructor(private sanitizer: DomSanitizer) {} getSafeHtml(html: string) { return this.sanitizer.bypassSecurityTrustHtml(html); }` and use `[innerHTML]="getSafeHtml(userHtml)"`. Use with extreme caution.

### 3.3. SQL Injection (SQLi) Prevention
*   **ORM Usage:** Strictly use an ORM (SQLAlchemy for Python) for all database interactions. ORMs typically use parameterized queries or construct SQL safely, preventing most SQLi vulnerabilities.
*   **No Raw SQL with User Input:** NEVER construct SQL queries by concatenating strings with user-supplied input. If raw SQL is absolutely unavoidable for a complex query, ensure all user input is passed as parameters to the query execution method, not interpolated into the query string.

    *   **AI Implementation Pattern (SQLAlchemy):**
        *   Always use ORM methods: `db.query(User).filter(User.id == user_id).first()`
        *   If using `text()` for raw SQL: `from sqlalchemy import text; query = text("SELECT * FROM users WHERE id = :user_id"); result = db.execute(query, {"user_id": user_id})`

### 3.4. Secure Error Handling and Messages
*   **Principle:** User-facing error messages MUST be generic and MUST NOT reveal sensitive information such as internal system details, stack traces, database error messages, specific reasons for authentication/authorization failures that could aid an attacker (e.g., distinguish between 'user not found' and 'invalid password'), or debugging information.
*   **Practice:** Log detailed error information for internal diagnostics and troubleshooting only. Present users with a generic error message and a reference ID (correlation ID) if possible, which can be used to look up the detailed error in the internal logs.

    *   **AI Actionable Checklist (Secure Error Handling):**
        *   [ ] Review all user-facing error messages to ensure they are generic.
        *   [ ] Verify that detailed error information (stack traces, system messages) is logged internally and not exposed to users.
        *   [ ] Implement a global error handler (backend and frontend) to catch unhandled exceptions and present generic error messages.
        *   [ ] Consider using correlation IDs in user-facing error messages that map to detailed internal logs.

    *   **AI Implementation Pattern (FastAPI Generic Errors):**
        *   Implement custom exception handlers in FastAPI to catch specific exceptions (or a generic `Exception`) and return a standardized, generic JSON error response.
        *   Example:
            ```python
            from fastapi import Request, HTTPException
            from fastapi.responses import JSONResponse

            class UnicornException(Exception):
                def __init__(self, name: str, detail: str, internal_log_message: str):
                    self.name = name # For internal logging
                    self.detail = detail # Generic detail for user
                    self.internal_log_message = internal_log_message # Detailed log

            @app.exception_handler(UnicornException)
            async def unicorn_exception_handler(request: Request, exc: UnicornException):
                logger.error(f"UnicornException: {exc.name} - {exc.internal_log_message} - Path: {request.url.path}")
                return JSONResponse(
                    status_code=500, # Or appropriate HTTP status
                    content={"message": "An unexpected error occurred. Please try again later.", "detail": exc.detail, "error_ref": "some_correlation_id"},
                )
            ```
    *   **AI Implementation Pattern (Angular Generic Errors):**
        *   Implement an `ErrorHandler` in Angular to catch client-side errors and display a generic message or redirect to an error page.
        *   Log detailed errors to a remote logging service or the console (for development).
        *   When handling HTTP errors from API calls, display generic messages based on status codes or error content, avoiding direct display of API error internals.

## 4. Application-Specific Vulnerabilities

*(To be detailed: e.g., ESI data manipulation risks, race conditions in contract aggregation, DoS/DDoS mitigation strategies)*

## 5. Dependency Management

Managing third-party libraries securely.

*   **Minimize Dependencies:** Only include libraries that are actively needed.
*   **Reputable Sources:** Use official package repositories (PyPI for Python, npm for Node.js/Angular).
*   **Version Pinning:** Pin exact versions of dependencies in `requirements.txt` (Python) and `package-lock.json` (npm/Angular) to ensure reproducible and predictable builds.
*   **Regular Updates:** Regularly update dependencies to their latest secure versions after checking changelogs for breaking changes.
*   **Vulnerability Scanning:** Integrate automated vulnerability scanning tools into the CI/CD pipeline.
    *   Python: `safety`, `pip-audit`.
    *   Node.js/Angular: `npm audit`, Snyk, Dependabot (GitHub).

    *   **AI Actionable Checklist (Dependency Management):**
        *   [ ] Initialize project with `requirements.txt` (Python) and `package.json` (Angular).
        *   [ ] Pin all direct dependencies to specific versions.
        *   [ ] Generate and commit lock files (`requirements.txt` often serves this for Python if fully pinned, `package-lock.json` for npm).
        *   [ ] Set up Dependabot or Snyk for automated vulnerability alerts on the repository.
        *   [ ] Add `npm audit --audit-level=high` (Angular) and `pip-audit` (Python) steps to CI pipeline.

## 6. Logging and Monitoring

Essential for detecting and responding to security incidents.

### 6.1. Security Event Logging
*   **Log Key Events:**
    *   Authentication success and failure (including IP address, user agent).
    *   Authorization failures.
    *   Significant ESI API errors (especially rate limiting, auth errors).
    *   Critical application errors.
    *   Changes to sensitive user data (e.g., watchlist modifications, if applicable).
    *   Validation failures for critical inputs.
*   **Log Content:** Include timestamp, event type, user ID (if authenticated), source IP, relevant details. AVOID logging sensitive data like passwords, full ESI tokens, or excessive PII in logs.
*   **Log Storage:** Store logs securely, preferably centralized (e.g., ELK stack, cloud provider logging services). Protect logs from unauthorized access or tampering.

    *   **AI Implementation Pattern (FastAPI Logging):**
        *   Use Python's built-in `logging` module, configured in FastAPI.
        *   Create structured logs (e.g., JSON format) for easier parsing by log management systems.
        *   Example: `logger.info({"event": "login_success", "user_id": user.id, "ip_address": request.client.host})`

### 6.2. Monitoring
*   Monitor application performance, error rates, and resource usage.
*   Set up alerts for unusual activity, high error rates, or security events (e.g., multiple failed login attempts from the same IP).

    *   **AI Actionable Checklist (Logging & Monitoring Setup):**
        *   [ ] Configure Python `logging` in FastAPI to output structured logs.
        *   [ ] Ensure logs are written to a persistent location or streamed to a log management service.
        *   [ ] Identify key security events to log (as listed above).
        *   [ ] Implement logging for these events at appropriate points in the code.
        *   [ ] Set up basic monitoring for application health and error rates (e.g., using Sentry, Prometheus/Grafana, or cloud provider tools).

## 7. Infrastructure Security

*(To be detailed: Secure configuration of servers, databases, caching layers, firewalls)*
