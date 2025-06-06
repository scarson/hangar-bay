# Hangar Bay - Design Decision Log

This document records major design discussion points, considerations, and decisions made throughout the Hangar Bay project, in generally chronological order.

## Initial Phase: Understanding Requirements & ESI (Approx. 2025-06-04 20:00:00-05:00)

*   **Project Goal:** Design a secure e-commerce application for EVE Online ships ("Hangar Bay").
*   **Core Constraint:** Security is paramount due to the EVE Online player base's nature.
*   **Initial Research:** Reviewed EVE Online basics, economy, ships, and the ESI API.
    *   Key finding: ESI API is RESTful, uses SSO, and has cache timers.
    *   ESI Swagger specification reviewed for available endpoints.
*   **Transaction Model Discussion:**
    *   **Consideration:** Can Hangar Bay facilitate transactions directly via ESI?
    *   **ESI Finding:** ESI does *not* allow creating contracts via API.
    *   **Options Considered:**
        1.  Listing platform (manual in-game transactions, Hangar Bay verifies ownership via SSO + asset API).
        2.  Aggregator of public in-game contracts (Hangar Bay displays public contracts, users accept in-game).
    *   **Decision (Memory: d14b4bed): Hangar Bay will be an aggregator of public in-game contracts.**
        *   **Reasoning:** Leverages EVE's existing secure contract system, reducing Hangar Bay's direct involvement in sensitive transaction parts.

## Tech Stack & Core Features Refinement (Approx. 2025-06-04 23:00:00-05:00)

*   **EVE SSO for Value-Add Features:**
    *   **Initial thought:** SSO optional for MVP if just browsing public contracts.
    *   **User Feedback/Decision:** SSO to be a core requirement to enable features like saved searches, watchlists, and configurable alerts. This significantly enhances user value.
*   **Backend Framework Discussion:**
    *   **Options Considered:** Python (FastAPI, Flask) vs. Go.
    *   **FastAPI Pros:** Rapid development, async support, auto-docs, Python ecosystem.
    *   **Go Pros:** Raw performance, concurrency model, static typing.
    *   **Decision: Tentatively Python with FastAPI.**
        *   **Reasoning:** Good balance of performance (especially for I/O bound ESI calls with async) and development speed. User familiarity with C# makes Python's learning curve manageable, and FastAPI's type hints are helpful.
*   **ASGI Server for FastAPI:**
    *   **Initial Spec:** Uvicorn.
    *   **Discussion:** Uvicorn (direct), Hypercorn, Gunicorn with Uvicorn workers.
    *   **Decision: Uvicorn for development, Gunicorn with Uvicorn workers for production.**
        *   **Reasoning:** Gunicorn provides robust process management for production, leveraging Uvicorn's speed.
*   **Database:**
    *   **Options Considered:** PostgreSQL, SQLite for dev.
    *   **Decision: SQLite for development, PostgreSQL for production.**
        *   **Reasoning:** SQLite for ease of local dev, PostgreSQL for production robustness. An ORM (e.g., SQLAlchemy) will be used, designing schemas for PostgreSQL capabilities. No dev-to-prod data migration needed; prod schema populated fresh.
*   **Caching Layer:**
    *   **Options Considered:** Redis vs. Valkey (Redis fork).
    *   **Research:** Valkey is community-driven (Linux Foundation), API compatible with Redis 7.2.4 for core needs, open BSD license.
    *   **Decision: Valkey.**
        *   **Reasoning:** Sufficient for caching needs, aligns with open-source preference, good client library compatibility.
*   **Frontend Framework:**
    *   **Options Considered:** React, Vue.js, Angular.
    *   **Decision: Angular.**
        *   **Reasoning:** User interest in learning Angular, comprehensive framework, TypeScript for static typing (potential security/robustness benefits).
*   **Deployment:**
    *   **Decision: Application must be containerized (Docker).**
        *   **Reasoning:** Consistency across environments, hosting provider agnosticism, CI/CD integration.

## Specification Documents (Approx. 2025-06-05 00:30:00-05:00)

*   **`design-spec.txt`:** Main design document.
*   **`security-spec.md`:** Created for detailed security guidelines.
    *   **Initial Content:** TLS 1.2/1.3, Perfect Forward Secrecy, PQC aspiration, Encryption at Rest placeholder.
*   **`test-spec.md`:** Created for testing strategy.
*   **`design-log.md`:** This document, for chronological decision tracking.
*   **`observability-spec.md`:** Created for logging, metrics, tracing (distinct from security-specific logs).

## Feature Specification Management (Approx. 2025-06-05 01:46:46-05:00)

*   **Approach:** To facilitate focused development and clear requirements for the Windsurf coding assistant, individual features will be detailed in separate markdown files.
*   **Location:** These feature specifications will reside in the `design/features/` directory.
*   **Template:** A standardized template, `design/features/00-feature-spec-template.md`, has been created to ensure consistency and comprehensiveness across all feature specs.
    *   The template includes sections for overview, user stories, acceptance criteria, scope, data models, API interactions, workflow, UI/UX, error handling, security, performance, dependencies, and notes.
    *   It distinguishes between **Required** and **Optional** sections, with instructions to complete all required sections and evaluate optional ones for applicability.
*   **Process (Memory: e0009aae):** When creating a new feature spec, the `00-feature-spec-template.md` will be referenced. Required sections and applicable optional sections will be copied and filled with feature-specific details.

## Feature Specification Elaboration: F001, F002 & F003 (Approx. 2025-06-05 03:11:17-05:00)

*   **Focus:** Began detailed elaboration of feature specifications, starting with F001 (Public Contract Aggregation & Display), F002 (Ship Browsing & Advanced Search/Filtering), and then F003 (Detailed Ship Contract View).
*   **F001 (Public Contract Aggregation & Display) Initial Decisions:**
    *   **Data Storage:**
        *   `issuer_name`: Store directly (resolved once at ingestion).
        *   `start_location_name`: Resolve on display (via `start_location_id`).
        *   `esi_type_cache`: Store all `dogma_attributes` and `dogma_effects` (using SQLite JSON1 for dev, PostgreSQL JSONB for prod).
    *   **Error Handling:** For DB errors, implement retry with exponential backoff and jitter.
    *   **Configuration:** EVE regions to poll will be admin-configurable.
    *   **Contract Updates:** Handle updates to existing contracts (e.g., auction prices) via targeted re-fetches based on ESI cache timers and internal refresh intervals, not full re-scans.
*   **F002 (Ship Browsing & Advanced Search/Filtering) Initial Decisions:**
    *   **List View:**
        *   Added user story for basic contract details in list view.
        *   Defined initial fields: Ship Type, Quantity, Total Price, Contract Type, Location, Time Remaining, Issuer Name.
        *   Default sort order: Expiration date (soonest first).
    *   **Advanced Filtering:**
        *   Ship attributes (meta level, tech level): Plan to use `dogma_attributes` from `esi_type_cache`.
        *   Ship categories/groups: Source from ESI Market Groups, cache periodically, and expose via API.
*   **F003 (Detailed Ship Contract View) Decisions:**
    *   **Dogma Attributes Display:** A curated list of 'Key Ship Attributes' will be displayed prominently, with an option (e.g., 'All Attributes' toggle/tab) to view all others. Attributes to be grouped logically.
    *   **Handling Multiple Items:** Main focus on primary ship(s). An 'Additional Included Items' section will list other non-primary-ship items (Name and Quantity).
    *   **Image Server:** Use EVE Online's official image server (`https://images.evetech.net/`) for ship renders (e.g., `types/{type_id}/render?size=512`) and icons.
*   **Cross-Feature Consistency & Iterative Refinement:**
    *   Initial decisions for F001 and F002 were made. Subsequently, F003 was elaborated.
    *   Decisions and requirements from F003, along with F002's needs, prompted revisions to F001. F002 was also updated to note potential enhancements based on F001/F003 changes.
    *   **Updates to F001 (driven by F002 & F003):**
        *   Added `market_group_id` to `esi_type_cache` (for F002 category filtering).
        *   Clarified `contracts.title` usage (for F002 keyword search).
        *   Noted dependency on a separate `location_details_cache` (for F002 location name search).
        *   Added `contains_additional_items: BOOLEAN` to the `contracts` table schema (for F003 display of mixed contracts).
        *   Clarified that `esi_type_cache` population must cover all item types in processed contracts, not just primary ship items (for F003).
    *   **Updates to F002 (driven by F001/F003):**
        *   Noted potential use of the `contains_additional_items` flag (from F001, for F003) for UI indicators or filtering in the list view.
    *   **Rationale:** This iterative refinement ensures that feature specifications remain consistent and that dependencies between features are explicitly identified and addressed. This process is crucial for robust design, allowing insights from detailing one feature to inform and improve related features.

## Mobile-Friendly Design & Accessibility Specification (Approx. 2025-06-05 03:54:40-05:00)

*   **Context:** Recognizing the importance of broad usability and inclusivity for Hangar Bay.
*   **Mobile-Friendly Design (Core Requirement):
    *   **Decision:** The application MUST provide an excellent user experience on desktops, tablets, and mobile phones.
    *   **Action:** `design-spec.md` (Section 10: UI/UX Considerations) was updated with detailed guidance for AI-assisted development, emphasizing leveraging Angular's responsive capabilities, fluid layouts, media queries, mobile-friendly navigation, touch interactions, performance optimization, readability, and progressive enhancement.
    *   **Action:** `test-spec.md` (Sections 3.3, 3.5, 4) was updated to include requirements for testing responsive design across various viewports and devices, and to note tool considerations.
*   **Accessibility (A11y) Specification (Core Requirement):
    *   **Decision:** Accessibility is paramount. A dedicated specification, `accessibility-spec.md`, was created to define standards and provide actionable guidance for AI-assisted development.
    *   **`accessibility-spec.md` Content:**
        *   **Conformance Target:** WCAG 2.1 Level AA minimum, aspiring to AAA where feasible.
        *   **Principles:** Detailed elaboration on Perceivable, Operable, Understandable, Robust (POUR) principles with AI-specific guidance.
        *   **Technology Focus:** Specific guidance for Angular (Material/CDK, ARIA, focus management, `LiveAnnouncer`, forms).
        *   **Testing:** Requirements for automated tools (Axe-core, Lighthouse) and manual testing (keyboard, screen readers, zoom, contrast).
    *   **Action:** `design-spec.md` was updated to reference `accessibility-spec.md` in multiple relevant sections (Goals, Security, Tech Stack, Core Features, UI/UX, Deployment, Future Enhancements).
    *   **Action:** `test-spec.md` was updated to create a new "Accessibility Tests (A11y)" section (3.6) and integrate A11y testing into the overall philosophy, tools, CI/CD, and feature test planning.
*   **Rationale:** These updates ensure that mobile usability and comprehensive accessibility are foundational requirements, guiding development and testing to create a more inclusive and user-friendly application.


## AI-Friendly Specification Enhancements (Approx. 2025-06-05 04:58:23-05:00)

*   **Objective:** To improve the usefulness of project documentation for AI coding assistants, enabling more effective AI-assisted development while preserving human readability.
*   **Scope:** All major specification documents and the project README were reviewed and enhanced.
*   **Key Enhancements Made:**
    *   **`design/features/00-feature-spec-template.md`:** Added a new "AI Implementation Guidance" section with subsections for key libraries, critical logic points, data validation checklists, and AI testing focus. Introduced structured comment blocks for data models and API endpoints.
    *   **`design/design-spec.md`:** Added AI-focused notes in Tech Stack, Core Features, and ESI API Integration sections. Prefixed UI/UX considerations with `AI Action:` and added detailed AI guidance for UI/UX principles.
    *   **`design/security-spec.md`:** Added detailed `AI Actionable Checklist` and `AI Implementation Pattern` subsections to critical areas including TLS/HSTS, Encryption at Rest, EVE SSO, Input Validation/Output Encoding (FastAPI & Angular), Dependency Management, and Logging/Monitoring.
    *   **`design/accessibility-spec.md`:** Added `AI Actionable Checklist` and `AI Implementation Pattern` subsections to key areas based on POUR principles and Angular-specific guidance (Text Alternatives, Semantic HTML/ARIA, Distinguishable elements, Visible Focus, Navigation, Input Assistance, Name/Role/Value, Angular Material, Dynamic ARIA, Focus Management, LiveAnnouncer, Angular Forms A11y).
    *   **`design/test-spec.md`:** Added `AI Actionable Checklist` and `AI Implementation Pattern` subsections for Unit Tests (Backend & Frontend), Integration Tests (Backend), E2E Tests, Accessibility Tests (Automated & Manual), and Security Testing integration into CI/CD.
    *   **`design/observability-spec.md`:** Added `AI Implementation Pattern` and `AI Actionable Checklist` subsections for Logging (Structured Logging, Correlation IDs), Metrics (Backend & Frontend), Tracing (OpenTelemetry for FastAPI & Angular), and guidance for integrating with tooling (Logging, Metrics, Tracing, Error Tracking).
    *   **`README.md`:** Significantly expanded with an "AI Assistant Guidance" section, including a project overview for AI, how to use the AI-enhanced specifications, notes on key technologies with an AI focus, a suggested development workflow with AI, and best practices for AI prompts specific to Hangar Bay.
*   **Rationale:** These enhancements aim to provide explicit, structured, and actionable guidance to AI coding assistants, reducing ambiguity and improving the quality and relevance of AI-generated code. This should streamline the development process and help ensure that critical non-functional requirements (security, accessibility, testability, observability) are consistently addressed.


## Adoption of Core Security Principles (Approx. 2025-06-05 05:20:20-05:00)

*   **Context:** Further refining the security posture of Hangar Bay based on modern best practices.
*   **Decision:** Explicitly adopted and documented core security principles in `security-spec.md`.
*   **Key Principles Added:**
    *   **Assume Breach:** Operating with the mindset that compromises are inevitable, focusing on robust internal security, detection, and response.
    *   **Zero Trust Architecture (ZTA):** Not inherently trusting any entity, verifying explicitly, enforcing least privilege, and utilizing microsegmentation.
    *   **Defense in Depth:** Implementing multiple layers of security controls.
    *   **Security by Design:** Integrating security throughout the SDLC.
    *   **Data Minimization:** Collecting and retaining only necessary data.
*   **Impact on `security-spec.md`:**
    *   A new "Core Security Principles" section was added at the beginning of the document.
    *   The requirement for TLS encryption for backend-to-PostgreSQL connections was updated to mandate TLS always, explicitly aligning with Zero Trust principles, removing the previous condition of "if over a non-trusted network."
*   **Rationale:** Formalizing these principles provides a clear foundation for all security-related decisions and implementations, ensuring a proactive and resilient security posture. This directly influences practical measures like encrypting all internal traffic and rigorously applying least privilege.


## Collaboration Reflection & AI Prompting Guidance (Approx. 2025-06-05 05:47:21-05:00)

*   **Context:** User initiated a reflection on the collaboration process, requesting an honest assessment of their software engineering/design skills and feedback effectiveness to enhance our working relationship.
*   **Assessment Outcome:** The AI (Cascade) provided feedback highlighting the user's strong strategic vision, systematic approach to documentation, focus on AI collaboration, technical acumen, attention to detail, and clear communication. Recommendations for even more effective collaboration included continued specificity in prompts, elaborating on complex logic, breaking down large requests, and leveraging the project's AI-enhanced specifications.
*   **Decision & New Artifact:** Inspired by the feedback, the user requested the creation of a new document to capture best practices for crafting AI prompt instructions.
    *   **File Created:** `design/instruction-recs.md`
    *   **Purpose:** To provide clear, practical recommendations for human users on crafting effective prompt instructions for AI coding assistants, covering both general scenarios and specific considerations for the Hangar Bay project. It explicitly notes its primary utility is for human reference.
    *   **Content Basis:** The initial content for `instruction-recs.md` was derived from the AI's recommendations provided during the collaboration assessment.
*   **Rationale:** This exercise in reflection and the creation of `instruction-recs.md` aim to further optimize the human-AI collaboration for the Hangar Bay project, ensuring clarity and efficiency in communication and task execution.

## Internationalization Specification Integration (Approx. 2025-06-05 06:15:00-05:00)

*   **Context:** Following the creation of the comprehensive `design/i18n-spec.md`, the main `design/design-spec.md` required updates to fully integrate internationalization as a core project concern.
*   **Action:** `design-spec.md` was systematically updated to:
    *   Include i18n as a project goal.
    *   Note the global nature of the target audience.
    *   Incorporate i18n considerations and references to `i18n-spec.md` within relevant sections: Tech Stack, Core Features (especially EVE SSO and UI elements), ESI API Integration (for localized data), Database Schema (user preferences), UI/UX (translatable components, layout adaptability), Accessibility (translatable ARIA labels, `lang` attribute), and Testing (i18n test cases).
    *   Ensure the general "Considerations" notes at the end of relevant sections include a reference to `i18n-spec.md`.
*   **Rationale:** These updates ensure that internationalization is woven into the fabric of the Hangar Bay design, guiding AI-assisted development to build a globally ready application from the ground up.

*   **Further Integration (Approx. 2025-06-05 06:45:00-05:00):**
    *   **`accessibility-spec.md` Update:** Integrated i18n considerations, emphasizing translatable accessibility strings (e.g., `aria-label`, `alt` text), dynamic page `lang` attribute management, and layout adaptability for varying text lengths. Cross-referenced `i18n-spec.md`.
    *   **`test-spec.md` Update:** Added a dedicated section for "Internationalization (i18n) Tests," outlining scope (UI translation, layout, language switching, locale formatting, ESI language parameter, character encoding) and strategies (pseudo-localization, target language testing). Updated general feature test planning to explicitly include i18n test cases. Cross-referenced `i18n-spec.md`.
    *   **UI/UX Correction in `design-spec.md`:** Restored accidentally removed mobile-friendly and general UI/UX principles in Section 10, ensuring comprehensive guidance alongside i18n considerations.
    *   **Reinforced Rationale:** The EVE Online player base is global. Comprehensive internationalization, deeply integrated with accessibility and testing, is therefore not just a feature but a foundational requirement to serve this diverse audience effectively and provide an inclusive, high-quality user experience for all.

*(This log will be updated as more decisions are made. Remember to include approximate ISO 8601 timestamps in the format 'YYYY-MM-DD HH:MM:SSZ' (U.S. Central Time) for new major decision sections.)*
