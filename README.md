# Hangar Bay
An ecommerce site for selling ships in the video game EVE Online.

Inspired by a friend who plays EVE and said:
"I can see where GPT could be useful for code snippets, but I can't imagine it's able to deliver any sort of comprehensive outcome. If I say, "write me an ecommerce site for selling ships in eve online" theres no way its going to do that right?
It's going to give me some template code about a shopping cart or something and thats it. Right?"

There's only one way to find out! 

Presently, I'm using this as an example project in developing a sophisticated software design specification tailored for AI coding assistants. 
There is a specific focus on ensuring that critical non-functional requirements (security, accessibility, testability, observability) are consistently addressed. Given concerns about AI coding assistant not producing especially secure code, I am especially interested in methods to get them to adhere to modern secure coding practices and incorporate security considerations into the design process. In this project, I'm attempting to do that by developing a security-spec.md that provides secure design principles tailored to the project, a checklist of security requirements, and AI implementation guidance for secure practices for the tech stack that it can (and must) reference while developing each feature. 

Please refer to the main design specification in [`design/design-spec.md`](design/design-spec.md) for a comprehensive overview of the project. The `design` directory contains detailed specifications for various aspects of the application, which have been enhanced with AI-specific guidance.

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
    *   Define models in `app/models/` (example path).
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