# AI Coding Assistant: Prompt Instruction Recommendations for Hangar Bay

**Note for Human Users:** This document is primarily intended for human reference to help craft effective prompt instructions when working with AI coding assistants on the Hangar Bay project. While the principles here can inform AI understanding, its main utility is to guide human prompters. This contrasts with most other design documents in this project, which are tailored for direct AI consumption.

## 1. Core Principles for Effective AI Prompts

Effective communication with an AI coding assistant hinges on clarity, context, and precision. The following principles are foundational:

*   **Be Specific and Explicit:** Avoid ambiguity. Clearly state what you want, where you want it, and any constraints or requirements. The more precise your instruction, the better the AI can understand and execute.
*   **Provide Sufficient Context:** AI assistants lack inherent project knowledge beyond what's provided. Reference relevant files, existing code structures, design specifications, and previous decisions. The `design/` directory is a key contextual resource for Hangar Bay.
*   **Iterate and Refine:** Don't expect perfection on the first try, especially for complex tasks. Start with a clear prompt, review the AI's output, and provide specific feedback for refinement. Treat it as a collaborative dialogue.
*   **Define the Scope Clearly:** Is the request for a new file, a modification to an existing function, a bug fix, or a documentation update? Clearly define the boundaries of the task.

## 2. General Recommendations for Crafting Prompts

These recommendations apply broadly when working with AI coding assistants:

1.  **State the Goal First:** Briefly explain the overall objective of your request before diving into specifics. This helps the AI understand the 'why' behind the 'what'.
    *   *Example:* "I need to add error handling to the user login process. Specifically, ..."

2.  **Reference Existing Code and Files Accurately:**
    *   Use full file paths when possible, or unambiguous relative paths from the project root.
    *   Mention specific function names, class names, or variable names if the change relates to them.
    *   *Example:* "In `c:/Users/Sam/OneDrive/Documents/Code/hangar-bay/app/api/v1/endpoints/users.py`, modify the `create_user` function to..."

3.  **Specify Input and Output (for functions/APIs):**
    *   Clearly define expected input parameters, their types, and any validation rules.
    *   Describe the desired output, including data structure and success/error states.
    *   *Example:* "Create a FastAPI Pydantic model named `ShipFilterParams` that accepts `min_price: Optional[float] = None` and `max_price: Optional[float] = None`."

4.  **Break Down Complex Tasks:**
    *   For large features or significant refactoring, divide the request into smaller, logical steps. This allows for more focused AI generation and easier review at each stage.
    *   *Example:* Instead of "Build the entire contract viewing page," try: 
        1.  "Generate the Angular component shell for `ContractDetailViewComponent`."
        2.  "Add a service method to fetch contract details by ID."
        3.  "Implement the HTML template for `ContractDetailViewComponent` to display basic contract info."

5.  **Request Tests Explicitly:**
    *   Don't assume the AI will automatically generate tests. Ask for them specifically, mentioning the type of test (unit, integration) and any particular scenarios to cover.
    *   *Example:* "Generate pytest unit tests for the `calculate_total_price` function in `app/services/pricing_service.py`. Include test cases for zero quantity, negative price, and valid inputs."

6.  **Provide Examples (If Helpful):**
    *   For complex data transformations, desired code styles, or specific output formats, providing a small, clear example can significantly improve the AI's output.

7.  **Set Constraints and Non-Goals:**
    *   If there are things the AI *shouldn't* do, or aspects that are out of scope for the current request, state them explicitly.
    *   *Example:* "Update the user profile form. Do not change the existing API endpoint for now."

## 3. Hangar Bay Specific Recommendations

Leverage the AI-enhanced design documentation we've created:

1.  **Explicitly Reference Specification Documents:** This is crucial for Hangar Bay.
    *   Direct the AI to consult specific sections of `design-spec.md`, `security-spec.md`, `accessibility-spec.md`, `test-spec.md`, `observability-spec.md`, or individual feature specs in `design/features/`.
    *   *Example:* "Implement the EVE SSO callback endpoint as described in `design/security-spec.md`, Section 2.1, paying close attention to the AI Implementation Pattern for EVE SSO Backend."
    *   *Example:* "Generate Angular form component for user registration. Ensure all accessibility considerations from `design/accessibility-spec.md`, Section on Angular Forms A11y, are met."

2.  **Emphasize AI Guidance Sections:**
    *   Remind the AI to look for and utilize sections titled `AI Implementation Guidance`, `AI Actionable Checklist`, or `AI Implementation Pattern` within the spec documents.
    *   *Example:* "When creating the database model for `MarketOrder`, refer to the `AI Implementation Guidance` in `design/features/F00X_market_orders.md` for Pydantic and SQLAlchemy best practices."

3.  **Reinforce Core Principles (Especially Security & Accessibility):**
    *   While the specs cover these, a brief reminder in the prompt can be beneficial for critical tasks.
    *   *Example:* "Create the API endpoint for submitting new ship listings. Ensure all input validation follows the patterns in `security-spec.md` and that logging adheres to `observability-spec.md`."

4.  **Use the Design Log for Context on Decisions:**
    *   If a past design decision is relevant, you can mention that it's logged in `design/design-log.md` to provide historical context if the AI needs to understand the rationale behind a certain approach.

## 4. Providing Feedback to the AI

*   **Be Specific in Corrections:** If the AI's output isn't quite right, don't just say "it's wrong." Explain *what* is wrong, *why* it's wrong, and *how* to correct it. Reference specific lines of code if possible.
*   **Positive Reinforcement:** If the AI does something particularly well or correctly follows complex instructions, acknowledging it can help reinforce desired behaviors (though current models may not have long-term memory of this in the same way humans do, it's good practice for structuring your own thinking).
*   **Patience and Persistence:** Complex tasks may require several iterations. Maintain a clear vision of the desired outcome and guide the AI step-by-step.

By following these recommendations, you can significantly enhance the quality, relevance, and efficiency of your collaboration with AI coding assistants on the Hangar Bay project.
