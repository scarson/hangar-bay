# Hangar Bay - EVE Online Ship Ecommerce Platform - Design Specification

## 1. Introduction

This document outlines the design specification for Hangar Bay, an e-commerce application for buying and selling ships within the video game EVE Online. The application aims to provide a secure, user-friendly platform for players to trade ships.

## 2. Goals

*   To create a secure and reliable platform for discovering EVE Online public ship contracts.
*   To provide an intuitive user interface for browsing, searching, and filtering public ship contracts.
*   To integrate seamlessly with the EVE Online ESI API for up-to-date contract, ship, and market information.
*   To help players efficiently find desirable ship contracts available in-game.
*   To ensure the application is accessible and usable by people with a wide range of abilities, adhering to WCAG 2.1 AA as a minimum (see `accessibility-spec.md`).
*   To design the application with internationalization (i18n) capabilities from the outset, enabling future localization for EVE Online's global player base (see `i18n-spec.md`).
*   To ensure the application meets high performance standards for responsiveness, scalability, and resource efficiency, as detailed in `performance-spec.md`.

## 3. Target Audience

*   EVE Online players worldwide looking to find and acquire ships through public contracts.
*   EVE Online players globally who have listed ships on public contracts and want them to be discoverable.
*   Players interested in current ship availability and pricing via public contracts, potentially in their preferred language.

## 4. Security

**SECURITY IS ABSOLUTELY PARAMOUNT FOR THIS APPLICATION.**

EVE Online players, the target audience for Hangar Bay, are known for their ingenuity in exploiting systems. Theft, deceit, extortion, hacking, and scheming are considered legitimate parts of the EVE Online metagame. This application **will** be targeted by parties with malicious intent who will attempt to exploit it in every conceivable way. **WE MUST NOT LET THAT HAPPEN.**

*   **No Tradeoffs:** There must be NO tradeoffs where security is sacrificed for features, convenience, or performance.
*   **Overriding Concern:** Security must be an overriding concern in every applicable design and implementation area.
*   **Minimum Standards:** At an absolute minimum, the application MUST take extreme precautions against:
    1.  All **OWASP Top 10 Web Application Security Risks** (latest version).
    2.  All applicable **OWASP API Security Top 10 Risks** (latest version).
    3.  Employ leading/best **secure coding practices** for all languages, frameworks, and technologies used in the application.
*   **Proactive Threat Modeling:** We must proactively think through potential attack vectors and risks for the application and aggressively eliminate them by design or implement effective mitigations wherever possible.
*   **Risk Management:** Where attack vectors and risks cannot be effectively eliminated by design or mitigated, we must extensively think through possible alternatives. If no alternatives are feasible, the risk must be documented as clearly as possible, including its potential impact and likelihood.
*   **Detailed Security Specification:** A separate document, `security-spec.md` (located in the `design` directory), provides more detailed security guidelines, standards, and technology-specific considerations. This main design spec will reference it where appropriate. All security principles outlined here and in `security-spec.md` are mandatory.
*   **EVE SSO Security:** EVE Single Sign-On (SSO) will be used. Access tokens and refresh tokens must be handled with utmost security, adhering to OAuth 2.0 best practices, including secure storage (e.g., encrypted in the database, HTTPOnly cookies for refresh tokens), transmission (HTTPS only), and minimal scope requests. Refer to `security-spec.md` for detailed token handling procedures.
*   **Input Validation:** All user-supplied input (including API inputs from ESI) must be rigorously validated on both client and server sides to prevent injection attacks (SQLi, XSS, command injection, etc.). Refer to `security-spec.md`.
*   **Output Encoding:** All data output to users must be properly encoded to prevent XSS attacks. Refer to `security-spec.md`.
*   **Authentication & Authorization:** Robust authentication (via EVE SSO) and authorization mechanisms must be implemented to ensure users can only access their own data (e.g., watchlists) and perform permitted actions. Refer to `security-spec.md`.
*   **Session Management:** Secure session management practices must be followed if backend sessions are used in conjunction with SSO tokens. Refer to `security-spec.md`.
*   **Cryptography:** All data in transit must be encrypted using TLS 1.2 or TLS 1.3 with Perfect Forward Secrecy. Refer to `security-spec.md` for detailed cryptographic standards, including aspirations for Post-Quantum Cryptography.
*   **Dependency Security:** All third-party libraries and dependencies must be kept up-to-date and monitored for vulnerabilities. Refer to `security-spec.md`.
*   **Data Privacy:** Consideration must be given to any player data stored (e.g., EVE character ID, watchlists), ensuring it is minimized, protected, and handled according to privacy best practices. Refer to `security-spec.md`.
*   **Regular Security Audits:** Plan for regular security reviews and penetration testing.

**(All other sections should also reference Section 4: Security, and where appropriate, `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, `observability-spec.md`, `i18n-spec.md`, and `design-log.md`.)* must include a reference to this Security section and, where applicable, to these detailed specifications, with instructions to consider them an integral part of their respective requirements.**

## 5. Application Architecture (High-Level)

The Hangar Bay application follows a modern web application architecture, designed for modularity, scalability, and maintainability. It functions primarily as an aggregator and sophisticated browser for public EVE Online ship contracts.

The core components are:

*   **Frontend (Client-Side Application):**
    *   **Technology:** Angular (with TypeScript).
    *   **Responsibilities:** Provides the user interface (UI) for browsing, searching, filtering (F002), and viewing detailed ship contracts (F003). Handles user interactions, makes API requests to the Backend, and renders data. Manages client-side state and routing.
    *   **Interaction:** Communicates exclusively with the Hangar Bay Backend API via HTTPS.

*   **Backend (Server-Side API & Logic):**
    *   **Technology:** Python with FastAPI (ASGI).
    *   **Responsibilities:**
        *   Exposes a RESTful API for the Frontend.
        *   Implements business logic for features F001, F002, F003, including data aggregation, filtering, and search.
        *   Manages interaction with the Database for data persistence and retrieval.
        *   Integrates with the ESI API Integration Layer to fetch data from EVE Online.
        *   Handles user authentication (F004) and authorization for protected endpoints and features (F005-F007, when implemented).
        *   Interacts with the Caching Layer to improve performance.

*   **Database (Persistence Layer):**
    *   **Technology:** PostgreSQL (Production), SQLite (Development).
    *   **Responsibilities:** Stores aggregated public contract data (F001), cached ESI type details (ships, items), market group information, and potentially user-specific data such as saved searches (F005) and watchlists (F006) once authentication is implemented.
    *   **Access:** Primarily accessed by the Backend API via an ORM (SQLAlchemy).

*   **Caching Layer:**
    *   **Technology:** Valkey (Redis-compatible).
    *   **Responsibilities:** Caches frequently accessed data, such as ESI API responses (respecting ESI cache headers), pre-calculated data, and popular query results to reduce database load and improve API response times.
    *   **Access:** Used by the Backend API.

*   **EVE ESI API Integration Layer (Backend Module):**
    *   **Responsibilities:** A dedicated module within the Backend responsible for all communications with the EVE Online ESI API. This includes:
        *   Constructing and sending ESI requests.
        *   Handling ESI responses, including pagination, error codes (4xx, 5xx), and rate limits.
        *   Adhering to ESI caching policies (Cache-Control, ETag).
        *   Transforming ESI data into formats suitable for the Hangar Bay application.
        *   Managing EVE SSO OAuth 2.0 flow for user authentication (F004).

### 5.1. High-Level Data Flow

1.  **User Interaction:** A user accesses the Hangar Bay application via a web browser (Frontend).
2.  **Frontend Request:** The Frontend makes API calls (e.g., to search for contracts) to the Backend API.
3.  **Backend Processing:**
    *   The Backend API receives the request, validates it, and processes it.
    *   For data retrieval, it first checks the Caching Layer (Valkey).
    *   If data is not in the cache or is stale, it queries the Database (PostgreSQL).
    *   If the required data originates from EVE Online (e.g., new contracts, type details not yet cached), the ESI API Integration Layer is invoked.
4.  **ESI Interaction (if needed):**
    *   The ESI API Integration Layer makes secure HTTPS requests to the EVE ESI API.
    *   It receives responses, respects cache headers, and handles potential errors or rate limits.
    *   Fetched data is processed and may be stored in the Database and/or Caching Layer for future requests.
5.  **Backend Response:** The Backend API formats the data and sends a response to the Frontend.
6.  **Frontend Rendering:** The Frontend receives the API response and dynamically updates the UI to display the information to the user.

**Scheduled/Background Processes (F001):**
*   A separate process, managed by the Backend (e.g., using a task scheduler like Celery, or a simpler cron-like mechanism for MVP), periodically invokes the ESI API Integration Layer to fetch new public contracts from specified EVE Online regions.
*   This data is then processed, filtered for ships, and stored in the Database.

*Considerations: All interactions between components, especially over networks (Frontend-Backend, Backend-ESI), MUST be secured using HTTPS. Refer to Section 4 (Security) and `security-spec.md`. Accessibility, as outlined in `accessibility-spec.md`, and internationalization, as per `i18n-spec.md`, must be considered for any user-facing outputs or interactions originating from these components.* 

## 6. Tech Stack

The following technology stack is proposed, with security, performance, and rapid development as key considerations. Specific versions will be determined at the start of implementation and documented in `requirements.txt` (for Python) or equivalent dependency files.

*   **Backend Framework: Python with FastAPI**
    *   **Reasoning:** Modern, high-performance, asynchronous support for efficient ESI API calls, automatic data validation, and OpenAPI documentation. Python's extensive libraries facilitate rapid development.
    *   **Alternatives Considered:** Go (excellent performance and concurrency, but potentially slower initial development for web features compared to FastAPI).
*   **ASGI Server (for FastAPI):**
    *   **Development:** Uvicorn (direct execution).
    *   **Production: Gunicorn with Uvicorn workers.**
    *   **Reasoning:** Uvicorn provides high-speed ASGI request handling. Gunicorn offers robust process management, worker scaling, and resilience suitable for production environments.
    *   **Alternatives Considered:** Hypercorn (another capable ASGI server).
*   **Database: PostgreSQL (Production) / SQLite (Development)**
    *   **Reasoning:** PostgreSQL offers robustness, scalability, and advanced features for production. SQLite provides ease of use for local development.
    *   **ORM Requirement:** An Object-Relational Mapper (ORM), such as SQLAlchemy for Python, MUST be used to interact with the database. This abstracts database-specific SQL, facilitates easier schema management, and aids in maintaining compatibility if the underlying database engine were to change (though the primary goal here is PostgreSQL).
    *   **Schema Design:** Database schemas and queries will be designed with PostgreSQL's capabilities and best practices in mind from the outset.
    *   **Data Population:** Production database will be populated with fresh data from ESI and other relevant sources; migration of data from development SQLite instances will not be required.
*   **Caching Layer: Valkey**
    *   **Reasoning:** A community-driven fork of Redis, offering high performance in-memory caching suitable for ESI responses and frequently accessed data. Chosen for its open-source governance and compatibility with Redis clients.
*   **Frontend Framework: Angular**
    *   **Reasoning:** A comprehensive and structured framework with TypeScript support, aligning with the USER's interest in learning it. Capable of building a rich user interface. TypeScript's static typing can contribute to robustness and help avoid certain classes of errors. Angular also has good support for accessibility (see `accessibility-spec.md`).
*   **Web Server (for serving static frontend assets, if not using a CDN):**
    *   *(Placeholder: e.g., Nginx, Caddy, or cloud provider's static asset hosting. Often the backend API and frontend are served via different mechanisms/domains or through a reverse proxy.)*

### 6.7. AI Implementation Notes
*   **General:** AI should prioritize code clarity, modularity, and adherence to specified patterns in feature specs (e.g., structured data models, API endpoint comments).
*   **Backend (Python/FastAPI):** AI should leverage Pydantic for robust data validation and serialization. Focus on creating efficient database queries and asynchronous operations where appropriate (e.g., ESI calls).
*   **Frontend (Angular):** AI should generate well-structured components, services, and modules. Utilize Angular Material and CDK for accessible and consistent UI elements. Employ RxJS for managing asynchronous data streams effectively. Ensure internationalization support using `@angular/localize`.
*   **Testing:** AI should assist in generating unit tests for all new logic (backend and frontend) and provide outlines for integration/E2E tests as guided by feature specs.

*Considerations: Refer to Section 4 (Security) and the detailed `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, `observability-spec.md`, and `i18n-spec.md`. The security, accessibility, internationalization, and testing best practices for each chosen technology will be strictly adhered to. This includes secure and accessible configuration, regular patching, and leveraging built-in mechanisms (e.g., `@angular/localize` for Angular i18n, `fastapi-babel` for FastAPI i18n).* 

## 7. Core Features
<!-- AI_NOTE_TO_HUMAN: This section outlines the primary functionalities. AI development should focus on implementing these robustly, with attention to the details in their respective feature specification documents. -->

Based on the **public contract aggregator model**:

*   **Public Contract Aggregation & Display:**
    *   Regularly fetch public item exchange and auction contracts from specified EVE Online regions.
    *   Filter contracts to identify those primarily offering ships.
    *   Display key contract details: ship type, name, quantity, price (ISK), contract type (auction/item exchange), location (station/structure), issuer, expiration date.
*   **Ship Browsing & Advanced Searching/Filtering:**
    *   Browse aggregated ship contracts.
    *   Search by ship name, type, or category (e.g., Frigate, Cruiser, Battleship).
    *   Filter by region, solar system, station/structure.
    *   Filter by price range, tech level, specific ship attributes (e.g., number of turret slots, drone bay capacity) if feasible by caching ship details.
    *   Sort results by price, expiration date, date listed.
*   **Detailed Ship Contract View:**
    *   Show comprehensive details for a selected ship contract, including all items in the contract (if it's a package).
    *   Display detailed ship attributes (hull, shield, armor, capacitor, speed, slots, bonuses, etc.) fetched from ESI `universe/types`.
    *   Provide information on how to find and accept the contract in-game (e.g., "Search for this contract under character [Issuer Name] in region [Region Name]").
*   **User Authentication (EVE SSO - Required for Core Value-Add Features):**
    *   Users MUST authenticate via EVE Online Single Sign-On (SSO) to access personalized features.
    *   **Core Authenticated Features:**
        *   **Saved Searches:** Allow users to save complex search criteria for ship contracts.
        *   **Watchlists:** Enable users to create and manage watchlists for specific ship types, price points, or other contract attributes.
        *   **Alerts/Notifications:** Provide configurable alerts (e.g., in-app, potentially email if user opts-in and provides an address) when contracts matching a user's watchlist criteria become available (e.g., a specific ship below a target price).
            *   *(Placeholder: Further detail notification mechanisms. This includes setting up SMTP integration for email alerts and investigating ESI API capabilities for sending in-game notifications, if any exist and are suitable.)*
    *   **Other Potential Authenticated Features (Low Hanging Fruit - to investigate further):**
        *   **Personalized Contract Feeds:** Options to prioritize contracts from user-defined favorite regions/stations or for recently viewed ship types.
        *   **Basic Issuer Context:** Optionally display public character age or corp/alliance affiliation for contract issuers (from ESI public data) – present neutrally as context, not endorsement.
        *   **Enhanced Contract Filtering:** Allow filtering for specific ship categories (e.g., Tech II Cruisers) or meta-levels.
        *   **Price Per Unit Display:** For contracts with multiple identical ships, show a calculated price per unit.
    *   **Optional Authenticated Features (Consider for future - more scope):**
        *   Ability to see their own public contracts highlighted or managed within Hangar Bay (would require `esi-characters.read_contracts.v1` scope).

*Considerations: Refer to Section 4 (Security) and the detailed `security-spec.md`, `accessibility-spec.md`, and `i18n-spec.md`. Secure handling of EVE SSO tokens is paramount. User data must be protected. All UI elements must be accessible and translatable. 

## 8. ESI API Integration Details
<!-- AI_NOTE_TO_HUMAN: For detailed, AI-parsable structures of ESI and Hangar Bay API endpoints, please refer to the 'API Endpoints Involved' section within individual feature specification documents (e.g., F001-*.md, F002-*.md). The feature specs will contain structured comment blocks like 'AI_ESI_API_ENDPOINT_START' and 'AI_HANGAR_BAY_API_ENDPOINT_START'. -->
<!-- AI_ADDITIONAL_GUIDANCE: These feature specifications now consistently begin with a "0. Authoritative ESI & EVE SSO References" section, providing direct links to official ESI/SSO documentation. Furthermore, all ESI, EVE SSO, and exposed Hangar Bay API endpoint definitions within these feature specs are accompanied by AI actionable checklists to guide implementation and ensure adherence to best practices and project standards. This structured approach is crucial for AI-assisted development. -->

Primary ESI endpoints for the public contract aggregator model:

*   **Public Contracts:**
    *   `GET /v1/contracts/public/{region_id}/` - To retrieve a list of public contracts in a given region. Paginated. Cache: 300 seconds (5 minutes).
*   **Contract Items:**
    *   `GET /v1/contracts/public/items/{contract_id}/` - To retrieve items included in a specific public contract. Paginated. Cache: 3600 seconds (1 hour).
*   **Ship/Item Types:**
    *   `GET /v3/universe/types/{type_id}/` - To get detailed information about a specific item/ship type, including dogma attributes and effects. Cache: Varies (often long, e.g., 1 day or more), uses ETag.
    *   `POST /v1/universe/ids/` - To resolve names to IDs (e.g., character names for issuers, type names for ships if searching by name). Cache: 3600 seconds (1 hour).
*   **Market Data (Supplementary):**
    *   `GET /v1/markets/prices/` - To get an overview of market prices for all item types. Cache: 3600 seconds (1 hour).
    *   `GET /v1/markets/regions/{region_id}/history/` - For historical market data for a type in a region (contextual). Cache: 3600 seconds (1 hour).
    *   `GET /v1/markets/structures/{structure_id}/` - If contracts are in player-owned structures, to get market orders (contextual). Requires auth if structure is private. Cache: 300 seconds.
*   **Search (Optional, for finding specific types or issuers):**
    *   `GET /v2/search/` - Search across various categories like solar systems, stations, item types, characters. Cache: 3600 seconds (1 hour).
*   **Authentication with EVE SSO (Optional for MVP):**
    *   If implemented, will use OAuth 2.0 flow as defined by EVE Developers.
    *   Scopes would be minimal, e.g., `publicData` for basic identification, or potentially `esi-characters.read_contracts.v1` if we wanted to let users see their *own* (even non-public) contracts, though this deviates from the public aggregator model for general users.
*   **Data Caching Strategy:**
    *   Strictly adhere to ESI `Cache-Control` and `ETag` headers.
    *   Implement local caching in Hangar Bay's backend/database to reduce ESI load and improve response times for users.
*   **Rate Limiting & Error Handling:**
    *   Implement robust error handling for ESI API responses (e.g., 4xx, 5xx errors).
    *   Respect ESI's error rate limiting (stop making requests if a certain error percentage is hit).
*   **User-Agent Policy:**
    *   Set a descriptive User-Agent string for all ESI requests as per ESI best practices.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. All ESI interactions must be secure (HTTPS). If SSO is used, token handling is paramount. Ensure any error messages or data passed to the frontend from this layer are structured to support accessible presentation (as per `accessibility-spec.md`) and internationalization (as per `i18n-spec.md`). ESI API calls for localized data (e.g., item names) should utilize the `language` parameter based on the user's selected locale, with appropriate fallbacks.* 

## 9. Database Schema (Initial Thoughts)

*(To be detailed)*

*   Tables for users (if local accounts exist alongside EVE SSO), ship types (cached from ESI), listings/contracts, etc.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. Data modeling should support accessibility requirements from `accessibility-spec.md` (e.g., storing full textual descriptions) and internationalization needs from `i18n-spec.md` (e.g., avoiding storage of translated UI strings directly in primary data tables, storing user language preferences).* 

## 10. UI/UX Considerations
<!-- AI_NOTE_TO_HUMAN: These are guiding principles. AI should aim to implement UI components and flows that adhere to these considerations. -->

*(To be detailed)*

*   **AI Action: Clarity and Intuitiveness:** Implement UI that is easy to understand and navigate, even for users unfamiliar with similar applications. Prioritize clear labeling and logical information hierarchy. Intuitive navigation is a key aspect of this.
*   **AI Action: Effective Data Presentation:** Ensure clear presentation of complex ship and market data. Use appropriate visualizations and summaries where helpful.

*   **AI Action: Responsive and Mobile-Friendly Design:** Ensure the application is usable and provides a good experience on various screen sizes (desktops, tablets, mobile phones).
    *   **AI Implementation Guidance:**
        *   **Leverage Angular's Capabilities:** Utilize Angular's features for responsive design, such as its component architecture, built-in directives, and integration with responsive grid systems (e.g., Angular Material's layout system, Bootstrap grid, or CSS Grid/Flexbox directly).
        *   **Fluid Layouts:** Employ fluid grids and flexible images/media that adapt to different viewport sizes. Use relative units (percentages, `em`, `rem`, `vw`, `vh`) and flexible containers to allow content to reflow gracefully.
        *   **Media Queries:** Use CSS media queries extensively to apply different styles and layouts based on screen characteristics.
        *   **Navigation:** Implement mobile-friendly navigation patterns (e.g., collapsible hamburger menus, off-canvas navigation, bottom navigation bars for key actions where appropriate).
        *   **Touch Interactions:** Ensure all interactive elements (buttons, links, form inputs) are adequately sized and spaced to be easily tappable on touchscreens. Avoid reliance on hover states for critical information disclosure.
        *   **Performance Optimization (Mobile):** Optimize assets (images, scripts, styles) for faster loading on mobile networks. Consider techniques like lazy loading for images and non-critical components.
        *   **Readability (Mobile & Desktop):** Ensure text is legible across all screen sizes with appropriate font sizes, line heights, and contrast ratios.
        *   **Accessibility (Mobile & Desktop):** Design and implement with accessibility in mind from the start. Adhere to WCAG 2.1 Level AA guidelines. Refer to `accessibility-spec.md` for detailed requirements and ensure Angular Material/CDK accessibility features are leveraged.
        *   **Progressive Enhancement/Graceful Degradation:** Design with a mobile-first approach or ensure graceful degradation so core functionality remains accessible on less capable devices or browsers.
        *   **Testing (Mobile):** Thoroughly test on various emulated mobile viewports (using browser developer tools) and, where possible, on a range of real mobile devices. (Refer to `test-spec.md` for detailed testing requirements).

*   **AI Action: Minimalism and Focus:** Design UIs that avoid clutter. Present only relevant information and actions to the user to maintain focus on the core tasks.
*   **AI Action: Performance and Responsiveness (General):** Ensure the application loads quickly and responds promptly to user interactions. Implement optimized data loading and rendering strategies. (See `performance-spec.md` for detailed guidance).
*   **AI Action: Consistency:** Maintain a consistent design language (colors, typography, layout, component behavior) throughout the application, leveraging Angular Material theming.
*   **AI Action: Error Handling and Feedback:** Implement clear, user-friendly error messages and feedback mechanisms for user actions (e.g., loading indicators, success/failure notifications using snackbars or toasts).
*   **AI Action: Trust and Security Cues:** Visually reinforce trust and security in the UI elements, especially around authentication and user data sections. Use iconography and language that conveys security.
*   **AI Action: Internationalization (i18n) Support:** Design UI components to be easily localizable. Ensure layouts can accommodate varying text lengths from different languages. Provide a clear mechanism for users to switch languages. All user-facing text must be externalized for translation. (Refer to `i18n-spec.md` for detailed guidance).

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. All UI components must be built with accessibility in mind (following `accessibility-spec.md`) and designed for internationalization (following `i18n-spec.md`).* 

## 11. Deployment

*(To be detailed further regarding specific CI/CD tools and hosting provider choices)*

*   **Containerization: Docker**
    *   The application (frontend and backend components) MUST be containerized using Docker. This ensures consistency across development, testing, and production environments and facilitates deployment to various hosting providers.
    *   Dockerfiles will be maintained for each service.
    *   Docker Compose will be used for local development orchestration.
*   **Hosting Agnosticism:** While a specific cloud provider (e.g., AWS, Azure, GCP) may be chosen for initial deployment, the containerized nature of the application should allow for migration to other providers or on-premise solutions if necessary, minimizing vendor lock-in.
*   **CI/CD Pipeline:** A continuous integration and continuous deployment (CI/CD) pipeline will be implemented (e.g., using GitHub Actions, GitLab CI, Jenkins) to automate testing, building, and deployment of container images.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. Secure container image management is crucial. CI/CD pipeline must have appropriate security controls. Accessibility of any user-facing deployment status pages or interfaces should also be considered (refer to `accessibility-spec.md`).* 

## 12. Testing

A comprehensive testing strategy is crucial for ensuring the quality, security, reliability, and usability of Hangar Bay.

*   **Detailed Specification:** A `test-spec.md` document is located in the `design` directory. It outlines the testing philosophy, types of tests (unit, integration, E2E, security, accessibility, performance, internationalization), tools, and CI/CD integration.
*   **Internationalization Testing:** Specific tests will be required to verify translations, locale-specific formatting, and UI adaptability across different languages. Refer to `i18n-spec.md` for i18n testing guidelines.
*   **AI Assistant Guidance:** AI coding assistants are expected to generate unit tests for new logic and assist in outlining integration and E2E tests, following the patterns in `test-spec.md` and considering test aspects from `i18n-spec.md`.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`.* 

## 13. MVP Scope and Deliverables

This section defines the scope for the Minimum Viable Product (MVP) of Hangar Bay. The MVP focuses on delivering the core functionality of discovering and viewing public ship contracts without requiring user authentication.

### 13.1. Core MVP Features (In Scope)

The following features, as detailed in their respective specification documents, constitute the core of the MVP:

*   **F001: Public Contract Aggregation & Display:** Automated fetching, processing, and storage of public ship contracts from EVE Online. (See `design/features/F001-Public-Contract-Aggregation-Display.md`)
*   **F002: Ship Browsing & Advanced Search/Filtering:** User interface for browsing, searching, and filtering the aggregated ship contracts. (See `design/features/F002-Ship-Browsing-Advanced-Search-Filtering.md`)
*   **F003: Detailed Ship Contract View:** Dedicated view displaying comprehensive details of a selected ship contract. (See `design/features/F003-Detailed-Ship-Contract-View.md`)

### 13.2. Post-MVP Features (Deferred)

The following features, while important for the long-term vision, are deferred beyond the initial MVP release. Their implementation typically depends on F004 (User Authentication).

*   **F004: User Authentication (EVE SSO):** (See `design/features/F004-User-Authentication-SSO.md`)
*   **F005: Saved Searches:** (See `design/features/F005-Saved-Searches.md`)
*   **F006: Watchlists:** (See `design/features/F006-Watchlists.md`)
*   **F007: Alerts/Notifications:** (See `design/features/F007-Alerts-Notifications.md`)

### 13.3. MVP Deliverables - Cross-Cutting Concerns

For the MVP, the following cross-cutting concerns will be addressed to the extent specified in their respective detailed documents, focusing on the implementation of F001, F002, and F003:

*   **Security:** Foundational security measures as per `security-spec.md` will be implemented for all MVP components (Frontend, Backend API, Database, ESI integration). This includes input validation, output encoding, secure ESI communication, and protection against common web vulnerabilities.
*   **Performance:** Core application performance for contract browsing, searching, and viewing will be optimized as per `performance-spec.md`. This includes efficient database queries, backend API response times, and frontend rendering for the MVP features.
*   **Accessibility (A11y):** The user interfaces for F002 and F003 will adhere to WCAG 2.1 Level AA guidelines as detailed in `accessibility-spec.md`.
*   **Internationalization (i18n):** The frontend (Angular) will be structured for internationalization using `@angular/localize` as per `i18n-spec.md`. English (en) will be the default and initially supported language for the MVP. The backend (FastAPI) will support locale negotiation for API responses where applicable (e.g., ESI data).
*   **Observability:** Basic logging (application events, errors) and health checks for backend services will be implemented as a foundation, guided by `observability-spec.md`.
*   **Testing:** Unit tests for critical backend and frontend logic for F001-F003 will be developed. Key API endpoints will have integration tests. End-to-end tests will cover core user flows for F002 and F003. All testing will follow `test-spec.md`.
*   **Deployment:** The application (Frontend and Backend) will be containerized using Docker. Basic deployment scripts or configurations for a chosen environment will be prepared.

*Considerations: All MVP development must adhere to the principles and requirements outlined in Section 4 (Security) and the referenced detailed specification documents for each cross-cutting concern.*

## 14. Accessibility (A11y)

Accessibility is a core requirement for Hangar Bay. The application MUST be designed and developed to be usable by people with a wide range of disabilities.

*   **Conformance Target:** WCAG 2.1 Level AA minimum. Aspire to Level AAA where feasible.
*   **Detailed Specification:** A comprehensive `accessibility-spec.md` document is located in the `design` directory. It outlines specific principles (POUR), technology-focused guidance (Angular), and testing requirements.
*   **Interaction with Internationalization:** Ensure that accessibility features (e.g., ARIA labels, `alt` text) are translatable and that the page's `lang` attribute is correctly set. Refer to `i18n-spec.md` for details on localizing accessible content.
*   **AI Assistant Guidance:** AI coding assistants MUST strictly adhere to the guidelines and patterns provided in `accessibility-spec.md` and `i18n-spec.md` when generating or modifying any frontend code or UI-related backend logic.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. All UI components must be built with accessibility in mind (following `accessibility-spec.md`) and designed for internationalization (following `i18n-spec.md`).*

## 15. Future Enhancements

*(To be detailed - some items moved to Core Features with SSO)*

*   Ship comparison tools.
*   Integration with other EVE Online tools/services (if APIs allow and align with Hangar Bay's focus).
*   Support for other high-value item types (e.g., capital ship modules, rare blueprints) if user demand exists.
*   Advanced market analytics based on aggregated contract data (e.g., price trends for specific ships within Hangar Bay's data).
*   More sophisticated notification channels or user-customizable notification settings.

*Considerations: Refer to Section 4 (Security) and the detailed `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, and `observability-spec.md`.* 
