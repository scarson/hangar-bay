# Hangar Bay - MVP Implementation Plan Overview

**Last Updated:** 2025-06-06 <!-- To be updated manually or by AI as plan evolves -->

## 1. Introduction

This document outlines the implementation plan for the Minimum Viable Product (MVP) of the Hangar Bay application. The MVP focuses on features F001 (Public Contract Aggregation & Display), F002 (Ship Browsing & Advanced Search/Filtering), and F003 (Detailed Ship Contract View). These features are public-facing and do not require user authentication (F004) for their core MVP functionality.

This plan is designed to be used by AI coding assistants (specifically Cascade) and human developers. It breaks down the MVP development into manageable phases and tasks, each detailed in separate Markdown files.

**Key Project Specifications to Reference:**
*   Main Design: `../../design/design-spec.md`
*   Feature Index: `../../design/features/feature-index.md`
*   F001: `../../design/features/F001-Public-Contract-Aggregation-Display.md`
*   F002: `../../design/features/F002-Ship-Browsing-Advanced-Search-Filtering.md`
*   F003: `../../design/features/F003-Detailed-Ship-Contract-View.md`
*   Security: `../../design/security-spec.md`
*   Testing: `../../design/test-spec.md`
*   Observability: `../../design/observability-spec.md`
*   Accessibility: `../../design/accessibility-spec.md`
*   Internationalization (i18n): `../../design/i18n-spec.md`

## 2. Development Phases & Tasks

The MVP development is structured into the following phases. Each task links to a detailed plan file.

### Phase 0: Foundational Setup
*   **Goal:** Establish the project structure, development environment, tooling, and core configuration management.
*   **Tasks:**
    *   [00.1 Project Initialization & Tooling](./phase-00-foundational-setup/00.1-project-initialization-tooling.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   **Backend (`app/backend/`):**
                *   Python virtual environment initialized (`.venv/`).
                *   `requirements.txt` generated (includes `flake8`, `black`).
                *   `docker/compose.yml` created for PostgreSQL and Valkey services.
            *   **Frontend (`app/frontend/angular/`):**
                *   Angular project initialized (`ng new`).
                *   Prettier configured (`.prettierrc.json`, `format` script in `package.json`).
                *   ESLint configured (`eslint.config.js` with `@angular-eslint/schematics`, `eslint-config-prettier`).
            *   **Project Root & Design:**
                *   Root `.gitignore` created.
                *   Angular project `.gitignore` confirmed.
                *   `README.md` updated with comprehensive development setup instructions.
                *   `design/design-log.md` updated with Angular CLI option decisions.
                *   `design/memory-index.md` created and populated.
                *   `design/risks.md` created and populated with initial risk (PERF-001).
            *   Cross-Cutting Concerns (CCC) Review section in task plan (`00.1-project-initialization-tooling.md`) completed and documented.
            *   **Git:** All changes committed (Commit ID: a76e187).
    *   [00.2 Configuration Management](./phase-00-foundational-setup/00.2-configuration-management.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   **Backend (`app/backend/`):**
                *   Pydantic `BaseSettings` class implemented for configuration loading from environment variables.
                *   `python-dotenv` integrated for local `.env` file support.
                *   `.env.example` file created with placeholder values.
                *   FastAPI application confirmed to load configuration via `BaseSettings`.
            *   **Frontend (`app/frontend/angular/`):**
                *   Angular environment files (`src/environments/environment.ts`, `src/environments/environment.prod.ts`) structured with `production` flag and `apiUrl`.
            *   **General:**
                *   Strategy for production secrets management (injection via environment) documented in `00.2-configuration-management.md`.
            *   Cross-Cutting Concerns (CCC) Review section in task plan (`00.2-configuration-management.md`) completed and documented.
            *   **Git:** All changes committed (Commit ID: [To be filled by User after commit]).

*   **Phase 0 Summary:** All foundational setup tasks, including project initialization, tooling, and configuration management, are now complete. Both tasks `00.1` and `00.2` have undergone their Cross-Cutting Concerns reviews. The project is ready to proceed to Phase 1: Backend Core Infrastructure.

### Phase 1: Backend Core Infrastructure
*   **Goal:** Set up the fundamental backend components: FastAPI application, database connectivity, and caching layer.
*   **Tasks:**
    *   [01.1 FastAPI Application Skeleton](./phase-01-backend-core-infrastructure/01.1-fastapi-app-skeleton.md)
    *   [01.2 Database Setup](./phase-01-backend-core-infrastructure/01.2-database-setup.md)
    *   [01.3 Valkey Caching Layer Integration](./phase-01-backend-core-infrastructure/01.3-valkey-cache-integration.md)

### Phase 2: Backend - F001: Public Contract Aggregation
*   **Goal:** Implement the core logic for fetching, processing, and storing public EVE Online contract data.
*   **Tasks:**
    *   [02.1 ESI API Client (Public Endpoints)](./phase-02-backend-f001-public-contract-aggregation/02.1-esi-client-public.md)
    *   [02.2 Data Models for F001](./phase-02-backend-f001-public-contract-aggregation/02.2-data-models-f001.md)
    *   [02.3 Background Aggregation Service](./phase-02-backend-f001-public-contract-aggregation/02.3-background-aggregation-service.md)
    *   [02.4 API Endpoints for F001](./phase-02-backend-f001-public-contract-aggregation/02.4-api-endpoints-f001.md)

### Phase 3: Frontend Core Infrastructure
*   **Goal:** Establish the Angular frontend application structure, API communication layer, and basic layout.
*   **Tasks:**
    *   [03.1 Angular Application Skeleton](./phase-03-frontend-core-infrastructure/03.1-angular-app-skeleton.md)
    *   [03.2 Backend API Service Layer](./phase-03-frontend-core-infrastructure/03.2-backend-api-service-layer.md)
    *   [03.3 Basic Layout, Routing, and Navigation](./phase-03-frontend-core-infrastructure/03.3-basic-layout-routing.md)

### Phase 4: Frontend - F001/F002: Contract Listing & Basic Filtering
*   **Goal:** Develop the UI for displaying contracts and implementing initial filtering capabilities.
*   **Tasks:**
    *   [04.1 Contract List Component](./phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.1-contract-list-component.md)
    *   [04.2 Basic Filtering UI](./phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.2-basic-filtering-ui.md)
    *   [04.3 Integrating Basic Filters with Contract List](./phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.3-integrating-filters-with-list.md)

### Phase 5: Backend - F002: Advanced Search & Filtering Logic
*   **Goal:** Enhance backend capabilities to support advanced search and filtering as per F002.
*   **Tasks:**
    *   [05.1 Advanced Filtering Logic & Query Enhancements](./phase-05-backend-f002-advanced-search-filtering-logic/05.1-advanced-filtering-logic.md)
    *   [05.2 Update API Endpoints for F002](./phase-05-backend-f002-advanced-search-filtering-logic/05.2-api-endpoints-f002-update.md)

### Phase 6: Frontend - F002: Advanced Filtering Implementation
*   **Goal:** Implement the advanced filtering interface in the frontend.
*   **Tasks:**
    *   [06.1 Advanced Filtering Component](./phase-06-frontend-f002-advanced-filtering-implementation/06.1-advanced-filtering-component.md)

### Phase 7: Backend - F003: Detailed Ship/Contract View
*   **Goal:** Develop backend support for fetching detailed contract information.
*   **Tasks:**
    *   [07.1 API Endpoint for F003](./phase-07-backend-f003-detailed-ship-contract-view/07.1-api-endpoints-f003.md)

### Phase 8: Frontend - F003: Detailed View Implementation
*   **Goal:** Create the UI for displaying the detailed contract view.
*   **Tasks:**
    *   [08.1 Contract Detail Component](./phase-08-frontend-f003-detailed-view-implementation/08.1-contract-detail-component.md)

### Phase 9: Cross-Cutting Concerns (MVP Scope)
*   **Goal:** Integrate essential non-functional requirements for security, logging, testing, accessibility, and i18n.
*   **Tasks:**
    *   [09.1 Security Hardening (MVP)](./phase-09-cross-cutting-concerns-mvp-scope/09.1-security-hardening-mvp.md)
    *   [09.2 Logging & Basic Observability (MVP)](./phase-09-cross-cutting-concerns-mvp-scope/09.2-logging-observability-mvp.md)
    *   [09.3 Testing Strategy & Implementation (MVP)](./phase-09-cross-cutting-concerns-mvp-scope/09.3-testing-strategy-mvp.md)
    *   [09.4 Accessibility & i18n Stubs (MVP)](./phase-09-cross-cutting-concerns-mvp-scope/09.4-accessibility-i18n-stubs-mvp.md)

### Phase 10: Deployment & Final Documentation
*   **Goal:** Containerize the application, set up a basic CI/CD pipeline, and finalize project documentation.
*   **Tasks:**
    *   [10.1 Deployment Preparation & Packaging](./phase-10-deployment/10.1-deployment-prep-packaging.md)
    *   [10.2 CI/CD Pipeline Setup](./phase-10-deployment/10.2-ci-cd-pipeline-setup.md)
    *   [10.3 Final Documentation & README Update](./phase-10-deployment/10.3-final-documentation-readme.md)

## 3. General AI Implementation Guidance

*   **Iterative Approach:** While phases are defined, aim for iterative development within tasks. Implement a small piece, test it, and then build upon it.
*   **Refer to Specifications:** Constantly refer back to the linked feature specifications and design documents for detailed requirements.
*   **Code Comments:** Generate clear and concise code comments, especially for complex logic or non-obvious decisions.
*   **Error Handling:** Implement robust error handling as per `design-spec.md` and feature-specific error handling sections.
*   **Security First:** Adhere to guidelines in `security-spec.md` for all code generation.
*   **Testing:** Generate unit tests alongside feature code. Follow guidance in `test-spec.md`.
*   **Integrated Cross-Cutting Concerns:** Beyond the dedicated tasks in Phase 09, all five cross-cutting concerns (Security, Observability, Testing, Accessibility, Internationalization) as detailed in their respective specification documents (`../../design/security-spec.md`, `../../design/observability-spec.md`, `../../design/test-spec.md`, `../../design/accessibility-spec.md`, `../../design/i18n-spec.md`) MUST be proactively and systematically integrated into **every task** throughout Phases 00-08. This is a non-negotiable requirement. Cascade will leverage its AI memories established for this purpose and will complete the mandatory "Cross-Cutting Concerns Review" checklist section within each task file to document how these considerations were applied to the specific work of that task.

## 4. Plan Maintenance

This plan is a living document. It will be updated as development progresses, decisions are refined, or new requirements emerge (though scope creep for MVP should be strictly managed).
