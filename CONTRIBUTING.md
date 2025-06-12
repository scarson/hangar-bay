# Contributing to Hangar Bay

First off, thank you for considering contributing to Hangar Bay! Whether you're a human developer or an AI assistant, your help is appreciated. This document provides guidelines to ensure a smooth and effective contribution process.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Cloning the Repository](#cloning-the-repository)
- [Development Environment Setup](#development-environment-setup)
  - [Backend Setup (Python/FastAPI)](#backend-setup-pythonfastapi)
  - [Frontend Setup (Angular)](#frontend-setup-angular)
  - [Running Linters and Formatters](#running-linters-and-formatters)
  - [Using Docker for Services](#using-docker-for-services-optional-but-recommended)
- [Coding Standards](#coding-standards)
- [Version Control Workflow](#version-control-workflow)
  - [Branching Strategy](#branching-strategy)
  - [Commit Messages](#commit-messages)
  - [Pull Requests (PRs)](#pull-requests-prs)
- [Testing](#testing)
- [Dependency Management](#dependency-management)
- [Issue Tracking](#issue-tracking)
- [Code Review Guidelines](#code-review-guidelines)
- [AI Assistant Guidance](#ai-assistant-guidance)
  - [1. Project Overview for AI Assistants](#1-project-overview-for-ai-assistants)
  - [2. How to Use These Specifications (AI Focus)](#2-how-to-use-these-specifications-ai-focus)
  - [3. Key Technologies (AI Focus)](#3-key-technologies-ai-focus)
  - [4. Development Workflow with AI](#4-development-workflow-with-ai)
  - [5. AI Prompts - Best Practices for Hangar Bay](#5-ai-prompts---best-practices-for-hangar-bay)

## Code of Conduct

(Placeholder: Link to or include a Code of Conduct if one is adopted for the project.)

## Getting Started

### Prerequisites

*   **Git:** For version control.
*   **Python:** Version 3.10 or higher recommended.
*   **Node.js:** Version 18.x (LTS) or higher recommended, which includes npm (Node Package Manager).
*   **Angular CLI:** Install globally after Node.js: `npm install -g @angular/cli`
*   **PostgreSQL:** Version 15 or 16. Required if not using Docker for the database. (See Backend Setup for details).
*   **(Optional but Recommended) Docker:** For running PostgreSQL and Valkey in containers, matching the production environment.

### Cloning the Repository
```bash
git clone <repository_url> # Replace <repository_url> with the actual URL
cd hangar-bay
```

## Development Environment Setup

This section outlines the steps to set up the development environment for Hangar Bay, covering both the Python backend and the Angular frontend.

### Backend Setup (Python/FastAPI)

1.  **Navigate to Backend Directory:**
    ```bash
    cd app/backend
    ```

2.  **Create and Activate a Virtual Environment:**
    *   Using `venv` (Python's built-in module):
        ```bash
        python -m venv .venv # This creates the .venv folder inside app/backend/
        # On Windows
        .\.venv\Scripts\activate
        # On macOS/Linux
        source .venv/bin/activate
        ```
    *   Ensure your `.gitignore` file at the project root ignores `.venv/`.

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt # For development-specific tools
    ```
    *(Note: Ensure `requirements.txt` and `requirements-dev.txt` are kept up-to-date and all dependencies are pinned as per project policy.)*

4.  **Setting up PostgreSQL (Local Installation):**
    If you are not using Docker for database services (see [Using Docker for Services](#using-docker-for-services-optional-but-recommended)), you'll need to install and configure PostgreSQL locally.

    *   **Download and Install PostgreSQL:**
        *   Download PostgreSQL from the [official website](https://www.postgresql.org/download/). Version 15 or 16 is recommended.
        *   Follow the installation instructions for your operating system. Ensure the PostgreSQL command-line tools (like `psql`) are added to your system's PATH.

    *   **Create Database and User:**
        Once PostgreSQL is installed and the service is running, connect to PostgreSQL using `psql` (you might need to do this as the `postgres` superuser initially) and run the following commands:
        ```sql
        CREATE DATABASE hangar_bay_dev;
        CREATE USER hangar_bay_user WITH PASSWORD 'your_secure_password_here'; -- Choose a strong password
        GRANT ALL PRIVILEGES ON DATABASE hangar_bay_dev TO hangar_bay_user;
        ALTER USER hangar_bay_user CREATEDB; -- Optional: useful if user needs to create/drop DBs for tests
        ```
        *Note: Remember the password you set for `hangar_bay_user` as you'll need it for the `.env` file in the next step.*

    *   **Ensure PostgreSQL Service is Running:**
        Make sure your PostgreSQL server is running before proceeding to the next steps or trying to run the application.

5.  **Set up Environment Variables:**
    *   Create a `.env` file in the `app/backend` directory (this file is ignored by Git).
    *   Populate it with necessary configurations (e.g., database URLs, API keys, ESI client ID/secret). Refer to `app/backend/src/config.py` for how these environment variables are loaded and used.
    *   Example `.env` structure:
        ```env
        DATABASE_URL="postgresql+asyncpg://user:password@host:port/database"
        VALKEY_URL="valkey://localhost:6379/0"
        # ESI Configuration
        ESI_CLIENT_ID="YOUR_ESI_CLIENT_ID"
        ESI_SECRET_KEY="YOUR_ESI_SECRET_KEY"
        ESI_CALLBACK_URL="http://localhost:4200/auth/callback" # Or your frontend dev callback
        # JWT Configuration
        JWT_SECRET_KEY="YOUR_VERY_STRONG_JWT_SECRET_KEY" # Should be a long, random string
        JWT_ALGORITHM="HS256"
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
        JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
        # ... other application secrets
        ```

6.  **Database Migrations (Alembic):**
    *(These commands assume Alembic is set up in `app/backend/src/alembic/`)*
    ```bash
    # From app/backend directory
    # To generate a new migration script after model changes:
    # alembic revision -m "short_description_of_changes"
    # Then edit the generated script in app/backend/src/alembic/versions/
    # To apply migrations:
    alembic upgrade head
    ```

7.  **Running the Backend Server (Uvicorn):**
    From the `app/backend` directory:
    ```bash
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
    ```
    *(Assumes your FastAPI app instance is named `app` in `src/main.py`)*

### Frontend Setup (Angular)

1.  **Navigate to Frontend Directory:**
    From the project root:
    ```bash
    cd app/frontend/angular
    ```

2.  **Install Dependencies:**
    If you haven't already (e.g., during `ng new` or `ng add`):
    ```bash
    npm install
    ```
    *(Ensure `package-lock.json` is committed and all dependencies in `package.json` are pinned as per project policy.)*

3.  **Set up Environment Variables:**
    *   Angular uses environment files in `src/environments/`.
    *   `environment.ts` is for development.
    *   `environment.prod.ts` is for production.
    *   Ensure `apiUrl` in `environment.ts` points to your local backend (e.g., `http://localhost:8000/api/v1`).

4.  **Running the Frontend Development Server:**
    ```bash
    ng serve
    ```
    This will typically start the Angular development server on `http://localhost:4200/`.

### Running Linters and Formatters

*   **Backend (Python):**
    *(Assumes Flake8 and Black are installed in the virtual environment, as per `requirements-dev.txt`)*
    From `app/backend` directory:
    ```bash
    flake8 ./src
    black ./src
    ```

*   **Frontend (Angular):**
    From `app/frontend/angular` directory:
    ```bash
    npm run lint  # Runs ESLint
    npm run format # Runs Prettier (ensure this script exists in package.json)
    # Or run Prettier directly:
    # npx prettier --write .
    ```

### Using Docker for Services (Optional but Recommended)

If you have Docker installed, you can use it to run PostgreSQL and Valkey. A `docker-compose.yml` file is provided in `app/backend/docker/compose.yml` to simplify running these services. To use it, navigate to the `app/backend/docker/` directory and run `docker compose up -d`. Ensure your `.env` file in `app/backend` has the correct `DATABASE_URL` and `VALKEY_URL` to connect to these Docker containers (usually `localhost` or `127.0.0.1` with standard ports).

---

## Coding Standards

*   **General:**
    *   Follow the style enforced by the project's linters and formatters (Black, Flake8 for Python; Prettier, ESLint for Angular/TypeScript).
    *   Write clear, concise, and well-commented code, especially for complex logic.
    *   Aim for readability and maintainability.
*   **Python (Backend):**
    *   Adhere to PEP 8 guidelines.
    *   Use type hints extensively.
    *   Follow FastAPI best practices for structuring routers, models, and services.
*   **TypeScript/Angular (Frontend):**
    *   Follow Angular style guide recommendations.
    *   Use strong typing; avoid `any` where possible.
    *   Structure components, services, and modules logically.
*   **Security:** Strictly adhere to the guidelines in [`design/security-spec.md`](design/security-spec.md).
*   **Accessibility:** Implement frontend components following [`design/accessibility-spec.md`](design/accessibility-spec.md).

## Version Control Workflow

### Branching Strategy

*   **`main`:** This branch represents the latest stable release. Direct commits to `main` are prohibited. Merges to `main` happen only from `develop` during a release.
*   **`develop`:** This is the primary development branch where all completed features are merged. It should always be in a state that could potentially be released.
*   **Feature Branches:** All new development (features, bug fixes, chores) must be done in a feature branch.
    *   Create feature branches from `develop`.
    *   Naming convention: `type/scope/short-description` (e.g., `feat/auth/sso-integration`, `fix/ui/login-button-style`, `chore/docs/update-readme`).
        *   `type`: `feat` (new feature), `fix` (bug fix), `docs` (documentation), `style` (formatting, linting), `refactor`, `perf` (performance), `test`, `chore` (maintenance).
        *   `scope`: (Optional) The part of the project affected (e.g., `auth`, `ui`, `api`, `db`).
*   **Hotfix Branches:** For urgent fixes to `main`, branch from `main` (e.g., `hotfix/critical-security-patch`) and merge back into both `main` and `develop`.

### Commit Messages

*   Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This helps with automated changelog generation and semantic versioning.
*   Example: `feat(api): add endpoint for user profile retrieval`
*   Keep commit messages concise but descriptive. The body of the commit message can provide more detail if needed.

### Pull Requests (PRs)

*   Once a feature branch is complete and tested, create a Pull Request (PR) to merge it into `develop`.
*   **PR Title:** Should be clear and descriptive, often similar to the primary commit message of the feature.
*   **PR Description:**
    *   Summarize the changes made.
    *   Explain the "why" behind the changes.
    *   Link to any relevant issues in the issue tracker (e.g., "Closes #123").
    *   Include steps for testing or screenshots/GIFs for UI changes if applicable.
*   Ensure all CI checks (linters, tests) pass before requesting a review.
*   At least one other developer should review and approve the PR before merging.
*   Delete the feature branch after the PR is merged.

## Testing

*   Adhere to the testing strategies outlined in [`design/test-spec.md`](design/test-spec.md).
*   **Unit Tests:** All new functions, methods, and components should have corresponding unit tests.
*   **Integration Tests:** Write integration tests for interactions between components or services, especially for API endpoints.
*   **End-to-End (E2E) Tests:** (To be implemented) For critical user flows.
*   Run all relevant tests locally before pushing changes or creating a PR.
*   Aim for high test coverage.

## 6. Dependency Management

This project follows a strict dependency version pinning policy to ensure reproducible and stable builds. The full policy statement and rationale can be found in [`design/design-spec.md`](design/design-spec.md) (Section 6.0). All developers and AI assistants MUST adhere to the following practices:

*   **Python (Backend):**
    *   All packages listed in `app/backend/requirements.txt` (and any development-specific requirement files like `requirements-dev.txt`) MUST have their exact versions specified.
    *   **Example:** `fastapi==0.100.0`
    *   Add new dependencies to `requirements.in` (and `requirements-dev.in` for dev tools).
    *   Regenerate `requirements.txt` and `requirements-dev.txt` using `pip-compile` from the `pip-tools` package:
        ```bash
        # From app/backend directory
        pip-compile requirements.in -o requirements.txt
        pip-compile requirements-dev.in -o requirements-dev.txt
        ```
    *   Commit both the `.in` and `.txt` files.

*   **JavaScript/TypeScript (Frontend - Angular):**
    *   All packages listed in `app/frontend/angular/package.json` (in both `dependencies` and `devDependencies`) MUST have their versions pinned.
    *   Use `npm install --save-exact <package-name>` or `npm install --save-dev --save-exact <package-name>` to add new dependencies with exact versions to `package.json`.
    *   **Example (in `package.json`):** `"@angular/core": "16.2.0"` (ensure no `^` or `~` prefixes unless a specific, conscious decision is made and documented for a valid reason).
    *   Always commit the `package.json` and `package-lock.json` files.

*   **Containerization (Docker):**
    *   **Base Images:** Dockerfiles (e.g., `app/backend/Dockerfile`, `app/frontend/angular/Dockerfile`) MUST use specific version tags for base images. Avoid using `latest` or broad version tags like `python:3`.
        *   **Example:** `FROM python:3.11.9-slim-buster` (preferred) instead of `FROM python:latest` or `FROM python:3.11`.
    *   **Package Installations within Dockerfiles:** Any packages installed within Dockerfiles using system package managers (e.g., `apt-get` for Debian/Ubuntu, `apk add` for Alpine) SHOULD also have their versions pinned if the package manager supports it and it's practical to do so. This adds an extra layer of reproducibility.
        *   **Example (Debian/Ubuntu):** `RUN apt-get update && apt-get install -y --no-install-recommends mypackage=1.2.3-1ubuntu1`
        *   **Example (Alpine):** `RUN apk add --no-cache mypackage=1.2.3-r0`

*   **Database Systems:**
    *   While not typically pinned in a version control file in the same way as application dependencies, ensure that the major version of database systems like PostgreSQL used in development, testing, and production environments is consistent and explicitly chosen (e.g., PostgreSQL 15.x). This is usually managed through Docker image selection for development (e.g., `postgres:15-alpine`) or infrastructure-as-code for deployed environments.

## Issue Tracking

*   (Placeholder: Describe how issues are tracked, e.g., GitHub Issues. Include guidance on reporting bugs, suggesting features, and using labels.)

## Code Review Guidelines

*   (Placeholder: Provide guidelines for both authors and reviewers. e.g., Reviewers should check for correctness, adherence to standards, security, performance, readability. Authors should be responsive to feedback.)

---

## AI Assistant Guidance

This section provides guidance for AI coding assistants to effectively contribute to the Hangar Bay project.

### 1. Project Overview for AI Assistants

Hangar Bay is an EVE Online in-game asset marketplace, focusing initially on ship sales. The primary goal is to create a functional, secure, and user-friendly platform leveraging EVE Online's ESI API for game data and authentication.

**Core Technologies:**
*   **Backend:** Python with FastAPI
*   **Frontend:** Angular
*   **Database:** PostgreSQL (with SQLite for local development/testing)
*   **Caching:** Valkey
*   **Authentication:** EVE SSO (OAuth 2.0)

### 2. How to Use These Specifications (AI Focus)

The [`design/`](design/) directory is your primary source of truth for requirements and implementation details. Key documents include:

*   [`design-spec.md`](design/design-spec.md): Overall architecture, features, and technology choices. Contains AI notes for high-level understanding.
*   [`features/`](design/features/): Individual feature specifications (e.g., `F001-*.md`, `F002-*.md`).
    *   These files detail specific application functionalities.
    *   **Key Structure:** Each feature spec now consistently includes a "0. Authoritative ESI & EVE SSO References" section at the beginning and AI actionable checklists for all defined ESI, EVE SSO, and Hangar Bay API endpoints.
    *   The `00-feature-spec-template.md` shows the overall template, including how data models, API endpoints, and general AI implementation guidance are structured. Use this template as a base when creating entirely new features.
*   [`security-spec.md`](design/security-spec.md): Detailed security requirements with AI actionable checklists and implementation patterns. Prioritize these strictly.
*   [`accessibility-spec.md`](design/accessibility-spec.md): Accessibility (WCAG 2.1 AA) requirements with AI actionable checklists and Angular-specific patterns.
*   [`test-spec.md`](design/test-spec.md): Testing strategy, including unit, integration, E2E, security, and accessibility testing, with AI patterns for test generation.
*   [`observability-spec.md`](design/observability-spec.md): Logging, metrics, and tracing strategy, emphasizing OpenTelemetry, with AI patterns for instrumentation.
*   [`i18n-spec.md`](design/i18n-spec.md): Internationalization strategy, including guidance for localizing FastAPI and Angular components, and AI patterns for generating translatable content.
*   [`performance-spec.md`](design/performance-spec.md): Performance targets, design principles, testing methodologies, and AI guidance for backend (FastAPI, Valkey, PostgreSQL) and frontend (Angular) development.
*   [`ai-system-procedures.md`](design/ai-system-procedures.md): Documents "AI System Procedures" (AISPs) – significant, recurring operational patterns for AI execution or participation.
    *   **Purpose:** AISPs provide a human-readable design record, detailing the problem, rationale, trigger conditions, AI execution steps, expected outcomes, and supporting details for complex or critical AI-involved workflows.
    *   **Usage:** While operational logic might be stored in AI memories, AISPs offer deeper context and step-by-step guidance. Refer to them to understand the 'why' and 'how' of these procedures. The document includes an `[AISP-000] AISP Entry Template` to guide the creation of new AISP entries.

**AI Action:** Before generating code for a feature or component, always consult the relevant specification documents. Pay close attention to sections titled `AI Implementation Guidance`, `AI Actionable Checklist`, or `AI Implementation Pattern` as they provide direct instructions and context.

### 3. Key Technologies (AI Focus)

*   **FastAPI (Backend):**
    *   Utilize Pydantic for request/response models and data validation.
    *   Employ dependency injection (`Depends`) for authentication and shared services.
    *   Follow RESTful API design principles.
    *   Refer to `security-spec.md` for input validation and `observability-spec.md` for OpenTelemetry integration patterns.
*   **Angular (Frontend):**
    *   Use typed forms (Reactive Forms preferred).
    *   Implement services for API communication and state management.
    *   Adhere to component-based architecture.
    *   Refer to `accessibility-spec.md` for ARIA, focus management, and Material component guidance.
    *   Refer to `observability-spec.md` for OpenTelemetry integration patterns.
*   **SQLAlchemy (Database ORM):**
    *   Define models in `app/backend/src/models/` (or similar conventional path).
    *   Use Alembic for database migrations.
    *   Avoid raw SQL; use ORM capabilities for security (see `security-spec.md`).
*   **OpenTelemetry:**
    *   Instrument both backend and frontend for distributed tracing, metrics, and correlation with logs as per `observability-spec.md`.

### 4. Development Workflow with AI

1.  **Understand Requirements:** Review the relevant feature spec(s) and related design documents (`security-spec.md`, `accessibility-spec.md`, etc.).
2.  **Clarify Ambiguities:** If a spec is unclear, ask for clarification before coding.
3.  **Generate Code:** Based on the specs, generate:
    *   Backend: FastAPI models, API route handlers, service logic, database models, tests.
    *   Frontend: Angular components, services, templates, styles, tests.
4.  **Incorporate AI Guidance:** Actively use the `AI Implementation Guidance`, checklists, and patterns from the specs.
5.  **Testing:** Generate unit and integration tests as per `test-spec.md`. Include accessibility and security considerations in tests.
6.  **Review & Iterate:** The generated code will be reviewed. Be prepared to make adjustments based on feedback.

### 5. AI Prompts - Best Practices for Hangar Bay

*   **Be Specific:** Instead of "Create an API endpoint," try "Create a FastAPI GET endpoint at `/users/{user_id}` that retrieves user data based on the Pydantic model `UserRead` from `user_models.py`, ensuring it requires authentication and includes OpenTelemetry tracing as per `observability-spec.md`."
*   **Reference Specifications:** Explicitly mention which spec document and section your request relates to (e.g., "Implement input validation for the `ContractCreate` model as outlined in `security-spec.md`, section 3.1.").
*   **Iterative Prompts:** Break down complex tasks. Start with model generation, then API routes, then service logic, then tests.
*   **Request Tests:** Always ask for unit tests, and specify if integration or A11y tests are needed for a particular component.
*   **Focus on AI-Enhanced Specs:** Remind the AI to look for and use the AI-specific sections within the markdown files.
