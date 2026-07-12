# Contributing to Hangar Bay

First off, thank you for considering contributing to Hangar Bay! Whether you're a human developer or an AI assistant, your help is appreciated. This document provides guidelines to ensure a smooth and effective contribution process.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Cloning the Repository](#cloning-the-repository)
- [Development Environment Setup](#development-environment-setup)
  - [Backend Setup (Python/FastAPI)](#backend-setup-pythonfastapi)
  - [Backend Dev Prerequisites (Local Run & Tests)](#backend-dev-prerequisites-local-run--tests)
  - [Frontend Setup (React)](#frontend-setup-react)
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
*   **Python:** Version 3.11 or newer for the backend.
*   **PDM (Python Dependency Manager):** For managing backend dependencies. Install it via `pipx install pdm` or `pip install --user pdm`. Refer to [PDM's official documentation](https://pdm-project.org/latest/getting-started/installation/) for more options.
*   **Node.js:** Version 20.19.0 or newer for the React frontend (includes npm).
*   **PostgreSQL:** Version 15 or 16. Required if not using Docker for the database. (See Backend Setup for details).
*   **(Optional but Recommended) Docker:** For running PostgreSQL and Valkey in containers, matching the production environment.

### Cloning the Repository
```bash
git clone <repository_url> # Replace <repository_url> with the actual URL
cd hangar-bay
```

## Development Environment Setup

This section outlines the steps to set up the development environment for Hangar Bay, covering both the Python backend and the React frontend.

### Backend Setup (Python/FastAPI with PDM)

1.  **Navigate to the backend directory:**
    ```bash
    cd app/backend
    ```

2.  **Install dependencies (including development tools like linters/formatters):
    ```bash
    pdm install -G dev
    ```
    This command reads the `pyproject.toml` and `pdm.lock` files, creates a virtual environment (in `.venv/` inside `app/backend/` if you've run `pdm config venv.in_project true`), and installs all necessary packages.

3.  **Activate the virtual environment (optional but recommended for IDEs):
    PDM automatically uses the project's virtual environment when you use `pdm run`. However, if your IDE or other tools need the environment to be explicitly activated, you can find the activation scripts within `app/backend/.venv/` (e.g., `app/backend/.venv/Scripts/activate` on Windows PowerShell/CMD, or `source app/backend/.venv/bin/activate` on Linux/macOS).

4.  **Set up Environment Variables:**
    *   The backend reads its environment from **`app/backend/src/.env`** (this location, not next to the code — Git ignores it). See the [Backend Dev Prerequisites (Local Run & Tests)](#backend-dev-prerequisites-local-run--tests) section below for the exact variables required for a local run and for the test suite (`DATABASE_URL`, `DATABASE_URL_TESTS`, `CACHE_URL`, `ESI_USER_AGENT`, and the JSON-list `AGGREGATION_REGION_IDS`).
    *   How these are loaded is defined in `app/backend/src/fastapi_app/config.py` and `app/backend/src/fastapi_app/core/config.py`.
    *   EVE SSO / JWT variables (`ESI_CLIENT_ID`, `ESI_SECRET_KEY`, `JWT_*`) are **not required for M1** (public contract browsing); they land with the SSO milestone (M2). Do not set them yet.

5.  **Database Migrations (Alembic):**
    *(These commands assume Alembic is set up in `app/backend/src/alembic/`)*
    ```bash
    # From app/backend directory
    # To generate a new migration script after model changes:
    pdm run alembic revision -m "short_description_of_changes"
    # Then edit the generated script in app/backend/src/alembic/versions/
    # To apply migrations:
    pdm run alembic upgrade head
    ```

6.  **Running the Development Server:**
    ```bash
    pdm run dev
    ```
    The FastAPI application should be available at `http://localhost:8000`.

### Backend Dev Prerequisites (Local Run & Tests)

The backend reads its environment from **`app/backend/src/.env`** (this location, not next to `.env.example`). For a local run and for the test suite you need PostgreSQL and Valkey running (see `app/backend/docker/`), plus these variables:

```env
# Local dev database + the scratch database the test suite drops/recreates each run.
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hangar_bay
DATABASE_URL_TESTS=postgresql+asyncpg://postgres:postgres@localhost:5432/hangar_bay_test
# Valkey (Redis-compatible) is required — the aggregation pipeline holds a lock in it.
CACHE_URL=redis://localhost:6379/0
ESI_USER_AGENT=hangar-bay-dev (your-email@example.com)
# MUST be a JSON list. A bare int or comma-separated string crashes at startup.
AGGREGATION_REGION_IDS=[10000002]
```

Notes:

*   **`AGGREGATION_REGION_IDS` must be a JSON list** (e.g. `[10000002]`). pydantic-settings JSON-decodes complex env fields before any field validator runs, so a bare int or comma-separated string fails at startup.
*   **Valkey is required.** The aggregation pipeline takes a TTL-bounded lock in Valkey. If the backend is killed mid-ingestion (for example under `--reload`), the lock stays held until its TTL expires, so the next startup logs "already running" and skips ingestion. During development, clear it with `docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"`. It self-heals in production once the TTL lapses.
*   **Every backend restart drops and recreates all tables** and immediately re-runs aggregation (dev limit: 100 contracts from the configured regions), so real contract data appears a few minutes after boot, not instantly. An empty contract list right after startup is expected, not a frontend bug.
*   **`DATABASE_URL_TESTS`** points at a scratch database the test fixtures drop and recreate on every run — never point it at data you care about. Create it once with `createdb hangar_bay_test` (or via the Docker compose in `app/backend/docker/`).

### Frontend Setup (React)

The React single-page app lives in `app/frontend/web` (Vite + React 19 + TypeScript + Tailwind CSS v4 + TanStack Router/Query).

1.  **Navigate to the frontend directory:**
    From the project root:
    ```bash
    cd app/frontend/web
    ```

2.  **Install Dependencies:**
    ```bash
    npm install
    ```
    *(Ensure `package-lock.json` is committed and all dependencies in `package.json` stay exactly pinned — see [Dependency Management](#dependency-management).)*

3.  **Running the Frontend Development Server:**
    ```bash
    npm run dev
    ```
    The app is served at `http://localhost:5173`, and proxies `/api/v1` requests to the backend on `http://localhost:8000` (no separate API-URL config needed for local dev).

4.  **Regenerating the API client types (after backend schema changes):**
    ```bash
    cd app/backend && pdm run export-openapi    # writes app/frontend/web/openapi.json
    cd app/frontend/web && npm run generate:api  # regenerates src/lib/api/schema.d.ts
    ```

### Running Linters and Formatters

*   **Backend (Python):**
    From the `app/backend` directory:
    ```bash
    pdm run lint  # Runs Flake8
    pdm run format # Runs Black
    ```

*   **Frontend (React):**
    From the `app/frontend/web` directory:
    ```bash
    npm run lint   # ESLint (flat config, with jsx-a11y)
    npm run format # Prettier
    npm run test   # Vitest
    ```

### Using Docker for Services (Optional but Recommended)

If you have Docker installed, you can use it to run PostgreSQL and Valkey. A compose file is provided at `app/backend/docker/compose.yml` to simplify running these services. To use it, navigate to the `app/backend/docker/` directory and run `docker compose up -d`. Ensure your `app/backend/src/.env` file has the correct `DATABASE_URL` and `CACHE_URL` (Valkey/Redis) to connect to these Docker containers (usually `localhost` or `127.0.0.1` with standard ports).

---

## Coding Standards

*   **General:**
    *   Follow the style enforced by the project's linters and formatters (Black, Flake8 for Python; Prettier, ESLint for React/TypeScript).
    *   Write clear, concise, and well-commented code, especially for complex logic.
    *   Aim for readability and maintainability.
*   **Python (Backend):**
    *   Adhere to PEP 8 guidelines.
    *   Use type hints extensively.
    *   Follow FastAPI best practices for structuring routers, models, and services.
*   **TypeScript/React (Frontend):**
    *   Follow the conventions enforced by ESLint (flat config) + Prettier.
    *   Use strong typing (TypeScript strict mode); avoid `any` where possible.
    *   Structure components and hooks logically; keep server state in TanStack Query and URL/filter state in TanStack Router search params.
*   **Security:** Strictly adhere to the guidelines in [`design/specifications/security-spec.md`](design/specifications/security-spec.md).
*   **Accessibility:** Implement frontend components following [`design/specifications/accessibility-spec.md`](design/specifications/accessibility-spec.md).

## Version Control Workflow

This project runs a **two-branch gitflow**. The canonical, authoritative rules — invariants, the worktree lifecycle, recovery procedures, merge authority, and the publication mechanic — live in [`docs/git-strategy.md`](docs/git-strategy.md). This section is the short form; where the two ever disagree, `docs/git-strategy.md` wins.

*   **`dev` (integration branch):** The GitHub default branch and the target of **every** feature, fix, and docs PR. It should always be in a releasable state. Do not commit to `dev` directly — it advances only by fetching and resetting to `origin/dev` after PRs merge on GitHub.
*   **`main` (release branch):** The published state of the project. No direct commits, no feature branches targeting it, no hotfixes landing on it directly. `main` advances **only** via deliberate `dev` → `main` publication PRs (see [`docs/git-strategy.md`](docs/git-strategy.md) §Release branch). There is no `develop` branch — if you have an old clone that predates the switch, run the one-time bootstrap in §One-time bootstrap of that doc.
*   **Work happens in worktrees, not the root checkout.** Create an isolated worktree + branch in one step: `git worktree add .claude/worktrees/<slug> -b <branch-name>`. Branches are ephemeral — branch → work → PR → merge → delete, in the session that merges. See [`docs/git-strategy.md`](docs/git-strategy.md) §Day-one workflow.
*   **Branch naming:** conventional prefixes drawn from the Conventional Commits vocabulary — `feat/*`, `fix/*`, `docs/*`, `refactor/*`, `perf/*`, `test/*`, `chore/*`, and `audit/*` for long-cycle campaigns. Optionally group with a scope: `feat/auth/sso-integration`, `fix/ui/login-button-style`. **Agent sessions** use the `claude/<topic>-<suffix>` namespace (e.g. `claude/m2-eve-sso-6a7202`); a `claude/*` branch is not a separate category — it maps onto whichever conventional type its work carries.

### Commit Messages

*   Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This helps with automated changelog generation and semantic versioning.
*   Example: `feat(api): add endpoint for user profile retrieval`
*   Keep commit messages concise but descriptive. The body of the commit message can provide more detail if needed.

### Pull Requests (PRs)

*   Once a branch is complete and tested, open a PR targeting **`dev`**: `gh pr create --base dev --fill` (or supply a full title/body). The `--base dev` is required — without it `gh` falls back to the repo default, which in older clones still resolves to `main`.
*   **PR Title:** Clear and descriptive; follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat(api): add contract detail endpoint`).
*   **PR Description:**
    *   Summarize the changes and explain the "why."
    *   Link relevant issues (e.g., "Closes #123").
    *   Include testing steps or screenshots/GIFs for UI changes where applicable.
*   **Every PR body MUST include a `## Merge classification` heading** with exactly one of:
    *   `Routine — auto-merge on green CI` — docs, tests, mechanical refactors, non-sensitive bug fixes, plan-reviewed features.
    *   `Review — <trigger>` — the change touches a sensitive domain (auth/secrets/crypto/injection guards, data-integrity paths, or architecture: public interfaces, serialization/wire contracts, DB schema, external API contracts).
    *   `Escalate — <concern>` — implementation surfaced something needing a maintainer's judgment (CI revealed a design issue, a substantive merge conflict, scope drift, or any other surprise).
    *   A missing classification defaults to `Review`. Full definitions: [`docs/git-strategy.md`](docs/git-strategy.md) §Merge authority.
*   **Merging:**
    *   Ensure CI is green first; wait for it with a monitoring tool, not a sleep-poll loop.
    *   `Routine` PRs are **self-merged by the author** (human or agent) once CI is green — click-to-approve with no real review is not required and adds no independence. `Review`/`Escalate` PRs are merged by a maintainer (Sam) after their judgment is applied.
    *   Always merge with a true merge commit: `gh pr merge <n> --merge --delete-branch`. **Never `--squash`, never `--rebase`** — this project preserves full per-commit history for bisection.
    *   Resolve any conflicts by rebasing in your worktree (not the GitHub UI) and `git push --force-with-lease` (never plain `--force`).
*   After the merge, delete the branch and worktree, and realign local `dev` (`git fetch origin dev && git reset --hard origin/dev`). See [`docs/git-strategy.md`](docs/git-strategy.md) §Day-one workflow step 5.
*   **Publication** (`dev` → `main`) is a separate, always-`Review` PR: `gh pr create --base main --head dev`, merged with `--merge --delete-branch=false` (`dev` is permanent). See [`docs/git-strategy.md`](docs/git-strategy.md) §Release branch.

## Testing

*   Adhere to the testing strategies outlined in [`design/specifications/test-spec.md`](design/specifications/test-spec.md).
*   **Unit Tests:** All new functions, methods, and components should have corresponding unit tests.
*   **Integration Tests:** Write integration tests for interactions between components or services, especially for API endpoints.
*   **End-to-End (E2E) Tests:** (To be implemented) For critical user flows.
*   Run all relevant tests locally before pushing changes or creating a PR.
*   Aim for high test coverage.

## Dependency Management

This project follows a strict dependency version pinning policy to ensure reproducible and stable builds. The full policy statement and rationale can be found in [`design/specifications/design-spec.md`](design/specifications/design-spec.md) (Section 6.0). All developers and AI assistants MUST adhere to the following practices:

*   **Python (Backend):**
    *   Dependencies are managed by **PDM** via the `pyproject.toml` file.
    *   To add a new dependency, navigate to `app/backend` and run:
        ```bash
        # For a production dependency
        pdm add <package-name>

        # For a development-only dependency (like linters or test tools)
        pdm add -G dev <package-name>
        ```
    *   PDM automatically pins the exact version in `pdm.lock` and updates `pyproject.toml`.
    *   Commit both the `pyproject.toml` and `pdm.lock` files to the repository.

*   **JavaScript/TypeScript (Frontend - React):**
    *   All packages listed in `app/frontend/web/package.json` (in both `dependencies` and `devDependencies`) MUST have their versions pinned — no `^` or `~` prefixes.
    *   Exact pinning is enforced automatically by `app/frontend/web/.npmrc` (`save-exact=true`): every `npm install <package-name>` writes the exact resolved version to `package.json`, so a normal install already produces a compliant pin.
    *   **Example (in `package.json`):** `"typescript": "5.9.3"` (ensure no `^` or `~` prefixes).
    *   Always commit the `package.json` and `package-lock.json` files.

*   **Containerization (Docker) & Database Systems:**
    *   The guidance for pinning versions for Docker base images and database systems remains the same. Always use specific version tags (e.g., `python:3.11.9-slim-buster`, `postgres:16-alpine`) and avoid `latest`.

## Issue Tracking

*   (Placeholder: Describe how issues are tracked, e.g., GitHub Issues. Include guidance on reporting bugs, suggesting features, and using labels.)

## Code Review Guidelines

Review depth is tied to the PR's **merge classification** (see [Pull Requests](#pull-requests-prs) and [`docs/git-strategy.md`](docs/git-strategy.md) §Merge authority), not applied uniformly:

*   **`Routine` PRs do not require a second human reviewer.** CI is the gate; the author verifies their own PR description, confirms green CI, and self-merges. This is deliberate — a rubber-stamp approval adds ceremony without independence.
*   **`Review` / `Escalate` PRs get a maintainer's judgment before merge.** Reviewers focus on the reason the PR was classified up: correctness and security for sensitive domains (auth, secrets, crypto, injection guards, data integrity), contract/schema stability for architecture changes, and the specific concern named in an `Escalate`.
*   **Adversarial review for meaningful changes.** Substantial PRs should get an adversarial second opinion (e.g. a `/codex review` pass) before merge, per repo policy.
*   **Authors** keep PRs small and focused, respond to feedback substantively rather than performatively (see the `superpowers:receiving-code-review` discipline), and fix CI failures to root cause rather than working around them.

---

## AI Assistant Guidance

This section provides guidance for AI coding assistants to effectively contribute to the Hangar Bay project.

### 1. Project Overview for AI Assistants

Hangar Bay is an EVE Online in-game asset marketplace, focusing initially on ship sales. The primary goal is to create a functional, secure, and user-friendly platform leveraging EVE Online's ESI API for game data and authentication.

**Core Technologies:**
*   **Backend:** Python with FastAPI
*   **Frontend:** React 19 (Vite, TypeScript, Tailwind CSS v4, TanStack Router/Query)
*   **Database:** PostgreSQL (local development **and** the test suite both use PostgreSQL — SQLite is not used anywhere; the test suite drops/recreates the `hangar_bay_test` database via `DATABASE_URL_TESTS`)
*   **Caching:** Valkey
*   **Authentication:** EVE SSO (OAuth 2.0)

### 2. How to Use These Specifications (AI Focus)

The [`design/`](design/) directory is your primary source of truth for requirements and implementation details. Key documents include:

*   [`design-spec.md`](design/specifications/design-spec.md): Overall architecture, features, and technology choices. Contains AI notes for high-level understanding.
*   [`features/`](design/features/): Individual feature specifications (e.g., `F001-*.md`, `F002-*.md`).
    *   These files detail specific application functionalities.
    *   **Key Structure:** Each feature spec now consistently includes a "0. Authoritative ESI & EVE SSO References" section at the beginning and AI actionable checklists for all defined ESI, EVE SSO, and Hangar Bay API endpoints.
    *   The `00-feature-spec-template.md` shows the overall template, including how data models, API endpoints, and general AI implementation guidance are structured. Use this template as a base when creating entirely new features.
*   [`security-spec.md`](design/specifications/security-spec.md): Detailed security requirements with AI actionable checklists and implementation patterns. Prioritize these strictly.
*   [`accessibility-spec.md`](design/specifications/accessibility-spec.md): Accessibility (WCAG 2.1 AA) requirements with AI actionable checklists and React-specific patterns.
*   [`test-spec.md`](design/specifications/test-spec.md): Testing strategy, including unit, integration, E2E, security, and accessibility testing, with AI patterns for test generation.
*   [`observability-spec.md`](design/specifications/observability-spec.md): Logging, metrics, and tracing strategy, emphasizing OpenTelemetry, with AI patterns for instrumentation.
*   [`i18n-spec.md`](design/specifications/i18n-spec.md): Internationalization strategy, including guidance for localizing FastAPI and the React frontend, and AI patterns for generating translatable content (frontend i18n is deferred in Milestone 1 — see that spec).
*   [`performance-spec.md`](design/specifications/performance-spec.md): Performance targets, design principles, testing methodologies, and AI guidance for backend (FastAPI, Valkey, PostgreSQL) and frontend (React) development.
*   [`ai-system-procedures.md`](design/meta/ai-system-procedures.md): Documents "AI System Procedures" (AISPs) – significant, recurring operational patterns for AI execution or participation.
    *   **Purpose:** AISPs provide a human-readable design record, detailing the problem, rationale, trigger conditions, AI execution steps, expected outcomes, and supporting details for complex or critical AI-involved workflows.
    *   **Usage:** While operational logic might be stored in AI memories, AISPs offer deeper context and step-by-step guidance. Refer to them to understand the 'why' and 'how' of these procedures. The document includes an `[AISP-000] AISP Entry Template` to guide the creation of new AISP entries.

**AI Action:** Before generating code for a feature or component, always consult the relevant specification documents. Pay close attention to sections titled `AI Implementation Guidance`, `AI Actionable Checklist`, or `AI Implementation Pattern` as they provide direct instructions and context.

### 3. Key Technologies (AI Focus)

*   **FastAPI (Backend):**
    *   Utilize Pydantic for request/response models and data validation.
    *   Employ dependency injection (`Depends`) for authentication and shared services.
    *   Follow RESTful API design principles.
    *   Refer to `security-spec.md` for input validation and `observability-spec.md` for OpenTelemetry integration patterns.
*   **React (Frontend):**
    *   Build with function components and hooks; TypeScript strict mode.
    *   Use TanStack Query for server state and TanStack Router (file-based) for URL-driven filter/sort/pagination state.
    *   Use the generated typed API client (`openapi-typescript` + `openapi-fetch`) for backend calls; regenerate types after backend schema changes.
    *   Refer to `accessibility-spec.md` for ARIA and focus-management guidance.
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
    *   Frontend: React components, hooks, TanStack Query/Router wiring, styles, tests.
4.  **Incorporate AI Guidance:** Actively use the `AI Implementation Guidance`, checklists, and patterns from the specs.
5.  **Testing:** Generate unit and integration tests as per `test-spec.md`. Include accessibility and security considerations in tests.
6.  **Review & Iterate:** The generated code will be reviewed. Be prepared to make adjustments based on feedback.

### 5. AI Prompts - Best Practices for Hangar Bay

*   **Be Specific:** Instead of "Create an API endpoint," try "Create a FastAPI GET endpoint at `/users/{user_id}` that retrieves user data based on the Pydantic model `UserRead` from `user_models.py`, ensuring it requires authentication and includes OpenTelemetry tracing as per `observability-spec.md`."
*   **Reference Specifications:** Explicitly mention which spec document and section your request relates to (e.g., "Implement input validation for the `ContractCreate` model as outlined in `security-spec.md`, section 3.1.").
*   **Iterative Prompts:** Break down complex tasks. Start with model generation, then API routes, then service logic, then tests.
*   **Request Tests:** Always ask for unit tests, and specify if integration or A11y tests are needed for a particular component.
*   **Focus on AI-Enhanced Specs:** Remind the AI to look for and use the AI-specific sections within the markdown files.
