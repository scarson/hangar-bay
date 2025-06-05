# Hangar Bay - EVE Online Ship Ecommerce Platform - Design Specification

## 1. Introduction

This document outlines the design specification for Hangar Bay, an e-commerce application for buying and selling ships within the video game EVE Online. The application aims to provide a secure, user-friendly platform for players to trade ships.

## 2. Goals

*   To create a secure and reliable platform for discovering EVE Online public ship contracts.
*   To provide an intuitive user interface for browsing, searching, and filtering public ship contracts.
*   To integrate seamlessly with the EVE Online ESI API for up-to-date contract, ship, and market information.
*   To help players efficiently find desirable ship contracts available in-game.
*   To ensure the application is accessible and usable by people with a wide range of abilities, adhering to WCAG 2.1 AA as a minimum (see `accessibility-spec.md`).

## 3. Target Audience

*   EVE Online players looking to find and acquire ships through public contracts.
*   EVE Online players who have listed ships on public contracts and want to see them (or for others to find them easily).
*   Players interested in current ship availability and pricing via public contracts.

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
*   **Secure Infrastructure:** The application must be deployed on a secure infrastructure with appropriate network security, logging, and monitoring. Refer to `security-spec.md`.
*   **Data Privacy:** Consideration must be given to any player data stored (e.g., EVE character ID, watchlists), ensuring it is minimized, protected, and handled according to privacy best practices. Refer to `security-spec.md`.
*   **Regular Security Audits:** Plan for regular security reviews and penetration testing.

**(All other sections should also reference Section 4: Security, and where appropriate, `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, `observability-spec.md`, and `design-log.md`.)* must include a reference to this Security section and, where applicable, to these detailed specifications, with instructions to consider them an integral part of their respective requirements.**

## 5. Application Architecture (High-Level)

*(To be detailed further)*

The application will function as an aggregator of public EVE Online contracts, focusing on ship sales. Transactions will occur in-game by players accepting these public contracts.

*   **Frontend:** (e.g., Web interface - React, Vue, Angular, Svelte, etc.) - Responsible for displaying contracts and search/filter UI.
*   **Backend:** (e.g., API - Python/Django/Flask, Node.js/Express, Java/Spring, Ruby/Rails, etc.) - Responsible for fetching data from ESI, processing, storing, and serving it to the frontend.
*   **Database:** (e.g., PostgreSQL, MySQL, MongoDB, etc.) - Stores aggregated contract data, ship details (cached from ESI), and potentially user preferences if SSO is implemented.
*   **EVE ESI API Integration Layer:** A dedicated module/service for interacting with the ESI API, handling requests for public contracts, contract items, ship details, caching, and error management.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. Accessibility, as outlined in `accessibility-spec.md`, should be considered for any user-facing outputs or interactions originating from this layer.* 

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

*Considerations: Refer to Section 4 (Security) and the detailed `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, and `observability-spec.md`. The security, accessibility, and testing best practices for each chosen technology will be strictly adhered to. This includes secure and accessible configuration, regular patching, and leveraging built-in mechanisms.* 

## 7. Core Features

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

*Considerations: Refer to Section 4 (Security) and the detailed `security-spec.md` and `accessibility-spec.md`. Secure handling of EVE SSO tokens is paramount. User data must be protected. All UI elements must be accessible. 

## 8. ESI API Integration Details

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

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. All ESI interactions must be secure (HTTPS). If SSO is used, token handling is paramount. Ensure any error messages or data passed to the frontend from this layer are structured to support accessible presentation, as guided by `accessibility-spec.md`.* 

## 9. Database Schema (Initial Thoughts)

*(To be detailed)*

*   Tables for users (if local accounts exist alongside EVE SSO), ship types (cached from ESI), listings/contracts, etc.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. Data modeling should support accessibility requirements from `accessibility-spec.md` (e.g., storing full textual descriptions where needed for screen readers, rather than just codes).* 

## 10. UI/UX Considerations

*(To be detailed)*

*   Intuitive navigation.
*   Clear presentation of complex ship and market data.
*   **Mobile-Friendly and Responsive Design (Core Requirement):** The application MUST provide an excellent user experience on a wide range of devices, including desktops, tablets, and mobile phones (both portrait and landscape orientations).
    *   **AI Implementation Guidance:**
        *   **Leverage Angular's Capabilities:** Utilize Angular's features for responsive design, such as its component architecture, built-in directives, and integration with responsive grid systems (e.g., Angular Material's layout system, Bootstrap grid, or CSS Grid/Flexbox directly).
        *   **Fluid Layouts:** Employ fluid grids and flexible images/media that adapt to different viewport sizes.
        *   **Media Queries:** Use CSS media queries extensively to apply different styles and layouts based on screen characteristics.
        *   **Navigation:** Implement mobile-friendly navigation patterns (e.g., collapsible hamburger menus, off-canvas navigation, bottom navigation bars for key actions where appropriate).
        *   **Touch Interactions:** Ensure all interactive elements (buttons, links, form inputs) are adequately sized and spaced to be easily tappable on touchscreens. Avoid reliance on hover states for critical information disclosure.
        *   **Performance Optimization:** Optimize assets (images, scripts, styles) for faster loading on mobile networks. Consider techniques like lazy loading for images and non-critical components.
        *   **Readability:** Ensure text is legible across all screen sizes with appropriate font sizes, line heights, and contrast ratios.
        *   **Accessibility (A11y):** Adherence to `accessibility-spec.md` (targeting WCAG 2.1 AA minimum) is a core requirement for all UI components and user experiences, across all devices and viewports. This includes, but is not limited to, semantic HTML, ARIA usage, keyboard navigation, focus management, and color contrast.
        *   **Progressive Enhancement/Graceful Degradation:** Design with a mobile-first approach or ensure graceful degradation so core functionality remains accessible on less capable devices or browsers.
        *   **Testing:** Thoroughly test on various emulated mobile viewports (using browser developer tools) and, where possible, on a range of real mobile devices. (Refer to `test-spec.md` for detailed testing requirements).
*   Emphasis on trust and security in the UI elements.

*Security Considerations: Refer to Section 4.* 

## 11. Deployment

*(To be detailed further regarding specific CI/CD tools and hosting provider choices)*

*   **Containerization: Docker**
    *   The application (frontend and backend components) MUST be containerized using Docker. This ensures consistency across development, testing, and production environments and facilitates deployment to various hosting providers.
    *   Dockerfiles will be maintained for each service.
    *   Docker Compose will be used for local development orchestration.
*   **Hosting Agnosticism:** While a specific cloud provider (e.g., AWS, Azure, GCP) may be chosen for initial deployment, the containerized nature of the application should allow for migration to other providers or on-premise solutions if necessary, minimizing vendor lock-in.
*   **CI/CD Pipeline:** A continuous integration and continuous deployment (CI/CD) pipeline will be implemented (e.g., using GitHub Actions, GitLab CI, Jenkins) to automate testing, building, and deployment of container images.

*Considerations: Refer to Section 4 (Security) and `security-spec.md`. Secure container image management is crucial. CI/CD pipeline must have appropriate security controls. Accessibility of any user-facing deployment status pages or interfaces should also be considered (refer to `accessibility-spec.md`).* 

## 12. Future Enhancements

*(To be detailed - some items moved to Core Features with SSO)*

*   Ship comparison tools.
*   Integration with other EVE Online tools/services (if APIs allow and align with Hangar Bay's focus).
*   Support for other high-value item types (e.g., capital ship modules, rare blueprints) if user demand exists.
*   Advanced market analytics based on aggregated contract data (e.g., price trends for specific ships within Hangar Bay's data).
*   More sophisticated notification channels or user-customizable notification settings.

*Considerations: Refer to Section 4 (Security) and the detailed `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, and `observability-spec.md`.* 
