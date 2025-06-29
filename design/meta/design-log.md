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
    *   **Reinforced Rationale:** The EVE Online player base is global. Comprehensive internationalization, deeply integrated

## Feature Specification Alignment (F001-F007) (Approx. 2025-06-06 02:59:35-05:00)

*   **Objective:** Systematically align all primary feature specifications (F001 through F007) with the updated feature specification template (`design/features/00-feature-spec-template.md`).
*   **Key Alignment Actions:**
    *   **Added "0. Authoritative ESI & EVE SSO References" Section:** This mandatory section was added to the beginning (after frontmatter) of `F001-Public-Contract-Aggregation-Display.md`, `F002-Ship-Browsing-Advanced-Search-Filtering.md`, `F003-Detailed-Ship-Contract-View.md`, `F004-User-Authentication-SSO.md`, `F005-Saved-Searches.md`, `F006-Watchlists.md`, and `F007-Alerts-Notifications.md`. This ensures consistent guidance for AI and developers regarding primary ESI/SSO documentation.
    *   **Added/Refined AI Actionable Checklists:**
        *   `F001-Public-Contract-Aggregation-Display.md`: AI actionable checklists were appended to all ESI API endpoint definitions.
        *   `F004-User-Authentication-SSO.md`: AI actionable checklists were appended to all consumed EVE SSO OAuth and ESI API endpoints.
        *   `F006-Watchlists.md`: The conditional ESI endpoint `GET /v3/universe/types/{type_id}/` was detailed, and an AI actionable checklist was added.
    *   **Verified Relative Paths:** Ensured that dependencies within these feature specifications continued to use relative markdown links, consistent with project standards.
    *   **Consistent API Block Usage:** Confirmed that exposed Hangar Bay API endpoints within these specs correctly utilized the `AI_HANGAR_BAY_API_ENDPOINT_START` and `AI_HANGAR_BAY_API_ENDPOINT_END` comment blocks.
*   **Rationale:** This comprehensive alignment enhances the clarity, consistency, and AI-friendliness of the core feature specifications, improving the accuracy of AI-assisted development and the quality of project documentation. It standardizes how ESI/SSO dependencies are referenced and how AI should approach their implementation. with accessibility and testing, is therefore not just a feature but a foundational requirement to serve this diverse audience effectively and provide an inclusive, high-quality user experience for all.

## Performance Specification Creation (Approx. 2025-06-06 01:05:00-05:00)

*   **Context:** The main `design-spec.md` identified a need for detailed performance considerations, initially placeholder-referenced as `(See performance-spec.md, to be created)`.
*   **Decision:** A dedicated `performance-spec.md` document was created to provide comprehensive guidance on performance targets, design principles, testing methodologies, and AI-specific implementation patterns for Hangar Bay.
*   **Rationale:** 
    *   Performance is a critical non-functional requirement for a responsive user experience, especially given interactions with ESI and potentially large datasets.
    *   A separate specification allows for focused and detailed treatment of performance aspects without cluttering other documents.
    *   It provides clear, centralized instructions for AI coding assistants to generate performant code by default and to consider performance implications throughout development.
    *   The spec covers backend (FastAPI, Valkey, PostgreSQL) and frontend (Angular) performance patterns, targets, testing tools, and common anti-patterns.
*   **Action:** `performance-spec.md` was created with a detailed structure. Cross-references and relevant guidance pointing to `performance-spec.md` were added to:
    *   `design-spec.md` (Section 4.3 Non-Functional Requirements and Section 10 UI/UX Considerations).
    *   `test-spec.md` (Section 3.4 Performance Tests).
    *   `observability-spec.md` (Sections 2.2 Metrics and 2.4 Error Tracking & Alerting).
    *   `design/features/00-feature-spec-template.md` (Section 11 Performance Considerations and Section 14 AI Implementation Guidance).
    *   The main `README.md` (AI Assistant Guidance section).


## Feature Index Creation and Maintenance Strategy (Approx. 2025-06-06 03:10:39-05:00)

*   **Context:** As the number of feature specifications grows, ensuring that AI coding assistants can reliably and quickly locate the correct specification document becomes crucial for efficient development and reducing errors. Relying solely on filename conventions or general search can be prone to ambiguity.
*   **Decision & New Artifact:** A dedicated feature index file, `design/features/feature-index.md`, was created.
    *   **Purpose:** To serve as a definitive, machine-readable index mapping Feature IDs (e.g., F001) to their full titles, current status, brief descriptions, and exact relative file paths (e.g., `./F001-Public-Contract-Aggregation-Display.md`).
    *   **Problem Solved:** This provides a structured and unambiguous way for AI assistants (like Cascade) to find specific feature specs, improving accuracy and speed. It also offers a quick human-readable overview of all features.
    *   **Initial Content:** The file was populated with existing features F001 through F007.
*   **Maintenance Strategy:** To ensure `feature-index.md` remains consistently up-to-date without requiring constant manual human intervention:
    *   **AI-Managed Process:** An AI-driven procedure has been established, documented in a persistent memory (ID: 8ab3f7a9-9f10-42c1-a282-b8ad6eefe5b6).
    *   **Trigger:** The AI (Cascade) will be prompted to check for necessary `feature-index.md` updates whenever a feature specification file (matching `F[0-9]{3}-*.md` in `design/features/`) is created or modified.
    *   **Action:** The AI will:
        1.  Read the affected feature spec(s) to extract key metadata (ID, Title, Status, Description, Path).
        2.  Read the current `feature-index.md`.
        3.  Compare and identify discrepancies (new features or changes to existing ones).
        4.  Propose specific changes to `feature-index.md` to the user for confirmation.
        5.  Upon user approval, apply the changes.
    *   **Rationale for Strategy:** This semi-automated approach balances the need for accuracy and up-to-date information with user oversight, ensuring the index remains a reliable tool for both AI and human developers. It leverages the AI's capability to process file changes and extract information, while retaining human control over the final content of the index.
*   **Related Memory:** The `feature-index.md` file itself is also noted in memory (ID: 894cb924-09d3-4293-b3d6-45d441d83616).

---

## AI System Procedure Documentation (Approx. 2025-06-06 03:25:07-05:00)

*   **Context:** Recognizing the critical importance of consistent and reliable execution of complex, recurring AI-involved operational patterns (like the newly defined procedure for maintaining `feature-index.md`). There's a need to document these procedures formally for transparency, maintainability, reusability, and continuous improvement.
*   **Decision & New Artifact:** A new documentation file, `design/ai-system-procedures.md`, has been created to serve as a central repository for these AI-centric operational procedures.
    *   **Type of Procedures Captured:** This file will document "AI System Procedures" (AISP). These are defined as significant, recurring operational patterns, protocols, or workflows designed for AI coding assistants (like Cascade) to execute or participate in. They typically involve a sequence of actions, decision points, and interactions with project artifacts or tools, often triggered by specific events.
    *   **Rationale for Recording:**
        *   **Consistency & Reliability:** Ensures AI assistants perform systemic tasks in a standardized and predictable manner.
        *   **Transparency & Auditability:** Provides a clear record of how and why certain automated/semi-automated tasks are performed.
        *   **Knowledge Transfer & Reusability:** Allows human team members to understand, refine, and potentially replicate these procedures in other projects or with different AI systems.
        *   **Evolution & Improvement:** Documented procedures are easier to review, critique, and improve over time.
        *   **Onboarding:** Helps new human team members or AI versions understand established operational patterns.
    *   **Structure and Templating of `ai-system-procedures.md`:**
        *   The file begins with an introductory AI guidance block explaining its purpose (primarily a design record and human reference).
        *   To promote consistency and guide the creation of new AISP entries, an `[AISP-000] AISP Entry Template` has been added at the beginning of the document. This template outlines the standard sections for an AISP and includes inline AI-readable comments detailing the expected content for each section, similar to the approach used for feature specification templates.
        *   Following the template, each documented procedure is assigned a unique ID (e.g., AISP-XXX) and adheres to the templated structure, including sections for: Problem Addressed, Rationale & Design Philosophy, Trigger Conditions, Detailed Steps for AI Execution, Expected Outcome, Supporting Implementation Details, Notes for Human Reviewers, and Version/Update information.
        *   **Benefits of Templating:** This approach is expected to ensure comprehensive and consistently structured documentation for all AI System Procedures, making them easier for AI assistants to understand, reference, and potentially assist in creating or updating. It also aids human readability and maintainability.
    *   **Initial Content:** The first procedure, `[AISP-001] Automated Maintenance of feature-index.md`, has been documented, detailing the process established in Memory `8ab3f7a9-9f10-42c1-a282-b8ad6eefe5b6`.
*   **Relationship to AI Memories:** While Cascade Memories will store the direct operational logic that the AI uses for execution, `ai-system-procedures.md` serves as the human-readable design specification and record for these procedures, explaining the broader context and intent.

---

## AI-Assisted Session Summary Logging (Approx. 2025-06-06 04:22:00-05:00)

*   **Context:** A need was identified to persistently capture the rich conversational context, key decisions, and rationale from AI-User interaction sessions within the project itself, beyond what is typically recorded in specification documents or commit messages.
*   **Decision & New Artifacts/Procedures:**
    *   A new log file, `design/cascade-log.md`, has been created. This file will store AI-generated summaries of interaction sessions, focusing on verbose and detailed accounts of the work performed, decisions made, and their underlying rationale.
    *   A new AI System Procedure, `[AISP-002] AI-Assisted Session Summary Logging`, has been documented in `design/ai-system-procedures.md`. This procedure formalizes the process for the AI (Cascade) to:
        1.  Understand a USER request to log a session.
        2.  Review the relevant conversational context.
        3.  Draft a detailed summary in Markdown format, including a timestamp.
        4.  Optionally present the summary to the USER for review.
        5.  Append the finalized summary to `design/cascade-log.md`.
    *   **Rationale for Strategy:** This approach aims to create a valuable, project-internal historical record. It leverages the AI's ability to synthesize information while keeping the USER in control of when logging occurs and the final content. The emphasis on detailed, verbose summaries is intended to maximize the contextual information retained.
*   **Next Steps:** An operational Cascade Memory will be created based on AISP-002 to enable the AI to perform this logging task upon USER request.

---

## Refinement of AISP-002: Proactive AI-Assisted Session Logging (Approx. 2025-06-06 04:47:00-05:00)

*   **Context:** Following the initial creation of `[AISP-002] AI-Assisted Session Summary Logging`, a need was identified to make the process more proactive, automated, and robust, reducing reliance on explicit USER commands for logging and improving the reliability of appending to `design/cascade-log.md`.
*   **Decisions & Enhancements (AISP-002 v1.1):**
    *   **Proactive AI Trigger:** AISP-002 was updated to instruct the AI (Cascade) to proactively identify significant, non-trivial blocks of work (e.g., new file creation, complex edits, bug fixes, design decisions) and propose logging a session summary to the USER.
    *   **Exclusion Criteria for Trivial Actions:** The procedure now explicitly excludes minor edits, routine Git operations, simple views/searches, and routine tests from triggering logging proposals to avoid unnecessary interruptions.
    *   **Robust Append Logic:** A consistent footer (`--- \n\n*(End of Cascade Interaction Log. New entries are appended above this line.)*`) was established in `design/cascade-log.md`, and AISP-002 was updated to use this footer as a reliable marker for appending new summaries.
    *   **Error Handling:** Basic error handling for append failures was incorporated into the procedure, with instructions for the AI to inform the USER and suggest alternatives.
    *   **Operational Memory Update:** Cascade's internal operational memory (ID: `42c9fb61-0933-428f-ad56-16e1f846afcf`) was updated to reflect these changes, ensuring its behavior aligns with AISP-002 v1.1.
    *   **Documentation Order:** AISP-002 was correctly reordered in `design/ai-system-procedures.md` to maintain numerical sequence.
*   **Rationale for Enhancements:** These changes aim to increase the utility and consistency of `cascade-log.md` by making the logging process more autonomous yet still USER-confirmed. The goal is to capture valuable contextual information more regularly and reliably, enhancing project history and future recall, while minimizing USER overhead.
*   **Next Steps:** Begin operational use of the enhanced AISP-002. Monitor the frequency and relevance of AI-initiated logging proposals and provide feedback to further refine the heuristics for identifying "non-trivial" interactions. Regularly commit `cascade-log.md`.

---

## Project Resource Review for MVP Readiness (Approx. 2025-06-06)

*   **Purpose:** To conduct a comprehensive review and refinement of all Hangar Bay project documentation, including feature specifications (F001-F007), the main design specification, supporting documents (e.g., `security-spec.md`, `accessibility-spec.md`, `i18n-spec.md`, `performance-spec.md`, `test-spec.md`, `observability-spec.md`), and procedural documents (e.g., `ai-system-procedures.md`, `cascade-log.md`). The goal was to ensure all resources are up-to-date, consistent, sufficiently detailed, and "AI-ready" to support efficient and accurate MVP development.
*   **Importance:**
    *   **Clarity and Reduced Ambiguity:** Provides clear, unambiguous requirements and design details for both human developers and AI coding assistants, minimizing misunderstandings and rework.
    *   **MVP Scope Alignment:** Confirms that all documented features and their specifications are aligned with the defined MVP scope (F001-F003 for implementation, F004-F007 refined for future work).
    *   **Solid Foundation:** Establishes a robust and reliable information baseline for the implementation, testing, and future iteration phases of the project.
    *   **Efficient Onboarding:** Facilitates smoother and faster onboarding for any new team members or AI assistant instances joining the project.
    *   **Traceability:** Ensures that design decisions, feature refinements, and procedural updates are well-documented and traceable.
*   **Process & Key Activities Undertaken:**
    *   **Systematic Review of Feature Specifications (F001-F007):** Each feature specification document was reviewed.
        *   Titles, descriptions, and statuses were updated in `design/features/feature-index.md` to "Refined" for all seven features.
    *   **Detailed Refinement of F004-F007:**
        *   **F004 (User Authentication - EVE SSO):** Clarified ESI scope policy (no scopes for F004 itself), ID token JWT validation, refresh token failure handling, session duration, CharacterOwnerHash update logic, and security of 'next' URL parameter.
        *   **F005 (Saved Searches):** Confirmed MVP scope (create, rename, delete, execute; no criteria updates post-MVP), enforced unique names, and added notes on UI truncation and handling of invalid filter options.
        *   **F006 (Watchlists):** Clarified `type_id` validation (must be a ship type), confirmed `(user_id, type_id)` uniqueness, noted live market data is out of scope for F006 (handled by F007), and added an optional `notes` field.
        *   **F007 (Alerts/Notifications):** Focused MVP on in-app notifications for watchlist matches, defined de-duplication rules, enhanced notification message content (including contract type), and refined data models for `notifications` and `user_notification_settings`.
    *   **Cross-Cutting Concerns Integration:** Ensured that all feature specifications adequately referenced or integrated considerations from dedicated documents for security, accessibility, internationalization, performance, testing, and observability.
    *   **Documentation Updates:**
        *   `cascade-log.md` was updated with detailed session summaries for the refinements of F004, F005, F006, and F007.
        *   Relevant AI System Procedures (e.g., AISP-001, AISP-002) were followed for documentation updates and logging.
*   **Practical Improvements & Outcomes:**
    *   **Enhanced Clarity & Precision:** All reviewed feature specifications (F001-F007) are now clearer, more precise, and internally consistent.
    *   **Accurate Feature Index:** `design/features/feature-index.md` accurately reflects the current "Refined" status and details of all defined features.
    *   **Resolved Ambiguities:** Key open questions and ambiguities within F004-F007 were addressed and resolved.
    *   **Improved AI-Readiness:** The documentation suite is better structured and detailed, enhancing its utility for AI-assisted development.
    *   **MVP Readiness Confirmation:** This comprehensive review confirms that project documentation and feature specifications are in a mature state, providing a solid foundation for proceeding with MVP development (F001-F003) and for the subsequent implementation of deferred features (F004-F007).
*   **Rationale:** This dedicated review and refinement phase was critical to consolidate all previous design work, ensure a high level of quality and consistency in project resources, and explicitly prepare the project for the transition into active MVP development. It serves as a key milestone, marking the conclusion of the intensive initial design and specification phase.

---

## AI-Focused MVP Implementation Plan Conceptualization (Approx. 2025-06-06 07:24)

{{ ... }}
*   **Objective:** To conceptualize and initiate a detailed, AI-friendly MVP implementation plan for Hangar Bay, guiding development of features F001-F003.
*   **Core Rationale for AI-Centric Plan:**
    *   **Enhanced Clarity & Precision:** Provide explicit, step-by-step tasks to minimize AI ambiguity.
    *   **Rich Contextual Grounding:** Link tasks directly to feature specs (F001-F003), design documents (`design-spec.md`, etc.), and specific sections/data models to give AI deep understanding.
    *   **Embedded AI Guidance:** Include structured prompts and "AI Implementation Guidance" within each task file.
    *   **Systematic Progression:** Ensure logical task ordering, manage dependencies, and integrate testability considerations from the start.
    *   **Living Documentation:** The plan itself serves as a persistent, detailed record of the MVP construction process.
*   **MVP Scope Covered:** The plan initially targets F001 (Public Contract Aggregation & Display), F002 (Ship Browsing & Advanced Search/Filtering), and F003 (Detailed Ship Contract View), which do not require user authentication (F004) for their MVP functionality.
*   **Phased Structure Adopted:**
    *   **Phase 0: Foundational Setup:** Covers project initialization, tooling (linters, formatters), dependency management (`requirements.txt`, `package.json`), version control (`.gitignore`), and initial `README.md` updates. Includes configuration management setup (Pydantic Settings, Angular environment files).
    *   **Phase 1: Backend Core Infrastructure:** Establishes the FastAPI application skeleton, database setup (PostgreSQL with Alembic for migrations, SQLite for dev), and Valkey caching layer integration.
    *   **Phase 2: Backend - F001: Public Contract Aggregation:** Develops the ESI API client for public endpoints, defines SQLAlchemy models for F001 data (contracts, items, type cache, etc.), implements the background aggregation service, and creates initial API endpoints for basic contract listing.
    *   **Phase 3: Frontend Core Infrastructure:** Sets up the Angular application skeleton, creates a backend API service layer in Angular, and implements the basic application layout, routing, and navigation.
    *   **Phase 4: Frontend - F001/F002: Contract Listing & Basic Filtering:** Develops the Angular component for displaying the contract list (F001) and implements UI elements for basic filtering (initial F002).
    *   **Phase 5: Backend - F002: Advanced Search & Filtering Logic:** Enhances backend query capabilities to support advanced filters defined in F002 and updates API endpoints accordingly.
    *   **Phase 6: Frontend - F002: Advanced Filtering Implementation:** Develops the Angular component for the advanced search/filter interface and integrates it with the backend.
    *   **Phase 7: Backend - F003: Detailed Ship/Contract View:** Creates API endpoint(s) to serve detailed information for a specific contract, including items and ship attributes, as per F003.
    *   **Phase 8: Frontend - F003: Detailed View Implementation:** Develops the Angular component to display the detailed contract view.
    *   **Phase 9: Cross-Cutting Concerns (Integrated Throughout & Finalized):** Addresses security hardening (MVP scope), logging and basic observability, testing (unit and basic E2E), and foundational accessibility & i18n stubs.
    *   **Phase 10: Deployment:** Covers Dockerization of backend and frontend applications and setting up a basic CI/CD pipeline.
*   **Process:**
    *   Created an overview document: `plans/implementation/00-mvp-implementation-plan-overview.md`.
    *   Began populating detailed task files (e.g., `00.1-project-initialization-tooling.md`, `00.2-configuration-management.md`) within a hierarchical structure (`plans/implementation/phase-XX-phase-name/YY.Z-task-name.md`).
*   **Significance:** This structured, AI-focused plan aims to streamline MVP development by providing unparalleled clarity, context, and actionable guidance for AI coding assistants and human developers alike.

---

---
date: 2025-06-06
author: Cascade (AI Assistant), Sam (User)
status: Decided
---

**Decision: Proactive Integration of Cross-Cutting Concerns into All MVP Tasks**

**Context:**
A critical review of the MVP implementation plan revealed that while Phase 09 detailed tasks for cross-cutting concerns (Security, Observability, Testing, Accessibility, i18n), these were not explicitly integrated into earlier feature development phases (00-08). This risked them being treated as afterthoughts, leading to potential rework and deficiencies.

**Proposals Considered:**
1.  Modify all existing task files with explicit NFR checklists.
2.  Create new "gate" sub-tasks for NFRs per feature task.
3.  Leverage Cascade's AI memory system for implicit NFR prioritization.
4.  Add a global reminder in the overview plan.
5.  Hybrid: Combine AI memories, a standardized NFR checklist in each task, and a global reminder.

**Decision:**
The **Hybrid Approach (Proposal 5)** was adopted. This involves:
1.  **Strong AI Memories:** Instilling in Cascade the requirement to always consider the five core cross-cutting concern specifications (`security-spec.md`, `observability-spec.md`, `test-spec.md`, `accessibility-spec.md`, `i18n-spec.md`) as primary inputs for all tasks. (Memories created).
2.  **Standardized "Cross-Cutting Concerns Review" Section:** Adding a mandatory checklist to each task file in Phases 00-08. This checklist requires Cascade to document how each concern was addressed for that specific task.
3.  **Global Reinforcement in `00-mvp-implementation-plan-overview.md`:** Adding a note to the overview plan explaining this integrated approach.

**Rationale:**
This multi-layered strategy ensures that critical non-functional requirements are not deferred but are an integral part of Cascade's workflow for every task. It combines direct AI behavioral influence (memories) with explicit, verifiable action items within each task (checklists), providing a robust framework for building a high-quality, secure, and maintainable application from the outset.

**Impact:**
All task files in Phases 00-08 will be updated. Cascade's operational procedures for task execution will now include completing the "Cross-Cutting Concerns Review" section. The `00-mvp-implementation-plan-overview.md` will be updated to reflect this process.

---

## Completion of MVP Implementation Task File Creation (2025-06-06)

**Decision/Event:** All detailed task files for the Hangar Bay MVP Implementation Plan (Phases 00 through 10) have been successfully created and committed to the repository. This includes tasks covering foundational setup, backend core infrastructure, frontend core infrastructure, features F001, F002, F003 (backend and frontend aspects), cross-cutting concerns (security, logging, testing, accessibility, i18n), and deployment/documentation.

**Rationale:** This completes a significant milestone in project planning, providing a comprehensive, actionable breakdown of work required for the MVP. These detailed task files, complete with AI implementation guidance, will facilitate both AI-assisted and human-driven development workflows.

**Affected Components:**
*   `plans/implementation/` (all subdirectories and files)

---

## MVP Implementation Strategy & Initial Plan (Approx. 2025-06-06 11:16:57-05:00)

*   **Decision:** Adopted **Proposal A: Foundational Setup & Backend Core First** for Hangar Bay MVP implementation.
    *   **Rationale:** Prioritizes building a robust foundation, allows early backend API stabilization, effectively utilizes AI for boilerplate, and systematically integrates cross-cutting concerns.
*   **Directory Structure Update:** Application code will reside in `app/backend` and `app/frontend` subdirectories within the project root.
*   **Initial Focus (Phases 00 & 01):**
    *   **Phase 00:** Project initialization, tooling (linters, formatters, pre-commit hooks), configuration management.
    *   **Phase 01 (Backend):** FastAPI application skeleton, database setup (SQLAlchemy, Alembic, SQLite/PostgreSQL), Valkey cache integration.
*   **Next Step:** Begin implementation of Phase 00, Task 00.1 (Project Initialization & Tooling Setup).

---

## Frontend Project Structure (Approx. 2025-06-06 11:52:00-05:00)

*   **Context:** Discussed the Angular project initialization path within `app/frontend/`.
*   **Options Considered:**
    1.  `app/frontend/hangar-bay-frontend/` (Angular CLI default, project name creates a subfolder).
    2.  `app/frontend/` (Angular project files directly in `app/frontend/`, using `ng new hangar-bay-frontend --directory .`).
    3.  `app/frontend/angular/` (Angular project files directly in a dedicated `angular` subfolder, using `ng new hangar-bay-frontend --directory .` from within `app/frontend/angular/`).
*   **Decision: The Angular project will be initialized in `app/frontend/angular/`.**
    *   **Reasoning:** This approach provides a clear separation if other frontend technologies or distinct frontend micro-applications are introduced later under `app/frontend/`. It addresses concerns about path redundancy (e.g., `app/frontend/hangar-bay-frontend/hangar-bay-frontend`) while clearly indicating the technology in use via the `angular/` directory. The Angular project's internal name will remain `hangar-bay-frontend`.
    *   **Action:** The user created the `app/frontend/angular/` directory. The `ng new` command will be executed within this directory using the `--directory .` flag.

---

## Angular Project Initialization Options (Approx. 2025-06-07 16:23:00-05:00)

*   **Context:** During Angular project initialization (`ng new hangar-bay-frontend --directory . --routing --style=scss`), decisions were made regarding advanced setup options prompted by the Angular CLI.
*   **Zoneless Application:**
    *   **Prompt:** "Do you want to create a 'zoneless' application without zone.js (Developer Preview)? (y/N)"
    *   **Decision: No.**
    *   **Reasoning:** For the MVP and learning purposes, the traditional `zone.js` approach for change detection is preferred due to its stability, wider community support, and simpler learning curve. Zoneless is a developer preview and adds complexity.
*   **Server-Side Rendering (SSR) / Static Site Generation (SSG):**
    *   **Prompt:** "Do you want to enable Server-Side Rendering (SSR) and Static Site Generation (SSG/Prerendering)? (y/N)"
    *   **Decision: No.**
    *   **Reasoning:** Client-side rendering (CSR) is simpler for the MVP. Hangar Bay's content is largely dynamic and often behind authentication, reducing the immediate SEO benefits of SSR/SSG. SSR/SSG add development and deployment complexity. Angular Universal can be added later if SEO for public contract listings or other performance needs arise.

---

**Date:** 2025-06-07
**Authors:** USER, Cascade
**Status:** Decided

### Subject: Strategy for Tracking MVP Implementation Progress for AI-Assisted Development

**Context:**
The Hangar Bay MVP implementation plan spans multiple phases and numerous individual tasks. A concern was raised regarding the potential for AI coding assistants (like Cascade) to lose context or de-prioritize details from earlier completed tasks as the project progresses. This is a known challenge with the limited context window and evolving memory of large language models. Relying solely on conversational history or internal AI memory might be insufficient for a project of this scale and duration.

**Problem:**
How can we effectively and persistently track implementation progress in a way that is most beneficial for an AI coding assistant, ensuring it can reliably access and utilize information about previously completed work to inform current and future tasks?

**Proposals Considered:**
1.  **Dedicated Progress File (`plans/implementation/00-mvp-implementation-plan-progress.md`):** A Markdown file mirroring the `00-mvp-implementation-plan-overview.md` structure. As tasks are completed, AI-friendly summaries (key artifacts, paths, configurations, commit IDs) are added under each task. (Chosen)
2.  **Task-Specific Completion Notes:** Appending summaries directly within each individual task plan file. (Considered less centralized for AI overview).
3.  **Purely AI Internal Memory:** Relying solely on Cascade's built-in memory creation. (Considered less transparent and potentially less reliable for very specific, older details).
4.  **Git Commit History as Primary Log:** Using detailed commit messages. (Considered less structured for AI to quickly synthesize overall task outcomes).

**Decision:**
Proposal 1 was adopted. The file `plans/implementation/00-mvp-implementation-plan-progress.md` was created.

**Rationale:**
This approach was chosen because:
*   **Persistent & Centralized Ground Truth:** It provides a single, stable, and structured document that Cascade can be reliably directed to for information about completed tasks.
*   **AI-Friendly Content:** Summaries are tailored for AI consumption, focusing on factual data points like file paths, key configurations, commands used, and references to other design documents or commit IDs. This is more effective than narrative summaries.
*   **Complements AI Memory:** This external knowledge base will augment Cascade's internal memory. Cascade can be prompted to review relevant sections of this file to "refresh" its context before starting new tasks, or when needing to recall specific details from past work.
*   **Transparency & Verifiability:** Allows human developers to easily review and verify the AI's understanding of completed work.
*   **Mitigates Context Window Limitations:** By having a persistent external reference, the AI is less susceptible to losing details from tasks completed much earlier in the development cycle.

**Cascade's Usage Plan:**
Cascade will:
1.  Be informed of the existence and purpose of `00-mvp-implementation-plan-progress.md`.
2.  Be prompted by the USER (or proactively suggest) to update this file with a summary after each significant task or sub-task completion.
3.  Be directed by the USER (or proactively decide) to review relevant sections of this file when:
    *   Starting a new task that builds upon or relates to previously completed work.
    *   Needing to recall specific configurations, file paths, or decisions from past tasks.
    *   Generating summaries or reports that require historical context.
4.  Use the structured, factual information in the summaries to more accurately inform its code generation, analysis, and decision-making processes.

This strategy aims to ensure consistent, context-aware AI assistance throughout the Hangar Bay MVP development.

---

### Design Decision - 2025-06-07 21:24:44-05:00 - Topic: Backend Directory Structure Finalized

The following directory structure was adopted for `app/backend/`:

```text
app/
└── backend/
    ├── .venv/                  # Virtual environment for the backend (gitignored)
    ├── docker/                 # Docker-specific files for the backend
    │   └── Dockerfile          # Example
    ├── src/                    # Python source code for the backend
    │   ├── __init__.py         # Makes 'src' a package
    │   └── fastapi_app/      # Your FastAPI application package
    │       ├── __init__.py     # Makes 'fastapi_app' a sub-package
    │       ├── main.py         # FastAPI app instance
    │       ├── config.py       # Pydantic settings
    │       ├── routers/        # Directory for API routers
    │       ├── models/         # Directory for Pydantic models or SQLAlchemy models
    │       └── services/       # Directory for business logic
    ├── __init__.py             # Makes 'backend' a package (useful if app/ is a project root)
    ├── requirements.txt        # Python dependencies for the backend
    └── tests/                  # Tests for the backend (often outside src)
```

**Rationale:** To establish a clear, maintainable, and scalable structure for the FastAPI backend, aligning with Python best practices and facilitating organized development.

**Impact:** Provides a foundational layout for all backend code, configuration, and related artifacts, improving developer onboarding and code navigability.


---
### Design Decision - 2025-06-07 21:40:34-05:00 - Topic: Comprehensive Secure Secret Management Strategy and Implementation

**Context:** A review of the backend configuration (`app/backend/src/fastapi/config.py`) highlighted that parameters like `DATABASE_URL`, `ESI_CLIENT_ID`, and `ESI_CLIENT_SECRET`, while intended to be loaded from environment variables, could inadvertently lead to developers hardcoding secrets locally or misunderstanding production secret handling if not explicitly addressed.

**Core Problem:** Storing plaintext secrets directly in code, committed configuration files, or any version-controlled artifact poses a significant security risk. This practice contravenes established security principles and industry best practices, such as those outlined by OWASP (e.g., OWASP Top 10 A05:2021 - Security Misconfiguration, which includes improper secrets management) and guidance from organizations like NIST and SANS. These standards strongly advocate for externalized secret management and advise against hardcoding secrets.

**Decision & Rationale:** To proactively address these risks and establish a robust secret management framework for Hangar Bay, a multi-faceted approach was adopted:

1.  **Principle Adoption:** The core principle is that secrets MUST NOT be hardcoded. For local development, secrets will be loaded from environment variables, typically populated via `.env` files. For staging/production, secrets MUST be injected into the environment through secure platform mechanisms or a dedicated secrets management service.

2.  **Security Specification Update (`design/security-spec.md`):**
    *   A new subsection, `1.4. Secure Secret Storage and Management`, was added to `design/security-spec.md`. This section explicitly prohibits plaintext secrets in code or version control, details the risks, and outlines recommended practices including the use of environment variables, `.env` files (gitignored) for local development, and dedicated secrets management services for production environments.
    *   It provides actionable checklists for AI and human developers to verify compliance.

3.  **`.gitignore` Enhancement:**
    *   The root `.gitignore` file was reviewed and updated to explicitly include `app/backend/.env`. This ensures that local development environment files containing actual secrets are never accidentally committed to version control, complementing the general `.env` ignore rule.

4.  **Planning Document Integration:**
    *   The task plan `plans/implementation/phase-09-cross-cutting-concerns-mvp-scope/09.1-security-hardening-mvp.md` was updated. Its 'Secrets Management Review' checklist now directly references `security-spec.md#1.4` and includes more specific verification steps (e.g., checking for no plaintext secrets in code, ensuring `.env` files are gitignored).
    *   The task plan `plans/implementation/phase-00-foundational-setup/00.1-project-initialization-tooling.md` was updated in its 'Cross-Cutting Concerns Review' section for 'Secrets Management'. It now mandates adherence to `security-spec.md#1.4` from the project's outset, including correct `.gitignore` setup.

5.  **AI Operational Memory Creation:**
    *   A new persistent memory (ID: `82552343-47c2-4a12-8ff7-9503cbe70bf5`), titled "Secure Secret Management Adherence (security-spec.md#1.4)", was created. This memory instructs AI assistants (like Cascade) to ensure that all 'Secrets Management' checklist items within any task file's 'Cross-Cutting Concerns Review' section are handled in strict alignment with `design/security-spec.md#1.4`.

**Impact:** These comprehensive updates significantly strengthen Hangar Bay's security posture by:
*   Establishing clear, documented policies against insecure secret handling.
*   Integrating these policies directly into actionable development plans and checklists.
*   Providing ongoing guidance for AI-assisted development to maintain these security standards.
*   Reducing the risk of accidental secret exposure through version control or insecure configurations.

This proactive approach ensures that secure secret management is a foundational aspect of the Hangar Bay project, from initial development through to production deployment.
---

---
**2025-06-07: Created AI Memory for Standardized Cross-Cutting Concerns (CCC) Review Procedure**

*   **Why:** To ensure consistent, thorough, and verifiable AI-assisted completion of the "Cross-Cutting Concerns Review" section in Hangar Bay task files. This procedure aims to improve the rigor with which the five key CCCs (Security, Observability, Testing, Accessibility, Internationalization) are evaluated against project specifications and standards during task execution. It enhances the reliability of these critical reviews and provides a clear framework for the AI.

*   **How:**
    *   A new AI Memory (ID: `0c495baf-94e6-4dfa-81c1-a386d94c813e`) titled "Procedure: AI-Assisted Cross-Cutting Concerns (CCC) Review" was defined and created.
    *   This memory outlines a detailed, step-by-step process for the AI (Cascade) to:
        1.  Locate the CCC section in a task file.
        2.  Iterate through each of the five major concerns.
        3.  For each concern, recall and consult its primary specification document (e.g., `design/security-spec.md`) and other relevant memories.
        4.  Analyze the specific task's context against the principles of the concern.
        5.  Address each sub-item in the standard CCC checklist.
        6.  Populate the "Notes" section with details of actions taken, rationale, or justifications.
        7.  Ensure overall completeness and consistency.
        8.  Collaborate with the USER by presenting the drafted review for feedback.
    *   The new memory explicitly lists the paths to the five core CCC specification documents (`design/security-spec.md`, `design/observability-spec.md`, `design/test-spec.md`, `design/accessibility-spec.md`, `design/i18n-spec.md`).
    *   The memory was indexed in `design/memory-index.md` (see entry for `0c495baf-94e6-4dfa-81c1-a386d94c813e`).
    *   The creation and full content of this memory, along with its justification for effectiveness, were logged in `design/cascade-log.md` (entry dated 2025-06-07).

*   **Impact:** This procedural memory is expected to significantly improve the quality and consistency of AI contributions to Cross-Cutting Concerns reviews, making them more systematic and aligned with project standards. It provides a clear operational guide for Cascade when performing these reviews.

---

---
**2025-06-07: Adopted Practice of Pinning Python Dependencies in `app/backend/requirements.txt`**

*   **Why:** To enhance the stability, reproducibility, and predictability of the backend Python environment for the Hangar Bay project. Unpinned dependencies can lead to unexpected issues due to automatic updates to newer, potentially incompatible or buggy, library versions.

*   **How:**
    *   The decision was made to pin all direct dependencies listed in `app/backend/requirements.txt`.
    *   The following packages had their versions explicitly set:
        *   `fastapi` pinned to `0.115.12`
        *   `uvicorn[standard]` pinned to `0.34.3`
        *   `SQLAlchemy` pinned to `2.0.41`
        *   `alembic` pinned to `1.16.1`
        *   (Packages `pydantic-settings` and `python-dotenv` were already pinned).
    *   Latest stable versions were identified using `pip index versions --pre <package>` and PyPI lookups.
    *   The `app/backend/requirements.txt` file was updated accordingly.

*   **Impact & Rationale:** This practice provides several key benefits:
    1.  **Reproducible Builds:** Ensures consistent environments across developer machines and CI/CD pipelines.
    2.  **Preventing Unexpected Breaking Changes:** Protects against automatic updates to library versions that might introduce bugs or break compatibility.
    3.  **Dependency Resolution Stability:** Helps `pip` resolve transitive dependencies more predictably.
    4.  **Security:** Provides a clear baseline for dependency versions, aiding in vulnerability assessment and management.
    5.  **Easier Debugging:** Simplifies troubleshooting by keeping dependency versions constant between environment rebuilds.
    6.  **Clearer Understanding of the Environment:** `requirements.txt` now serves as an exact manifest of the backend's Python dependencies.

---

---
**2025-06-07 23:49:51-05:00 - Adopted Project-Wide Dependency Version Pinning Policy**

*   **Why:** To enhance the stability, reproducibility, and predictability of builds across all components of the Hangar Bay project. Pinning dependency versions is a crucial best practice that mitigates risks associated with automatic updates, ensures consistent development and deployment environments, and aids in security vulnerability management.

*   **How:**
    1.  **Policy Formalization:** A formal policy mandating the pinning of all dependency versions was established. This policy covers:
        *   Backend Python dependencies (`requirements.txt`).
        *   Frontend JavaScript/TypeScript dependencies (`package.json` and associated lock files like `package-lock.json`).
        *   Base images and package installations within Dockerfiles.
        *   Consistency in major versions for database systems like PostgreSQL.
    2.  **Documentation Updated:**
        *   The `design/design-spec.md` was updated with a new subsection `6.0. Dependency and Versioning Policy` under "Section 6: Tech Stack" to detail this requirement for human developers and AI.
        *   A `cascade-log.md` entry was created to capture the verbose discussion and rationale behind the areas requiring pinning.
    3.  **AI Memory Created:** A new AI operational memory (ID: `4b806f4d-8600-46c6-b939-f373f67f3c50`), titled "Policy: Project-Wide Dependency Version Pinning," was created. This memory instructs AI assistants (like Cascade) to adhere to and enforce this policy during development.
    4.  **Memory Index Updated:** The `design/memory-index.md` was updated to include an entry for the new AI memory.

*   **Impact:**
    *   All future development work will adhere to strict dependency version pinning.
    *   Project build processes will be more reliable and less prone to unexpected failures due to dependency changes.
    *   The project's security posture is strengthened by having a clear and consistent baseline of dependency versions.
    *   Onboarding new developers will be simpler due to more predictable environment setups.
    *   This decision builds upon the previous specific action to pin backend Python dependencies, extending the practice project-wide.

---

---
**2024-07-30: Documentation Restructure: `CONTRIBUTING.md` Introduction and `README.md` Simplification**

**Why:**
*   The existing `README.md` was becoming overly long and mixed high-level project overview with detailed development setup instructions and AI-specific guidance. This made it challenging for contributors (both human and AI) to quickly locate essential information.
*   A clearer separation of concerns was needed to distinguish between a concise project introduction, practical development guidelines, and in-depth architectural specifications.

**How:**
1.  **Creation of `CONTRIBUTING.md`:**
    *   A new, dedicated file (`CONTRIBUTING.md`) was established at the project root.
    *   This file now consolidates:
        *   Detailed development environment setup instructions (migrated from the previous `README.md`).
        *   Project coding standards.
        *   Version control workflow (including branching strategy, commit message conventions, and pull request procedures).
        *   Guidelines for testing (with links to `design/test-spec.md`).
        *   Dependency management policies (referencing the policy in `design/design-spec.md`).
        *   Comprehensive AI assistant guidance (migrated from `README.md` and expanded).
        *   Placeholders for future sections like a Code of Conduct, Issue Tracking, and Code Review Guidelines.
2.  **Refactoring of `README.md`:**
    *   The `README.md` was significantly streamlined to serve as a high-level entry point to the project.
    *   It now primarily contains:
        *   A brief project overview and its motivation.
        *   Prominent links to key documentation: `CONTRIBUTING.md`, `design/design-spec.md`, and `design/design-log.md`.
        *   A concise list of core technologies used in the project.
    *   Detailed setup instructions and extensive AI guidance sections were removed from `README.md` and are now accessible via the link to `CONTRIBUTING.md`.

**Impact:**
*   **Improved Clarity and Navigability:** Contributors can more easily find the information relevant to their needs.
*   **Enhanced Onboarding Experience:** `CONTRIBUTING.md` provides a focused and actionable guide for new human developers and AI assistants.
*   **Better Separation of Documentation Concerns:**
    *   `README.md`: Provides a quick, high-level project overview and essential navigation links.
    *   `CONTRIBUTING.md`: Offers practical, "how-to" guidance for development and contribution.
    *   `design/design-spec.md` (and other `design/` documents): Detail the "what" and "why" of the system's architecture and design.
*   **Increased Maintainability:** Specific sections of documentation can be updated more easily without impacting unrelated content.
*   **Optimized AI Interaction:** AI assistants have a dedicated, structured document outlining development procedures and project interaction guidelines, improving their efficiency and adherence to project standards.

---

---
**2025-06-08 03:05:00-05:00: User Model Design: Account Types and Authorization Flags**

**Context:**
During the initial database setup (Task 01.2) and definition of the first SQLAlchemy model (`User` in `fastapi_app/models/common_models.py`), a key consideration arose regarding authentication methods and explicit user type differentiation, primarily EVE Online Single Sign-On (SSO) versus potential local administrative/test accounts.

**Decision:**
The `User` model was designed to clearly separate account type (authentication origin) from authorization levels:
*   `hashed_password`: Made `nullable=True`. This allows EVE SSO users (who authenticate externally and do not have a locally stored password) to have a `NULL` value in this field. Local accounts will have a hashed password stored here.
*   `eve_character_id`: Added as `Column(Integer, unique=True, index=True, nullable=True)`. This field will store the EVE Online character ID for users authenticating via SSO. It is `nullable=True` for local accounts.
*   `username`: Retained as `nullable=False` and `unique=True`. This field can store the EVE character name for SSO users or a chosen username for local accounts.
*   `email`: Retained as `nullable=False` and `unique=True`.
*   `user_type`: Added as `Column(SAEnum(UserType), nullable=False, index=True)`. This uses a Python `enum.Enum` (`UserType` with values `EVE_SSO`, `LOCAL`) backed by SQLAlchemy's `Enum` type. This explicitly defines the account's origin/management type.
*   `is_admin`: Added as `Column(Boolean, default=False, nullable=False)`. A boolean flag to indicate administrative privileges, independent of `user_type`.
*   `is_test_user`: Added as `Column(Boolean, default=False, nullable=False)`. A boolean flag to identify test accounts, independent of `user_type`.

**Rationale:**
This refined approach significantly enhances flexibility, clarity, and separation of concerns:
*   **Decoupling Account Type from Authorization:**
    *   `user_type` (`EVE_SSO`, `LOCAL`) defines the account's origin and how it's managed/authenticated.
    *   Boolean flags (`is_admin`, `is_test_user`) define specific roles or attributes, which can apply to any `user_type`. For example, an `EVE_SSO` user can be an admin, as can a `LOCAL` user.
*   **Improved Data Integrity and Querying:** Explicit flags for admin status and test status are clearer and more robust than inferring these from a combined `user_type` enum.
*   **Scalability:** This model is easier to extend with more granular roles or permissions in the future (e.g., by adding more boolean flags or a dedicated RBAC system).
*   **SQLAlchemy `Enum` Benefits:** Using `SAEnum(UserType)` continues to provide type safety in Python and database-level constraints for account types.
*   The `hashed_password` and `eve_character_id` fields remain key for their respective authentication paths.

**Impact:**
*   The `User` model in `fastapi_app/models/common_models.py` reflects this refined design, including the updated `UserType` enum (`EVE_SSO`, `LOCAL`) and the new `user_type`, `is_admin`, and `is_test_user` columns.
*   Alembic migrations for the `users` table will be based on this comprehensive schema.
*   Future authentication, authorization, and user management logic will leverage `user_type` for account origin and the boolean flags for specific privileges/attributes.
*   The task plan `01.2-database-setup.md` will be updated to note this more detailed design.

---

---
**2025-06-08 05:14:24-05:00: Backend Dependency Management Migration to PDM**

**Decision:** Migrated the Hangar Bay backend Python project's dependency and environment management from a traditional `venv` and `requirements.txt` setup to PDM (Python Development Master).

**Rationale & Alternatives Considered:**

The existing `venv` and `requirements.txt` approach, while functional, lacks some of the modern conveniences and robustness offered by newer tools. The primary alternative was to maintain the status quo. However, migrating to PDM was chosen for several key benefits:

*   **Standardization:** PDM utilizes `pyproject.toml`, aligning with modern Python packaging standards (PEP 517, PEP 518, PEP 621, PEP 660).
*   **Reproducibility:** PDM generates a `pdm.lock` file, ensuring deterministic builds and consistent environments across different setups by locking down the exact versions of all direct and transitive dependencies.
*   **Improved Dependency Resolution:** PDM has a sophisticated dependency resolver that can handle complex scenarios more effectively than pip alone.
*   **Integrated Tooling:** PDM allows defining run scripts directly in `pyproject.toml` (e.g., for linting, formatting, running the dev server), streamlining common development tasks.
*   **Clearer Dependency Groups:** PDM supports explicit dependency groups (e.g., `dev`, `test`), making it easier to manage dependencies for different purposes.
*   **Simplified Workflow:** Commands like `pdm add`, `pdm install`, `pdm update`, and `pdm run` offer a more cohesive and user-friendly experience.
*   **In-Project Virtual Environments:** Configuring PDM for in-project `.venv` (`pdm config venv.in_project true`) keeps the environment closely tied to the project, simplifying discovery and activation for developers and IDEs.

**Benefits:**
The migration to PDM is expected to lead to:
*   More reliable and reproducible builds.
*   Easier onboarding for new developers.
*   A cleaner project structure for backend dependencies.
*   Simplified execution of common development tasks (linting, formatting, running server).
*   Better long-term maintainability of the backend environment.

**Execution Summary:**
The migration was executed systematically:
1.  A dedicated task file (`00.3-backend-pdm-migration.md`) was created to document the process.
2.  PDM was initialized in the `app/backend/` directory, configured for an in-project virtual environment.
3.  Production and development dependencies were manually added with pinned versions using `pdm add`.
4.  PDM scripts for `lint`, `format`, and `dev` were configured in `pyproject.toml`.
5.  The root `.gitignore` was updated to correctly track `pdm.lock` and ignore PDM-specific cache/build files.
6.  The main project `README.md` was updated with new backend setup instructions.
7.  The legacy `app/backend/requirements.txt` was deleted.
8.  A `ModuleNotFoundError` for `fastapi_app` when running `pdm run dev` (due to the `src` layout) was resolved by adding `--app-dir src` to the Uvicorn command in the `dev` script.
9.  The setup was thoroughly tested, confirming successful dependency installation and script execution.

The migration is considered successful and complete.

---

## Operationalizing a Comprehensive Phase Review Process (Approx. 2025-06-08 07:36:20-05:00)

**Context & Objective:**
As the Hangar Bay project progresses through its initial implementation phases, a critical need emerged for a structured, repeatable, and comprehensive phase review process. The primary objectives were to:
1.  Ensure thorough documentation of work completed, decisions made, and outcomes achieved within each phase.
2.  Systematically capture technical learnings, process improvements, and challenges encountered.
3.  Provide a formal mechanism for reviewing cross-cutting concerns (Security, Observability, Testing, Accessibility, I18n, Performance) at a phase level.
4.  Track unresolved issues and technical debt, and formulate actionable recommendations for subsequent phases.
5.  Critically, to enhance AI-USER collaboration by creating a structured feedback loop and proactively generating persistent memories for the AI assistant (Cascade) to improve its future performance and contextual understanding.

**Iterative Development & Reflective Refinement:**
The development of the phase review process was not a one-off task but an iterative and reflective endeavor.
*   **Initial Template:** An initial `phase-review-template.md` was drafted.
*   **First Application (Phase 0):** This template was first applied to document the "Phase 0: Foundational Setup" in `00-foundational-setup-review.md`. This practical application served as a crucial testbed.
*   **Reflective Review:** Upon completing the draft of the Phase 0 review, a dedicated meta-review was conducted. This involved critically assessing the template's effectiveness, identifying gaps, and pinpointing areas where clarity or comprehensiveness could be improved. This reflective step was key to honing the process.
*   **Template Enhancements:** Based on the meta-review, `phase-review-template.md` was significantly enhanced:
    *   **Bi-directional Continuity Links:** Added "Previous Phase Review" and "Next Phase Review" fields in the header to explicitly link adjacent phase reviews, ensuring project continuity.
    *   **Tracking Carry-over Issues:** A new sub-section, "Status of Carry-over from Previous Phase," was added under "Unresolved Issues & Technical Debt" to ensure that items identified in previous reviews are explicitly tracked.
    *   **Proactive Memory Creation:** A vital new sub-section, "Specific Memories to Create/Update based on this Phase's Learnings," was added to "Recommendations for Subsequent Phases." This formalizes the process of distilling key learnings from each phase into actionable memories for Cascade.

**Operationalization - Key Components & Artifacts:**
The refined phase review process was operationalized through a set of interconnected documents and procedures:
*   **`plans/implementation/phase-reviews/phase-review-template.md`:** This is the cornerstone document, providing the standardized structure and detailed prompts for all sections of a phase review. Its comprehensiveness guides both the USER and Cascade.
*   **`plans/implementation/phase-reviews/00-foundational-setup-review.md`:** The first fully completed review document, serving as an exemplar and demonstrating the practical application of the enhanced template.
*   **Cascade Memory for the Process (`MEMORY[ae1474b0-0dab-4877-bf81-b124de8ab6f4]` - "Hangar Bay: Phase Review Process and Best Practices for Cascade"):** A detailed, persistent memory was created specifically for Cascade. This memory outlines the entire phase review procedure, emphasizing template usage, critical sections, inter-linking of review documents, and the importance of extracting learnings for AI improvement. This operationalizes the process for the AI assistant.
*   **Specific Learnings Captured as Actionable Memories:** The Phase 0 review directly led to the identification and creation of several key memories, demonstrating the "Specific Memories to Create/Update" section in action:
    *   `MEMORY[76514710-a6dd-4f01-96f2-fff235ab83c9]`: Python Src Layout Uvicorn Configuration
    *   `MEMORY[62974893-f9ef-42cb-b031-27fa1a4d19db]`: Python Environment Migration Best Practice
    *   `MEMORY[d3e20aff-aac5-45fd-95e5-ad9ecf10a198]`: Comprehensive Gitignore for New Projects
    *   `MEMORY[ae1474b0-0dab-4877-bf81-b124de8ab6f4]`: Hangar Bay: Phase Review Process and Best Practices for Cascade
*   **`design/memory-index.md`:** All newly created memories, including the process memory and the specific learning memories, were indexed in this central file, providing a quick reference and ensuring their discoverability.

**Benefits Achieved & Overall Impact:**
The establishment and operationalization of this comprehensive phase review process have yielded significant benefits, profoundly enhancing our documentation and knowledge capture mechanisms:
*   **Improved Documentation Quality & Consistency:** Standardized templates ensure all critical aspects are covered in each review.
*   **Enhanced Knowledge Capture & Retention:** Key decisions, learnings, and justifications are systematically recorded, preventing knowledge loss and providing valuable context for future work, especially for Cascade.
*   **Better Traceability:** Bi-directional links and structured tracking of issues provide clear traceability across project phases.
*   **Proactive Management of Technical Debt:** Formal sections for identifying debt and recommending actions ensure these are not overlooked.
*   **Structured AI Collaboration & Learning:** The process explicitly incorporates feedback for Cascade and mandates the creation of memories, fostering a continuous learning loop for the AI.
*   **Iterative Process Improvement:** The reflective nature of the review ensures the process itself can adapt and improve over time.

This structured approach to phase reviews, born from an iterative and reflective cycle, represents a significant maturation in the Hangar Bay project's governance and its strategy for effective human-AI collaboration. It ensures that each phase not only delivers its technical objectives but also contributes to a growing, well-organized, and actionable knowledge base for the entire project lifecycle.

---

## Phase 03 Pre-Mortem Review & Task Refinement (Approx. 2025-06-08)

*   **Context:** Conducted a multi-round pre-mortem review process for the Phase 03 Angular frontend core infrastructure tasks. This iterative review aimed to proactively identify potential issues, clarify requirements, and ensure alignment before extensive implementation. (Related to User Memory/Concept ID: `c47b0e87-7941-492e-9b55-6ee0d0261410` - *Note: This ID was provided by the user; its specific content is not currently in Cascade's active memory set.*)
*   **Process & Structure:**
    *   The review involved several loops of discussion, planning, and refinement between the USER and Cascade.
    *   Initial task definitions were challenged, leading to restructuring and renaming.
    *   Cross-references, metadata, and documentation impacts were systematically analyzed.
*   **Key High-Level Insights from the Process:**
    *   **Proactive Issue Identification:** The pre-mortem approach proved highly effective in surfacing ambiguities and potential downstream problems before they manifested in code.
    *   **Enhanced Clarity:** Iterative discussion significantly clarified task scopes, responsibilities, and the desired end-state for each Phase 03 deliverable.
    *   **Improved Architectural Alignment:** Ensured that the restructured tasks (e.g., `03.0-angular-project-initialization.md`, `03.1-angular-core-module-setup.md`) accurately reflected the Hangar Bay architectural standards and best practices for Angular development.
    *   **Value of Explicit Sequencing:** Reinforced the importance of explicit YAML metadata for task sequencing, making the development flow transparent and machine-readable.
*   **Notable Issues Identified and Resolved:**
    *   **Task Scope & Naming:** Initial task names and scopes for `03.0` and `03.1` were found to be overlapping and not optimally aligned with a logical project setup flow. This led to their renaming and significant content restructuring to `03.0-angular-project-initialization.md` and `03.1-angular-core-module-setup.md`.
    *   **Metadata Consistency:** Ensured that all `PreviousTask` and `NextTask` references in the YAML metadata blocks were correct across all four Phase 03 tasks after the restructuring.
    *   **Documentation Cohesion:** Verified and updated links and task descriptions in overview documents (`00-mvp-implementation-plan-overview.md`, `00-mvp-implementation-plan-progress.md`) to maintain consistency with the restructured tasks.
    *   **Implicit vs. Explicit Dependencies:** The process highlighted the need to make all task dependencies and execution order explicit, moving away from any implicit understandings.
*   **Outcome:** The Phase 03 tasks are now more robustly defined, sequenced, and documented, providing a clearer path for implementation. The final structure was committed (Commit ID: `7583c02`).

---

## Formalization of Project Review Processes & Artifacts (Approx. 2025-06-08 21:35:00-05:00)

*   **Context:** A need was identified to formalize and centralize project review artifacts, specifically pre-mortem (anticipatory) and post-mortem (retrospective, e.g., phase reviews), to enhance knowledge capture, process consistency, and AI-assisted learning for the Hangar Bay project.
*   **Decisions & Actions Taken:**
    *   A new top-level directory `design/reviews/` was established to house all review-related artifacts.
    *   Subdirectories were created:
        *   `design/reviews/pre-mortems/` for proactive pre-mortem reviews.
        *   `design/reviews/post-mortems/` for retrospective reviews.
    *   The existing `plans/implementation/phase-reviews/` directory and its contents (phase review templates and completed reviews) were migrated to `design/reviews/post-mortems/phase-reviews/`, recognizing phase reviews as a type of post-mortem.
    *   A new standardized template for pre-mortem reviews, `00-pre-mortem-review-template.md`, was created in `design/reviews/pre-mortems/`.
    *   A new Cascade memory (ID: `ee09a93d-c516-4049-9d9d-78e80280c63a`, Title: "Project Review Structure and Templates (Hangar Bay)") was created to document this new structure and its purpose.
*   **Key High-Level Insights & Rationale:**
    *   **Centralized Artifacts for AI Efficiency:** Consolidating review documents in `design/reviews/` provides Cascade with a predictable, centralized location for discovering, accessing, and analyzing these critical learning artifacts.
    *   **Complementary Review Cycle:** Formalizing both pre-mortem (anticipating potential failures and risks before work) and post-mortem (learning from actual outcomes after work) reviews creates a comprehensive "bookend" for project phases and significant tasks, fostering a robust learning cycle.
    *   **Synergistic AI Analysis (Pre + Post):**
        *   **Validating Foresight:** Cascade can compare risks identified in pre-mortems against actual issues documented in corresponding post-mortems. This helps assess the accuracy of the pre-mortem process and identify areas for improvement in risk anticipation.
        *   **Pattern Recognition:** By analyzing both types of reviews across multiple project segments, Cascade can identify recurring risk patterns, common pitfalls, or consistently successful mitigation strategies.
        *   **Effectiveness Tracking:** The effectiveness of mitigation strategies proposed in pre-mortems can be evaluated by examining their impact as recorded in post-mortems.
        *   **Refining Planning & Estimation (Qualitative):** Insights from both review types can highlight consistently complex task areas, informing better upfront planning and resource consideration for similar future work.
        *   **Proactive, Contextual Support:** When new tasks or phases are initiated, Cascade can review past relevant pre- and post-mortems to offer more targeted, proactive questions and suggestions based on historical learnings.
    *   **Enhanced Project Governance & Continuous Improvement:** This structured approach to reviews strengthens overall project discipline, ensures systematic knowledge capture, and provides a clear mechanism for continuous process improvement based on documented learnings.
*   **Impact on Cascade's Operations:** Cascade will leverage this structured review data to provide more insightful, proactive support, contributing to improved task and phase implementation quality, better risk management, and more effective human-AI collaboration.

---

## Angular Frontend Documentation & AI Memory Initialization (Approx. 2025-06-09 22:58:43-05:00)

*   **Objective:** To establish a comprehensive, AI-friendly knowledge base for Angular frontend development for the Hangar Bay project, improving consistency, quality, and AI collaboration.
*   **Key Actions & Decisions:**
    *   The `design/angular/` directory was created to house detailed Angular guidelines.
    *   A high-level Angular frontend architecture document, `design/angular-frontend-architecture.md`, was established.
    *   A suite of detailed guideline documents (`00` through `09`) covering introduction, coding style, components, templates, state management (Signals & RxJS), forms, routing, HTTP, SSR/performance, and testing was created within `design/angular/`.
    *   A Hybrid Documentation Approach was adopted, combining human-readable detailed guides with granular AI memories.
    *   An "AI Analysis Guidance for Cascade" section was prepended to markdown files exceeding 200 lines to remind AI to read the full content if necessary.
    *   An initial set of AI memories was created to capture key Angular best practices and project conventions. This includes:
        *   Overall Angular documentation structure (Memory: `ea3572b4-af10-48a2-83a8-cc4f83f3cf0d`)
        *   File Naming Convention (Memory: `2bc1d2f0-56a1-489a-a1e4-d392e3b33d06`)
        *   Dependency Injection Preference (Memory: `deaf34ea-03ac-478b-be6d-0aecd1a9b15d`)
        *   Component Template Access (Memory: `9e5f9aaf-9f1b-45e4-8796-b2eb4a46d663`)
        *   Deferred Loading with `@defer` (Memory: `c99834e5-65a8-40cf-a53a-0401af4dd91d`)
        *   Standalone Components Preference (Memory: `bd7c05f6-6df9-4f84-b9b0-c39ea94d7545`)
        *   Signals for State Management (Memory: `f72a5380-d354-41cf-b566-b535b5296051`)
        *   New Control Flow (`@if`, `@for`, `@switch`) (Memory: `4cc11d93-0dc6-4ab7-a8f9-d16771a48d91`)
        *   `track` with `@for` for Performance (Memory: `11d0a1e2-4982-424d-83a4-aef3a38611ed`)
*   **Rationale:** This structured documentation and AI memory initiative aims to streamline Angular development, ensure adherence to modern best practices, and enhance the effectiveness of AI-assisted coding for Hangar Bay.

---

---
**2025-06-10 01:39:35-05:00: Standardization of Markdown Cross-Project Links & Tooling Challenges**

**Context & Objective:**
A significant effort was undertaken to standardize all cross-project markdown links within the Hangar Bay documentation (implementation plans, design specifications, etc.). The primary goal was to ensure all such links used root-relative paths, typically starting with `/design/specifications/` or `/design/features/`, to improve link robustness, maintainability, and clarity across the entire project. This initiative was driven by the `MEMORY[b77171e2-c900-4f20-9620-6fad06e863aa]` which mandates root-relative paths.

**Process & Challenges:**
The process involved systematically reviewing and updating markdown files, primarily focusing on Phase 02 (Backend F001) and Phase 03 (Frontend Core Infrastructure) implementation task files. The `replace_file_content` tool was used for these modifications.

Several challenges were encountered during this process:
1.  **Tool Behavior with Markdown:** The `replace_file_content` tool, while powerful, exhibited some non-ideal behaviors when dealing with markdown links:
    *   **Incorrect Wrapping:** On several occasions, the tool incorrectly wrapped already correct or newly corrected links with `[path](path)` syntax, duplicating the path.
    *   **Backtick Preservation:** Ensuring backticks around link paths (`/path/to/file.md`) were preserved or correctly added was sometimes problematic, requiring specific attention in the `ReplacementContent`.
    *   **Fragment Identifier Handling:** Care was needed to preserve URL fragment identifiers (e.g., `#section-id`) during replacements.
2.  **Exact `TargetContent` Requirement:** The tool requires the `TargetContent` to be an exact string match. Minor discrepancies, including whitespace or subtle formatting differences between the expected and actual content, led to failed replacements or unintended changes. This necessitated careful file viewing and precise `TargetContent` specification.
3.  **Iterative Corrections:** Due to the above challenges, updating links in a single file often required multiple iterations of:
    *   Viewing the file content.
    *   Identifying incorrect links.
    *   Crafting `replace_file_content` tool calls.
    *   Reviewing the diff/output.
    *   Re-viewing the file and making further corrections if the tool's application was not as expected.
4.  **Multiple Instances:** Handling multiple instances of the same relative link within a single file sometimes required careful use of `AllowMultiple: true` or breaking down changes into several chunks.

**Files Updated (Examples):**
*   `plans/implementation/phase-02-backend-f001-public-contract-aggregation/02.3-background-aggregation-service.md`
*   `plans/implementation/phase-02-backend-f001-public-contract-aggregation/02.4-api-endpoints-f001.md`
*   `plans/implementation/phase-03-frontend-core-infrastructure/03.0-angular-project-initialization.md`
*   `plans/implementation/phase-03-frontend-core-infrastructure/03.1-angular-core-module-setup.md`
*   `plans/implementation/phase-03-frontend-core-infrastructure/03.2-backend-api-service-layer.md`
*   `plans/implementation/phase-03-frontend-core-infrastructure/03.3-basic-layout-routing-navigation.md`
*   User also manually updated links in `00-mvp-implementation-plan-overview.md`, `00-mvp-implementation-plan-progress.md`, and `phase-review-template.md`.

**Key Learnings & Recommendations for Cascade:**
*   **Markdown Link Complexity:** Modifying markdown links, especially with variations in existing formatting (backticks, fragments, relative vs. absolute), is a delicate operation. Automated replacements must be approached with extreme caution.
*   **Tool Specificity:** When using `replace_file_content` for markdown:
    *   Be highly precise with `TargetContent`.
    *   Verify the exact existing string, including any surrounding markdown syntax (backticks, brackets, parentheses).
    *   In `ReplacementContent`, ensure the desired final markdown syntax is explicitly constructed.
    *   Anticipate that the tool might reformat or misinterpret complex markdown structures if not perfectly targeted.
*   **Incremental Changes & Verification:** For tasks involving widespread, similar changes across multiple files or complex changes within a single file, adopt a highly incremental approach:
    1.  Target a small, specific set of changes.
    2.  Execute the change.
    3.  Thoroughly verify the result (view file/diff).
    4.  Correct any deviations immediately before proceeding.
*   **Consider Alternative Strategies:** For very complex or widespread refactoring of structured text like markdown, if `replace_file_content` proves consistently problematic, discuss alternative strategies with the USER (e.g., scripts, manual review for edge cases).
*   **Memory Reinforcement:** This experience reinforces the importance of `MEMORY[b77171e2-c900-4f20-9620-6fad06e863aa]` and the need to be vigilant about link formats.

**Outcome:**
Despite the challenges, the targeted documentation files were successfully updated to use standardized root-relative links, improving the overall consistency and maintainability of the project's documentation. The process provided valuable insights into the nuances of using code editing tools for structured text formats like Markdown.

---

## Pre-Mortem Process Evolution & Standardization (Approx. 2025-06-10 04:08:20-05:00)

*   **Context:** A review of the existing pre-mortem documents revealed an opportunity to significantly enhance their structure and utility, transforming them from simple risk logs into comprehensive strategic guides and learning tools. This effort was inspired by the prompt to better explain the "why and how" behind decisions, not just the "what."
*   **Decision:** The pre-mortem process and associated artifacts were systematically overhauled.
*   **Key Enhancements:**
    *   **New Template Structure:** The `design/reviews/pre-mortems/00-pre-mortem-review-template.md` was completely redesigned to be more robust and prescriptive.
    *   **Added Strategic Sections:** The template and existing pre-mortems (`phase-02-backend-f001-pre-mortem.md`, `phase-03-frontend-core-infra-pre-mortem.md`) were updated to include:
        *   `Assumptions and Dependencies`: To explicitly state the foundational context of the design.
        *   `Implications for Testing Strategy`: To directly link identified risks to concrete quality assurance actions.
        *   `Monitoring and Observability Requirements`: To ensure operational readiness is a first-class design citizen.
    *   **Enhanced AI Guidance:** All sections in the new template include detailed `Guidance for Cascade` prompts to improve the quality of AI-assisted reviews and ensure a focus on connecting problems to solutions.
    *   **Improved Traceability:** `PreviousPreMortemReview` and `NextPreMortemReview` links were added to the frontmatter of all pre-mortem documents to create a clear, navigable history of the project's design evolution.
*   **Rationale:** This evolution of the pre-mortem process standardizes a higher level of rigor for risk analysis. It ensures that future reviews are more thorough, actionable, and serve as valuable, long-lived documentation for both human developers and AI assistants, capturing not just risks but also the strategic thinking behind their mitigation.

---

---

**2025-06-12 04:30:57-05:00: Lessons from ESI Data Aggregation: Transaction Management & Batching**

**Context & Objective:**
During the development and troubleshooting of the F001 Public Contract Aggregation backend feature, particularly concerning Alembic migrations and data persistence, critical lessons were learned regarding the interaction between external ESI API calls and internal database transaction management. The objective of this log entry is to capture these learnings to inform future design and implementation patterns for data aggregation and processing.

**Key Learnings & Decisions:**

1.  **Cost Asymmetry and Its Implications:**
    *   **ESI API Calls:** Recognized as "expensive" due to network latency, rate limits, and potential unreliability. Each call should be treated as a valuable, potentially failing operation.
    *   **Database Transactions:** Local database operations (commits, rollbacks) are "cheap" and fast in comparison.
    *   **Decision:** Design patterns must acknowledge this asymmetry, minimizing ESI calls (e.g., via ETags) and ensuring robust handling of their outcomes before committing related data.

2.  **Problem with Fine-Grained Commits:**
    *   **Initial Approach:** An earlier tendency was to commit data to the database incrementally within a larger logical operation (e.g., commit contract header, then fetch/commit items separately).
    *   **Identified Risk:** This pattern leads to a high risk of data inconsistency if a subsequent ESI call (e.g., for contract items) or processing step fails after an initial part of the data (e.g., contract header) has already been committed. This can leave orphaned or incomplete records in the database.

3.  **Adoption of "Logical Unit of Work" with Atomic Transactions:**
    *   **Definition:** A "logical unit of work" encompasses all ESI calls and processing steps required to fetch and store a complete, self-contained entity (e.g., a contract along with *all* its items).
    *   **Decision:** All database changes related to a single logical unit of work *must* be performed within a *single database transaction*.
        *   **Success Path:** The transaction is committed only if *all* ESI calls and processing for that unit are successful.
        *   **Failure Path:** If *any* part of the unit of work fails (ESI error, processing error), the *entire* database transaction for that unit is rolled back.
    *   **Rationale:** This ensures atomicity and data integrity. It is preferable to re-attempt fetching/processing a complete unit (leveraging ESI ETags to minimize actual data re-transfer) than to persist incomplete or inconsistent data.

4.  **Reinforcement of Idempotency and ESI ETags:**
    *   **Idempotency:** Operations must be designed so that re-processing the same logical unit (e.g., due to a retry) results in the correct final state without duplicates or errors (typically via upsert logic).
    *   **ETags:** Continued emphasis on using ESI ETags for conditional GETs is crucial to reduce load on ESI and avoid re-processing unchanged data.

5.  **Implications for Future Design (Cascade & Team):**
    *   **Transaction Boundaries:** Carefully define transaction boundaries around logical units of work, especially when dealing with external API interactions.
    *   **Error Handling:** Implement comprehensive error handling for external API calls, with clear rollback strategies for associated database transactions.
    *   **State Management:** For multi-step external interactions, consider explicit state management within models (e.g., `processing_status` fields) to track progress and facilitate retries for failed units.
    *   **Background Task Queues:** For complex or long-running aggregations, leverage robust task queues that can manage retries and state for individual units of work.

**Outcome:**
By adopting a stricter model of atomic transactions for logical units of work, the reliability and data integrity of the ESI aggregation process are significantly improved. This approach minimizes the risk of inconsistent database states resulting from partial failures during interactions with the ESI API. These principles will guide the design of future data ingestion and processing features.

---

**2025-06-12 08:29:39-05:00: Architectural Pattern for Dependency Management in Hybrid Contexts**

**Context & Objective:**
The application runs in multiple contexts: synchronous API requests managed by FastAPI's lifecycle, and asynchronous background jobs managed by APScheduler running in separate processes. A critical `PicklingError` during background job execution revealed that the dependency management strategy must account for these different contexts. Pickling means serialization. The objective is to define a clear, robust pattern for managing dependencies, especially non-picklable resources like cache or database clients.

**Key Decisions & Pattern:**

1.  **FastAPI Request-Response Context (The Default):**
    *   **Pattern:** Use FastAPI's built-in dependency injection (`Depends`) system.
    *   **Mechanism:** Dependencies (e.g., `get_db`, `get_cache`) create and yield resources. FastAPI manages the resource lifecycle, ensuring it's available for the request and properly closed/released afterward.
    *   **Use Case:** Standard API endpoints (`@router.get`, `@router.post`, etc.).

2.  **APScheduler Background Job Context (The Exception):**
    *   **Problem:** Objects passed to jobs running in a separate process must be serializable (picklable). Live resource clients (like `aioredis.Redis`) are not picklable. Passing them via dependency injection from the main app to the job fails.
    *   **Pattern:** "Dynamic Resource Instantiation."
    *   **Mechanism:**
        *   Services or classes intended for use in background jobs (`ContractAggregationService`, `ESIClient`) must *not* accept live resource clients in their `__init__` methods.
        *   Instead, they should accept picklable configuration, primarily the Pydantic `Settings` object.
        *   Within the method that executes as the background job, the resource client is created, used, and closed dynamically. (e.g., `redis = await aioredis.from_url(settings.CACHE_URL)`).
    *   **Rationale:** This ensures no non-picklable objects are passed across process boundaries. It makes the service self-contained and responsible for its own resources when operating outside the FastAPI request lifecycle.

**Implications for Future Design:**
*   This dual-pattern approach is now the standard. When creating a new service, the first question must be: "Will this run in a background job?"
*   If yes, it *must* follow the "Dynamic Resource Instantiation" pattern.
*   If no, it can and should leverage the standard FastAPI `Depends` pattern.
*   This avoids architectural drift and provides a clear, non-negotiable rule for handling resource dependencies, preventing future `PicklingError` issues.

---

**2025-06-12 08:31:00-05:00: Service Architecture: Self-Contained vs. Injected Resources**

**Context & Objective:**
To further clarify the application's service layer architecture and prevent cyclical refactoring (e.g., toggling between passing a full `Settings` object vs. individual dependencies), this entry defines the philosophy for service construction.

**Key Decisions & Philosophy:**

1.  **Services are Self-Sufficient Units:** A service (e.g., `ContractAggregationService`) is viewed as a self-sufficient component responsible for a specific domain of business logic.

2.  **Configuration over Live Resources:**
    *   **Decision:** Services should be initialized with *configuration*, not with live, stateful resources like database sessions or cache clients. The primary piece of configuration passed to a service's constructor will be the Pydantic `Settings` object.
    *   **Rationale:**
        *   **Decoupling:** This decouples the service's logic from the resource's lifecycle management. The service doesn't need to know *how* a database session is created, only *that* it needs one and how to get it.
        *   **Flexibility & Testability:** It's easier to instantiate a service in a test environment by passing a mock or test-specific `Settings` object.
        *   **Pickle-Safety:** As established in the dependency management pattern, passing picklable `Settings` is essential for background job compatibility.

3.  **Resource Acquisition:**
    *   **Decision:** Services acquire resources *when needed* using one of two methods, depending on context:
        *   **API Context:** A service method called from an API endpoint can accept a resource (e.g., `db: AsyncSession`) as a method parameter, which is provided by FastAPI's DI system.
        *   **Background Context:** A service method running as a background job will instantiate its own resources using the `Settings` object it holds, as per the "Dynamic Resource Instantiation" pattern.

**Implications & Anti-Patterns to Avoid:**
*   **Canonical Pattern:** `my_service = MyService(settings=app_settings)`
*   **Anti-Pattern:** `my_service = MyService(db=get_db(), cache=get_cache())`. This is an anti-pattern because it tightly couples the service to live resources at instantiation time, making it less flexible, harder to test, and non-picklable.
*   This decision provides a stable, long-term answer to the "how do we build and provide services?" question, preventing future refactoring churn.

---

**2025-06-12 08:47:26-05:00: Standardized Documentation Structure for Technology Stacks**

**Context & Objective:**
To ensure consistency and maximize effectiveness for AI-assisted development (particularly for Cascade), a standardized documentation structure for different technology stacks (e.g., FastAPI, Angular) was needed. The previous structure had inconsistencies in the location of architecture overview documents and the organization of pattern/guide documents. The objective is to establish a clear, predictable, and efficient layout.

**Decision: Adopt "Fully Co-located Technology Stacks" Structure (Proposal 2)**

*   **Structure Definition:**
    *   `design/[technology_name]/` (e.g., `design/angular/`, `design/fastapi/`): Each technology stack will have its own comprehensive directory.
        *   `00-[technology]-architecture-overview.md`: The main architectural document for that specific stack (e.g., `design/fastapi/00-fastapi-architecture-overview.md`).
        *   `patterns/`: Subdirectory for specific, prescriptive design pattern documents related to that stack.
        *   `guides/`: Subdirectory for "how-to" or "cookbook" style guides for that stack.
        *   Other specific documents related to that technology can reside at the root of this technology-specific directory or be further organized if needed.
    *   `design/architecture/`: This folder will be reserved for truly global, cross-stack architectural documents, if any. It is not the primary location for stack-specific overviews.

*   **Rationale & Benefits for Cascade (AI Assistant):**
    *   **Optimal Discoverability & Focus:** All information pertinent to a specific technology stack (overview, patterns, guides) is grouped together in one place. This is highly efficient for AI, allowing quick access to relevant context without navigating disparate directory structures.
    *   **Enhanced Memory & Consistency:** Co-location is key to helping the AI "remember" and consistently apply established architectural principles for a given stack.
    *   **Modularity & Scalability:** The `patterns/` and `guides/` subdirectories prevent monolithic documents and cluttered flat folders, making it easier for the AI to find and apply specific rules or procedures.
    *   **Predictable Layout:** A consistent structure across all technology stacks reduces ambiguity and improves the AI's ability to navigate and utilize the documentation effectively.

*   **Implementation Steps:**
    *   Create the new structure for FastAPI in `design/fastapi/`.
    *   Refactor the existing Angular documentation by moving `design/architecture/angular-frontend-architecture.md` to `design/angular/00-angular-architecture-overview.md` and creating `patterns/` and `guides/` subdirectories within `design/angular/`.

**Impact:** This standardized structure will improve the AI's ability to understand, adhere to, and leverage architectural documentation, leading to more consistent, higher-quality code and reduced architectural drift.

--- 

### 2025-06-25 05:21:32-05:00 :: Confirmed Zoneless Angular Architecture

**Decision:** The Hangar Bay frontend will be a fully zoneless Angular application. This will be achieved by providing the `noop` zone implementation in `app.config.ts` and removing the `zone.js` polyfill.

**Rationale:**
*   **Performance:** Eliminating Zone.js reduces the initial bundle size and removes the performance overhead associated with its automatic change detection patching of browser APIs.
*   **Modern Practices:** This aligns with the direction of modern Angular development, encouraging more explicit and fine-grained control over change detection using signals and other manual triggers.
*   **Predictability:** It makes application behavior more predictable, as change detection cycles are triggered intentionally rather than automatically by any async operation.

**Impact:** All core infrastructure plans and AI implementation guidance have been updated to enforce this. All new components and services must be written with the assumption that Zone.js is not present.

---

### 2025-06-25 05:21:32-05:00 :: Standardized Top-Level Routing Structure

**Decision:** Adopted a standardized, scalable top-level routing structure for the application. The primary navigation will consist of a root "Home" link (`/`) and top-level feature links, such as "Contracts" (`/contracts`).

**Rationale:**
*   **Foundational & Scalable:** This approach provides a standard, scalable starting point. The `/contracts` route can later expand to have sub-routes like `/contracts/browse`, `/contracts/123`, etc., without needing to change the top-level navigation.
*   **Clarity:** The path `/contracts` is a clear, top-level entry point for the main feature of the application. A more specific path like `/browse-contracts` is better suited for a sub-view within that feature.

**Impact:** All Phase 3 implementation plans have been updated to reflect this structure. Future feature development should follow this pattern for top-level navigation.

---
### 2025-06-25 16:08:06-05:00 :: Established Mandatory Structural Protocol Testing

**Decision:** To prevent implementation errors of correct architectural patterns, a new mandatory testing practice has been added to the project's quality strategy. Any class designed to implement a specific Python protocol (e.g., async context manager, iterator) must be accompanied by a dedicated unit test that verifies its structural contract.

**Rationale:**
*   **Prevent Recurrence of Errors:** This decision is a direct result of a `TypeError` caused by the `ESIClient` class correctly being designed as an async context manager but failing to implement the required `__aenter__` and `__aexit__` methods.
*   **Shifting Failure Detection Left:** Structural tests are fast and simple. They catch fundamental implementation bugs during development and CI, long before they can cause runtime failures in a deployed environment.
*   **Enforcing Architectural Integrity:** This practice provides an automated guarantee that our code adheres to the low-level contracts of our chosen patterns, improving overall system robustness.

**Impact:** The `design/fastapi/guides/09-testing-strategies.md` guide has been updated with this new rule and a concrete example. Cascade has also internalized this as a persistent memory to enforce the practice in all future work.

---

### 2025-06-25 16:08:06-05:00 :: Codified the "Dual-Mode Service" Pattern

**Decision:** A new architectural pattern, the "Dual-Mode Service," has been formally documented in `design/fastapi/patterns/05-dual-mode-service-pattern.md`. This pattern governs the design of services that need to operate in two distinct contexts: (1) as a dependency-injected singleton in the main FastAPI application, and (2) as a freshly instantiated object within a separate process, such as an `APScheduler` background job.

**Rationale:**
*   **Resolving `PicklingError`:** The primary driver was to solve the `PicklingError` from `APScheduler`'s `ProcessPoolExecutor`, which cannot serialize services holding unpicklable resources like database or HTTP client connections.
*   **Architectural Clarity:** The pattern provides a clear, reusable solution. It dictates that services should be initialized with lightweight, picklable configuration (like a `Settings` object) and dynamically create their unpicklable resources (like an `httpx.AsyncClient`) on-demand, typically within an async context manager.
*   **Decoupling:** It decouples the service's lifecycle from the lifecycle of its heavy resources, making the service itself safe to pass between processes.

**Impact:** This is now the standard pattern for any service intended for use in background jobs. The `ESIClient` and `ContractAggregationService` have been refactored to follow this pattern, resolving the critical bug that blocked background processing.

---

### 2025-06-25 16:08:06-05:00 :: Corrected ESIClient to Implement Async Context Management

**Decision:** The `ESIClient` service class has been refactored to correctly implement the asynchronous context manager protocol by adding the `__aenter__` and `__aexit__` methods. These methods now manage the lifecycle of the internal `httpx.AsyncClient`.

**Rationale:**
*   **Fixing a `TypeError`:** The immediate cause was a `TypeError` because the class was being used in an `async with` block without supporting the protocol.
*   **Adherence to Design Patterns:** This change brings the `ESIClient` into compliance with two established patterns: the `API Client Service Pattern`, which requires a long-lived client instance, and the `Dual-Mode Service Pattern`, which requires on-demand resource creation for background jobs.
*   **Resource Management:** Proper implementation ensures that the `httpx.AsyncClient` is created when the context is entered and guaranteed to be closed when the context is exited, preventing resource leaks.

**Impact:** The `ESIClient` is now a robust, reusable service that functions correctly both when injected into API endpoints and when instantiated within the `ContractAggregationService` background job. This resolved a critical runtime bug.

---

## API Versioning & Proxy Alignment (2025-06-25 17:11:35-05:00)

*   **Context:** During the initial implementation of the contract listing feature (Phase 4), a mismatch was discovered between the backend API's expected path and the Angular frontend's proxy configuration.
*   **Problem:**
    *   The backend FastAPI router (`contracts.py`) was updated to serve endpoints under a versioned prefix: `/api/v1`.
    *   The Angular development proxy (`proxy.conf.json`) was configured to forward requests for `/api/v1` to the backend, but it also included a `pathRewrite` rule (`"^/api/v1": ""`) that *removed* this prefix before forwarding.
    *   This resulted in the frontend requesting `/api/v1/contracts/` but the backend receiving a request for `/contracts/`, causing a 404 Not Found error.
*   **Decision:** The `pathRewrite` rule was removed from `proxy.conf.json`.
*   **Rationale:**
    *   **Consistency:** This ensures that the path used by the frontend to make an API call is the exact same path that the backend server receives.
    *   **Explicit Versioning:** It enforces the API versioning scheme (`/api/v1`) as a fundamental part of the communication contract, making the architecture clearer and preventing future misconfigurations.
    *   **Maintainability:** By keeping the paths consistent, it simplifies debugging and makes it easier to reason about the flow of data between the frontend and backend during development. The proxy configuration now correctly reflects the backend's routing structure.

---

### 2025-06-25 17:33:36-05:00: Standardize on Fetch API for Angular HttpClient

**Problem:** The frontend application was stuck in a "Loading contracts..." state. Investigation confirmed the backend API was running correctly and the `proxy.conf.json` was properly configured. This indicated a subtle issue in the HTTP communication layer between the Angular development server and the backend, likely related to the default `XMLHttpRequest` transport used by `HttpClient`.

**Decision:** Enabled the modern `fetch` API as the underlying transport mechanism for Angular's `HttpClient` across the entire application. This was accomplished by updating `app.config.ts` to use `provideHttpClient(withFetch())`.

**Rationale:** The `fetch` API is a more modern, robust, and reliable standard for making web requests compared to the legacy `XMLHttpRequest`. It often resolves complex or hard-to-debug issues in proxied development environments where requests can hang or fail silently. By making this a project-wide standard, we improve development stability and align with modern web practices.

**Implications:** This change has no negative impact on existing application logic. Angular's `HttpClient` provides a powerful abstraction layer that normalizes the behavior of the underlying transport. All existing error handling (e.g., `catchError` for `4xx`/`5xx` statuses) and success callbacks will continue to function identically. The primary benefit is a more stable and predictable development experience.

---

## Formalizing the "Stateful Service" Pattern for Asynchronous Operations (2025-06-25 19:23:34-05:00)

*   **Context:** The post-mortem review for the Phase 4 contract listing feature identified the `ContractSearch` service as a "gold standard" implementation for managing state derived from asynchronous operations triggered by user input (e.g., search/filtering).
*   **Problem:** This pattern, which uses a signal-based service with an RxJS pipeline featuring `debounceTime` and `switchMap` to prevent race conditions, was not formally documented in the project's design guides. This created a risk of inconsistent or less robust implementations in future features.
*   **Decision:** To ensure consistency, promote best practices, and reduce future development risks, this "Stateful Service" pattern will be formalized as the standard approach for such scenarios.
*   **Action:** The `design/angular/guides/04-state-management-and-rxjs.md` document was updated with a new section (3.3) that explicitly details this pattern. The section outlines the core principles and includes a code sample from the `ContractSearch` service as the canonical example for AI and human developers to follow.
*   **Rationale:** Formalizing proven, successful patterns in design documentation is crucial for maintaining code quality, ensuring architectural consistency, and providing clear, actionable guidance for the development team (both human and AI). This update codifies a key learning from Phase 4, making the entire project more robust.

---

## Ad-hoc Frontend Utility: ISK Formatting Pipe (Approx. 2025-06-25 20:02:07-05:00)

*   **Context:** During the development and debugging of the contract browsing UI, a need arose to format large numerical values (e.g., contract prices) into a human-readable ISK format (e.g., "1.23B ISK", "500.00K ISK"). This was implemented outside of a formal task file to address an immediate UI requirement.
*   **Decision & Implementation:** A reusable Angular pipe, `IskPipe`, was created.
    *   **Location:** `app/frontend/angular/src/app/shared/pipes/isk.pipe.ts`
    *   **Architecture:** Implemented as a standalone, pure pipe for optimal performance. It transforms a number into a string with appropriate suffixes (K, M, B, T) and two decimal places.
*   **Rationale:**
    *   **Reusability & Consistency:** Creating a shared pipe ensures that ISK values are formatted consistently across the entire application.
    *   **Maintainability:** Centralizes the formatting logic in one place, making it easy to update or modify in the future.
    *   **Cleanliness:** Keeps presentation logic out of component class files, adhering to Angular best practices.
*   **Documentation:** This design log entry serves as the official record for this ad-hoc feature work, ensuring its visibility for future development and team awareness.

---

DESIGN_LOG_FOOTER_MARKER_V1 :: *(End of Design Log. New entries are appended above this line.)* Entry heading timestamp format: YYYY-MM-DD HH:MM:SS-05:00 (e.g., 2025-06-06 09:16:09-05:00))*
