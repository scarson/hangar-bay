# Hangar Bay - MVP Implementation Plan Overview

**Last Updated:** 2025-06-08 <!-- To be updated manually or by AI as plan evolves -->

## 1. Introduction

This document outlines the implementation plan for the Minimum Viable Product (MVP) of the Hangar Bay application. The MVP focuses on features F001 (Public Contract Aggregation & Display), F002 (Ship Browsing & Advanced Search/Filtering), and F003 (Detailed Ship Contract View). These features are public-facing and do not require user authentication (F004) for their core MVP functionality.

This plan is designed to be used by AI coding assistants (specifically Cascade) and human developers. It breaks down the MVP development into manageable phases and tasks, each detailed in separate Markdown files.

**Key Project Specifications to Reference:**
*   Main Design: `/design/specifications/design-spec.md`
*   Feature Index: `/design/features/feature-index.md`
*   F001: `/design/features/F001-Public-Contract-Aggregation-Display.md`
*   F002: `/design/features/F002-Ship-Browsing-Advanced-Search-Filtering.md`
*   F003: `/design/features/F003-Detailed-Ship-Contract-View.md`
*   Security: `/design/specifications/security-spec.md`
*   Testing: `/design/specifications/test-spec.md`
*   Observability: `/design/specifications/observability-spec.md`
*   Accessibility: `/design/specifications/accessibility-spec.md`
*   Internationalization (i18n): `/design/specifications/i18n-spec.md`

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
    *   [00.3 Backend PDM Migration](./phase-00-foundational-setup/00.3-backend-pdm-migration.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   PDM initialized in `app/backend/`; `pyproject.toml` and `pdm.lock` created/configured.
            *   Backend dependencies migrated to PDM, `requirements.txt` deleted.
            *   PDM scripts for `lint`, `format`, `dev` created and functional (including `--app-dir src` fix for `dev`).
            *   Root `.gitignore` updated for PDM files.
            *   Main `README.md` updated with PDM setup instructions.
            *   Cross-Cutting Concerns (CCC) Review section in task plan (`00.3-backend-pdm-migration.md`) completed.
            *   **Git:** All changes committed (Commit ID: 2670d0197d7aa6ab2335ff9db79fd83e4eb521f0).

*   **Phase 0 Summary:** All foundational setup tasks, including project initialization, tooling, configuration management, and PDM migration, are now complete. Tasks `00.1`, `00.2`, and `00.3` have undergone their Cross-Cutting Concerns reviews. The project is ready to proceed to Phase 1: Backend Core Infrastructure.

### Phase 1: Backend Core Infrastructure
*   **Goal:** Set up the fundamental backend components: FastAPI application, database connectivity, and caching layer.
*   **Tasks:**
    *   [01.1 FastAPI Application Skeleton](./phase-01-backend-core-infrastructure/01.1-fastapi-app-skeleton.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   FastAPI application skeleton established in `app/backend/src/fastapi_app/`.
            *   `main.py` created with FastAPI app instance, root (`/`) and `/health` endpoints.
            *   Pydantic settings integrated via `config.py`, loading from `.env`.
            *   Subdirectories `routers/`, `models/`, `services/` created with `__init__.py` files.
            *   Application package renamed from `fastapi` to `fastapi_app` to resolve import conflicts.
            *   Application confirmed runnable with Uvicorn: `uvicorn fastapi_app.main:app --reload`.
            *   Task plan (`01.1-fastapi-app-skeleton.md`) and design log (`design/design-log.md`) updated to reflect `fastapi_app` naming.
        *   Cross-Cutting Concerns (CCC) Review section in task plan (`01.1-fastapi-app-skeleton.md`) completed and documented.
        *   **Git:** All changes committed (Commit ID: 0995833).
    *   [01.2 Database Setup](./phase-01-backend-core-infrastructure/01.2-database-setup.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   SQLAlchemy models defined for initial schema.
            *   Alembic initialized; initial migration script generated and applied.
            *   Database connection (`DATABASE_URL`) configured via Pydantic settings and `.env`.
            *   FastAPI application successfully connects to the PostgreSQL database.
            *   Basic database health check or test query implemented.
            *   Cross-Cutting Concerns (CCC) Review section in task plan (`01.2-database-setup.md`) completed.
            *   **Git:** All changes committed (Commit ID: 2670d0197d7aa6ab2335ff9db79fd83e4eb521f0).
    *   [01.3 Valkey Caching Layer Integration](./phase-01-backend-core-infrastructure/01.3-valkey-cache-integration.md)

### Phase 2: Backend - F001: Public Contract Aggregation
*   **Goal:** Implement the core logic for fetching, processing, and storing public EVE Online contract data, and expose it via API endpoints.
*   **Tasks:**
    *   [02.1 ESI API Client (Public Endpoints)](./phase-02-backend-f001-public-contract-aggregation/02.1-esi-client-public.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   ESI client refactored into `ESIClient` class in `core/esi_client_class.py`.
            *   Handles ETag caching with `redis.asyncio.Redis`.
            *   Fetches public contracts, items, universe types, market groups, regions.
            *   Robust error handling (e.g., `ESINotModifiedError`) and graceful degradation for cache issues.
            *   `httpx.AsyncClient` lifecycle managed in FastAPI app.
            *   Configuration via Pydantic settings (`ESI_BASE_URL`, `ESI_USER_AGENT`).
        *   Cross-Cutting Concerns (CCC) Review section in task plan (`02.1-esi-client-public.md`) completed and documented.
        *   **Git:** All changes committed (Commit ID: [To be filled by User after commit]).
    *   [02.2 Data Models for F001](./phase-02-backend-f001-public-contract-aggregation/02.2-data-models-f001.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   SQLAlchemy ORM models defined: `Contract`, `ContractItem`, `EsiTypeCache`, `EsiMarketGroupCache`, `EsiRegionCache`.
            *   Alembic migrations created and applied for database schema.
            *   Relationships and F001-specific fields (e.g., `is_ship_contract`) implemented.
        *   Cross-Cutting Concerns (CCC) Review section in task plan (`02.2-data-models-f001.md`) completed and documented.
        *   **Git:** All changes committed (Commit IDs: 5a6d9f5 (docs: Complete Phase 2 implementation plan updates and reviews), f2eb488 (feat: Implement Phase 2 Backend - F001 Public Contract Aggregation)).
    *   [02.3 Background Aggregation Service](./phase-02-backend-f001-public-contract-aggregation/02.3-background-aggregation-service.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   `APScheduler` with `AsyncIOScheduler` and `RedisJobStore` integrated.
            *   `ContractAggregationService` in `services/background_aggregation.py` implements core aggregation logic.
            *   Redis-based concurrency lock for job runs.
            *   Fetches, processes, and stores contract data for configured regions.
            *   Includes ID-to-name resolution, ship contract identification logic, and `EsiTypeCache` management.
            *   Detailed structured logging and robust error handling (e.g., `AGGREGATION_REGION_IDS` parsing, missing ESI fields).
        *   Cross-Cutting Concerns (CCC) Review section in task plan (`02.3-background-aggregation-service.md`) completed and documented.
        *   **Git:** All changes committed (Commit ID: [To be filled by User after commit]).
    *   [02.4 API Endpoints for F001](./phase-02-backend-f001-public-contract-aggregation/02.4-api-endpoints-f001.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   Pydantic response schemas defined in `schemas/contract.py` and `schemas/market.py`.
            *   FastAPI `APIRouter`s for contracts and ships created and integrated.
            *   `GET /api/v1/contracts/ships` endpoint with filtering and pagination.
            *   `GET /api/v1/ships/market_groups` endpoint.
            *   Endpoints use SQLAlchemy for queries and transform results to Pydantic schemas.
            *   Input validation for query parameters.
        *   Cross-Cutting Concerns (CCC) Review section in task plan (`02.4-api-endpoints-f001.md`) completed and documented.
        *   **Git:** All changes committed (Commit ID: [To be filled by User after commit]).

*   **Phase 2 Summary:** All backend tasks for F001 (Public Contract Aggregation) are complete. This includes the ESI client, data models, background aggregation service, and API endpoints. The system can now periodically fetch EVE Online public contract data, process it, store it, and expose it via a filterable, paginated API. All associated task plans have had their Cross-Cutting Concerns reviews completed. The backend is stable and ready for frontend integration for F001 features.

### Phase 3: Frontend Core Infrastructure
*   **Goal:** Establish a modern, standalone, zoneless Angular frontend application structure, including the API communication layer and basic layout, ready for feature development.
*   **Tasks:**
    *   [03.0 Angular Project Initialization](./phase-03-frontend-core-infrastructure/03.0-angular-project-initialization.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   New Angular project generated with modern defaults: standalone, zoneless, strict, SCSS, custom 'hgb' prefix.
            *   Prettier, ESLint, and `@angular/localize` (for i18n) installed and configured.
            *   Global CSS reset applied in `styles.scss`.
            *   `shared/` directory structure established for reusable components.
            *   `npm audit` confirmed zero vulnerabilities.
    *   [03.1 Angular Core Configuration](./phase-03-frontend-core-infrastructure/03.1-angular-core-module-setup.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   Application configured for zoneless change detection via `provideZonelessChangeDetection()` in `app.config.ts`.
            *   `HttpClient` provided for the application.
            *   Unit tests for `app.config.ts` created and passing, verifying the zoneless setup.
            *   Shared subdirectories (`components`, `directives`, `pipes`, `utils`) scaffolded with `.gitkeep` files.
    *   [03.2 Backend API Service Layer](./phase-03-frontend-core-infrastructure/03.2-backend-api-service-layer.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   `ContractApi` service created for interacting with the backend contract endpoints.
            *   Service tests implemented using `HttpTestingController` to mock backend responses.
            *   Codebase refactored to align with modern Angular conventions (e.g., `ContractApi` instead of `ContractApiService`).
    *   [03.3 Basic Layout, Routing, and Navigation](./phase-03-frontend-core-infrastructure/03.3-basic-layout-routing-navigation.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   `Header` and `Footer` layout components integrated into the main `app.html` shell.
            *   `HomeComponent` created and set as the default route (`/`).
            *   Navigation links in the header use `routerLink` and `routerLinkActive`.
            *   User-facing text marked with `i18n` attributes.
            *   All component and application tests are passing with 100% coverage.

*   **Phase 3 Summary:** The entire frontend core infrastructure is now complete and built on a modern, robust, and scalable foundation. The application is zoneless, uses standalone components, has a clean project structure, includes a data service layer for backend communication, and features a basic, fully tested layout with routing. The project is now prepared for feature-specific UI development in Phase 4.

### Phase 4: Frontend - F001/F002: Contract Listing & Basic Filtering
*   **Goal:** Develop the UI for displaying contracts and implementing initial filtering capabilities.
*   **Tasks:**
    *   [04.1 Contract List Component](./phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.1-contract-list-component.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   **Component:** `ContractBrowsePage` created to display contract data, loading/error states, and pagination.
            *   **State Management:** `ContractSearch` service implemented using a reactive, signal-based approach (`Subject` + `signal`) to manage application state, as defined in the `zoneless-state-management-service.md` pattern.
            *   **Routing:** `ContractFilterResolver` implemented to handle initial data loading via route resolution.
            *   **Testing:** Comprehensive unit and integration tests written for the service, component, and resolver. Notably, this involved overcoming challenges with `TestScheduler` in a zoneless environment, leading to a robust testing pattern using an RxJS `Subject` instead of `toObservable`.
            *   **Cross-Cutting Concerns (CCC):** Full CCC review completed and documented in the task file, including accessibility and i18n attributes.
    *   [04.2 Table Layout and Pipes](./phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.2-table-layout-and-pipes.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   **UI Refactor:** `ContractBrowsePage` refactored from a card layout to a semantic HTML `<table>` for improved accessibility and data presentation.
            *   **Pipes:** Created and tested two new standalone, reusable pipes: `Isk` (for compact ISK currency formatting) and `TimeLeft` (for human-readable relative time).
            *   **Testing:** Addressed a testing gap by implementing a comprehensive integration test suite for `ContractBrowsePage`. The suite validates component rendering, state changes, pipe transformations, and user interactions, ensuring the component is robust and production-ready.
    *   [04.3 Basic Filtering UI](./phase-04-frontend-f001-f002-contract-listing-basic-filtering/04.3-basic-filtering-ui.md)
        *   **Status:** Completed
        *   **Key Outcomes & Artifacts:**
            *   **Filter UI:** Added a dropdown (`<select>`) control to the `ContractBrowsePage` to allow users to filter contracts by type (Item Exchange, Auction, etc.).
            *   **State Management:** Extended the `ContractSearch` service and `ContractSearchFilters` model to handle the new `type` parameter.
            *   **URL Integration:** The `contractFilterResolver` now reads the `type` from the URL query parameters, allowing filter state to be bookmarkable and shareable.
            *   **Testing:** Added unit tests for the new logic in the service and resolver to ensure correctness.
        

*   **Phase 4 Summary:** The first feature slice of the frontend is complete. Users can now view, search, and paginate through public contracts. The implementation successfully applied the project's core architectural patterns for state management and testing in a modern zoneless Angular environment. The key challenge of testing complex RxJS pipelines with `TestScheduler` was resolved, creating a valuable pattern for future development. The project is ready to proceed with more advanced features.

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
