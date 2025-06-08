# Task XX.Y: [Task Title]

**Phase:** XX - [Phase Name]
**Parent Plan:** [Link to Parent Phase Plan or Overview Plan]
**Last Updated:** YYYY-MM-DD

_AI Guidance: Replace `XX.Y`, `[Task Title]`, `[Phase Name]`, `[Link to Parent Plan]`, and `YYYY-MM-DD` with specific details for the task._

## 1. Objective

_AI Guidance: Clearly and concisely define the primary goal of this task. What specific problem will be solved or what feature will be implemented? Focus on the 'what' and 'why' of the task. This should be a brief paragraph, 2-4 sentences long._

## 2. Relevant Specifications

_AI Guidance: List all relevant design documents, specification files (e.g., `../design/design-spec.md`, `../design/security-spec.md`, specific feature specs from `../design/features/`), or external documentation that provide context or requirements for this task. Use bullet points and include paths relative to this task file or the project root. Ensure links are functional if possible._
*   `../design/[relevant-spec-1].md`
*   `../design/features/[relevant-feature-spec].md`

## 3. Key Implementation Steps

_AI Guidance: Break down the task into smaller, actionable steps. For each step:
*   Use markdown checkboxes: `* [ ] Step description`.
*   Be specific about the actions to be taken.
*   If the step involves code generation, complex commands, or requires specific AI assistance, include an 'AI Prompt:' subsection with a clear, detailed prompt for Cascade.
*   Distinguish between Backend, Frontend, or other relevant components if applicable using subheadings (e.g., `### 3.1. Backend (Python/FastAPI)`, `### 3.2. Frontend (Angular)`)._

### 3.1. [Component 1 / Aspect 1]

*   [ ] **Step 1.1:** Description of the first step.
    *   **AI Prompt (if needed):** "Generate/explain/create..."
*   [ ] **Step 1.2:** Description of the second step.

### 3.2. [Component 2 / Aspect 2]

*   [ ] **Step 2.1:** Description of the first step for this component.

## 4. AI Implementation Guidance

_AI Guidance: Provide specific instructions, preferences, or constraints for Cascade when assisting with this task. This helps tailor AI support effectively. This could include:
*   Preferred libraries, frameworks, or versions (e.g., "Use Pydantic V2 for data models").
*   Coding style reminders (e.g., "Adhere to PEP 8 for Python code").
*   Specific patterns to follow or avoid (e.g., "Avoid using global variables; prefer dependency injection").
*   Key considerations for AI-generated code or commands (e.g., "Ensure all generated shell commands are POSIX-compliant").
*   Example: "When generating FastAPI routes, ensure all paths are prefixed with `/api/v1` and include appropriate OpenAPI documentation (summary, description, tags). Responses should use Pydantic models."_

*   Guidance point 1.
*   Guidance point 2.

## 5. Definition of Done (DoD)

_AI Guidance: List clear, verifiable, and measurable criteria that must be met for this task to be considered complete. Each item should be a specific outcome that can be demonstrated or checked.
*   Example: `* New API endpoint `/feature-x` is implemented, tested, and returns the expected data structure as per the spec.`
*   Example: `* Unit tests for all new backend logic achieve >85% statement coverage.`
*   Example: `* Frontend component for Feature X is implemented, displays correctly, and interacts with the backend as expected.`
*   Example: `* Relevant documentation (e.g., README, API docs, inline code comments) is updated to reflect changes.`
*   Example: `* All acceptance criteria listed in the feature specification `../design/features/[relevant-feature-spec].md` are met.`
*   Example: `* Code has been reviewed and approved.`
*   Example: `* All related items in the 'Cross-Cutting Concerns Review' section (Section 7) are addressed and checked off.`_

*   [ ] Criterion 1.
*   [ ] Criterion 2.
*   [ ] All new code is committed to the `[feature/task-branch-name]` branch.

## 6. Challenges & Resolutions

_AI Guidance: This section is for documenting any significant challenges encountered *during* the execution of the task, the solutions or workarounds applied, and any lessons learned or notes for future developers or Cascade.
*   Format each entry:
    *   `* **Challenge:** [Brief description of the challenge encountered.]`
    *   `  **Resolution:** [How the challenge was overcome or the solution implemented.]`
    *   `  **Future Cascade/Developer Note:** [Optional: Key takeaways, advice, or reminders for similar future tasks or for Cascade's learning.]`
*   Initially, this section will be a placeholder. It should be filled in as work progresses and challenges arise._

*   (Placeholder for any challenges encountered and their resolutions during this task.)

## 7. Cross-Cutting Concerns Review

_AI Guidance: This section MUST be filled out before the task is considered complete. For each of the five concerns (Security, Observability, Testing, Accessibility, Internationalization), review the checklist items.
*   Mark `[x]` for items that have been addressed or are N/A with justification.
*   Leave `[ ]` for items that are pending or need further action for THIS task.
*   Use the 'Notes' sub-section under each concern to detail specific actions taken, provide rationale for N/A items, or reference specific code/documentation.
*   Refer to the linked primary specification documents for detailed guidance on each concern. The paths below are relative to this template's location; adjust if this template is moved or copied to a deeper directory structure._

This section documents how the five key cross-cutting concerns were addressed during the completion of this task. Refer to the primary specification documents for detailed guidance:
*   Security: `../design/security-spec.md`
*   Observability: `../design/observability-spec.md`
*   Testing: `../design/test-spec.md`
*   Accessibility: `../design/accessibility-spec.md`
*   Internationalization (i18n): `../design/i18n-spec.md`

### 7.1. Security
*   [ ] **Secure Design:** (e.g., threat modeling, principle of least privilege)
*   [ ] **Input Validation:** (e.g., validating all external inputs)
*   [ ] **Output Encoding:** (e.g., preventing XSS)
*   [ ] **Authentication/Authorization:** (e.g., ensuring proper checks)
*   [ ] **Secrets Management:** (e.g., secure storage and access)
*   [ ] **Dependency Management:** (e.g., checking for vulnerable libraries)
*   **Notes:** (Detail specific actions taken or rationale for no action, especially if a category is not applicable to this task.)

### 7.2. Observability
*   [ ] **Structured Logging:** (e.g., using key-value pairs, JSON format)
*   [ ] **Key Events Logged:** (e.g., task initiation, completion, critical errors, significant state changes)
*   [ ] **Error Logging:** (e.g., comprehensive error details, stack traces)
*   [ ] **Correlation IDs:** (e.g., for tracing requests across services)
*   [ ] **Metrics:** (e.g., performance indicators, resource usage - if applicable)
*   **Notes:** (Detail specific actions taken or rationale for no action.)

### 7.3. Testing
*   [ ] **Unit Tests:** (e.g., for new functions, classes, components)
*   [ ] **Integration Tests:** (e.g., for interactions between components/services)
*   [ ] **Test Coverage:** (e.g., summary of coverage achieved or targeted)
*   [ ] **Test Data Management:** (e.g., how test data is sourced/managed)
*   **Notes:** (Detail specific actions taken or rationale for no action.)

### 7.4. Accessibility (A11y)
*(Primarily for UI-related tasks, but consider CLI/API accessibility where relevant)*
*   [ ] **Semantic HTML/Structure:** (e.g., using appropriate tags for meaning)
*   [ ] **ARIA Attributes:** (e.g., for dynamic content or custom controls)
*   [ ] **Keyboard Navigability:** (e.g., all interactive elements reachable and operable via keyboard)
*   [ ] **Color Contrast:** (e.g., ensuring sufficient contrast for text and UI elements)
*   [ ] **Screen Reader Compatibility:** (e.g., testing with screen readers)
*   [ ] **Alternative Text for Images:** (e.g., providing descriptive alt text)
*   **Notes:** (Detail specific actions taken or rationale for no action, especially if not UI-related.)

### 7.5. Internationalization (I18n)
*(Primarily for UI-related tasks, but consider for any user-facing text including logs/error messages)*
*   [ ] **Text Abstraction:** (e.g., using translation keys instead of hardcoded strings)
*   [ ] **Locale-Specific Formatting:** (e.g., for dates, numbers, currencies)
*   [ ] **UI Layout Adaptability:** (e.g., for text expansion in different languages)
*   [ ] **Character Encoding:** (e.g., using UTF-8)
*   **Notes:** (Detail specific actions taken or rationale for no action, especially if not UI-related.)

---
<!-- This section should be placed before any final "Task Completion Checklist" or similar concluding remarks. -->
